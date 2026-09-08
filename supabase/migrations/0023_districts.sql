-- اشتراطات الأحياء: الحكم على الحيّ لا على دائرة.
--
-- بعض الأحياء لا تُستقبل فيها حجوزات، وبعضها لا تُخدم لعميلةٍ واحدة، وبعضها
-- عليه رسوم مواصلات. وحدود الأحياء ليست دوائر، فالدائرة تلتقط طرفَ حيٍّ
-- مجاور ولا تلتقط طرفَ الحيّ المقصود. لذلك الحكم بالمضلّع: النقطة تقع
-- داخل حيٍّ بعينه أو لا تقع.
--
-- والمبدأ كما هو في حارس الإيصال: المتصفّح يعرض والقاعدة تحكم. الصفحة
-- ترسل إحداثيّتين لا اسم حيٍّ ولا حكمًا.
--
-- ── فرقٌ مقصود عن حارس الإيصال ───────────────────────────────────────
-- ذاك يكتم سببه لأنّ من عرف الشرط زوّر صورةً تتجاوزه. وهذا **يقول سببه**:
-- العميلة لا تختار حيَّها فلا شيء يُزوَّر، وكتمانُ السبب يجعلها تظنّ
-- بالمنصّة عطبًا فتذهب.

/* ═══ ١) الأحياء ═══════════════════════════════════════════════════════
   تُستورد مرّةً من ملفّ حدود أحياء الرياض (تصنيف الهيئة الملكية لمدينة
   الرياض). لا تُكتب في المستودع: تُرفع من اللوحة، فتحديثُ الحدود لاحقًا
   استيرادٌ آخر لا نشرُ شيفرة. */

create table if not exists public.districts (
  id        bigint primary key,
  ar        text not null,
  en        text,
  lat       numeric(9,6) not null,
  lng       numeric(9,6) not null,
  rings     jsonb not null,
  min_lat   numeric(9,6) not null,
  max_lat   numeric(9,6) not null,
  min_lng   numeric(9,6) not null,
  max_lng   numeric(9,6) not null,
  added_at  timestamptz not null default now()
);

-- صندوقٌ محيط قبل المضلّع: يستبعد أغلب الأحياء بمقارنتين لا بمسحِ رؤوس.
create index if not exists districts_bbox_idx
  on public.districts (min_lat, max_lat, min_lng, max_lng);
create index if not exists districts_ar_idx on public.districts (ar);

alter table public.districts enable row level security;
drop policy if exists "districts readable" on public.districts;
-- أسماء الأحياء وحدودها معلومةٌ عامّة، وقراءتها تُغني اللوحة عن حِيَل.
create policy "districts readable" on public.districts for select using (true);

/* ═══ ٢) الشروط ════════════════════════════════════════════════════════
   حيٌّ بلا سطرٍ هنا = بلا شرط. فلا تحتاج صاحبة العمل أن تلمس مئةً وثمانين
   حيًّا لتستثني عشرين.

   و`active` مفتاحُ تعطيلٍ لا حذف: رسوم العمارية موسميّة — تُطفأ حين
   يهدأ الطلب وتُشعل حين يعود، والمبلغ والرسالة باقيان كما ضُبطا. */

create table if not exists public.district_rules (
  district_id bigint primary key references public.districts(id) on delete cascade,
  reject      boolean not null default false,
  min_people  smallint not null default 0,      -- ٠ = بلا حدّ
  fee_amount  numeric(10,2) not null default 0,
  message     text,
  active      boolean not null default true,
  updated_at  timestamptz not null default now()
);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'district_rules_sane_ck') then
    alter table public.district_rules add constraint district_rules_sane_ck
      check (min_people between 0 and 12 and fee_amount between 0 and 100000);
  end if;
end $$;

alter table public.district_rules enable row level security;
drop policy if exists "district rules admin" on public.district_rules;
-- الشروط تُقرأ بدالّةٍ مالكة عند الفحص؛ ولا تُعرض للعميلة قائمةً تُدرَس.
create policy "district rules admin" on public.district_rules
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

/* ═══ ٣) ما خارج الأحياء المعروفة ══════════════════════════════════════
   الخرج والمزاحمية محافظتان لا حيّان، والدرعية والعمارية بلديّتان
   مستقلّتان. فبدل رسم حدودٍ لكل بعيد: سطرٌ واحد يحكم كلَّ ما لم يقع في
   حيٍّ معروف. وما تخدمه صاحبة العمل فعلًا خارج الرياض يُضاف حيًّا
   كسائر الأحياء فيخرج من هذا الحكم. */

alter table public.settings
  add column if not exists loc_check_enabled boolean not null default false,
  add column if not exists outside_reject    boolean not null default true,
  add column if not exists outside_min       smallint not null default 0,
  add column if not exists outside_fee       numeric(10,2) not null default 0,
  add column if not exists outside_message   text
    default 'هذا الموقع خارج نطاق خدمتنا. تواصلي معنا لنرى إن كان بالإمكان ترتيبه.';

/* ═══ ٤) أين تقع النقطة ════════════════════════════════════════════════
   رميُ شعاعٍ (ray casting): يُعدّ كم ضلعًا يقطع الشعاعُ الخارجُ من النقطة.
   فرديٌّ = داخل. والحلقات المتعدّدة تتناوب، فالثقب داخل المضلّع يُخرج. */

create or replace function public.point_in_rings(p_lat numeric, p_lng numeric, p_rings jsonb)
returns boolean
language plpgsql immutable
as $fn$
declare
  ring jsonb; n int; i int; inside boolean := false;
  -- لا تُسمَّ متغيّرات هنا `by`: كلمةٌ محجوزة في plpgsql فتسقط الدالّة
  -- بخطأ صياغةٍ غامض (وقع مثلها في عمود اسمه `trigger`).
  y1 numeric; x1 numeric; y2 numeric; x2 numeric; dy numeric;
begin
  for ring in select value from jsonb_array_elements(coalesce(p_rings, '[]'::jsonb)) loop
    n := jsonb_array_length(ring);
    if n is null or n < 3 then continue; end if;
    for i in 0 .. n - 1 loop
      -- الإحداثيات مخزَّنة [خط العرض، خط الطول] كما في ملفّ المصدر.
      y1 := (ring->i->>0)::numeric;               x1 := (ring->i->>1)::numeric;
      y2 := (ring->((i + 1) % n)->>0)::numeric;   x2 := (ring->((i + 1) % n)->>1)::numeric;
      dy := y2 - y1;
      if dy <> 0 and ((y1 > p_lat) <> (y2 > p_lat))
         and (p_lng < (x2 - x1) * (p_lat - y1) / dy + x1)
      then inside := not inside;
      end if;
    end loop;
  end loop;
  return inside;
end $fn$;

/** الحيّ الذي تقع فيه النقطة، أو لا شيء. الأصغر يفوز عند التداخل. */
create or replace function public.district_at(p_lat numeric, p_lng numeric)
returns public.districts
language sql stable
as $$
  select d.* from public.districts d
   where p_lat between d.min_lat and d.max_lat
     and p_lng between d.min_lng and d.max_lng
     and public.point_in_rings(p_lat, p_lng, d.rings)
   order by (d.max_lat - d.min_lat) * (d.max_lng - d.min_lng) asc
   limit 1;
$$;

/* ═══ ٥) الحكم ═════════════════════════════════════════════════════════
   يردّ ما تعرضه الصفحة: الحيّ، وحالُه، وما يترتّب. ويقول سببه — §الفرق
   المقصود أعلاه. */

create or replace function public.check_location(
  p_lat numeric, p_lng numeric, p_people integer default 1)
returns jsonb
language plpgsql stable security definer set search_path to 'public', 'pg_temp'
as $fn$
declare
  d public.districts%rowtype;
  r public.district_rules%rowtype;
  s public.settings%rowtype;
  v_people int := greatest(coalesce(p_people, 1), 1);
  v_reject boolean; v_min int; v_fee numeric; v_msg text; v_where text;
begin
  select * into s from public.settings where id = 1;
  if not coalesce(s.loc_check_enabled, false) then
    return jsonb_build_object('state', 'ok', 'checked', false);
  end if;
  if p_lat is null or p_lng is null then
    return jsonb_build_object('state', 'ok', 'checked', false);
  end if;

  select * into d from public.district_at(p_lat, p_lng);

  if d.id is null then
    v_where  := 'خارج الأحياء المعروفة';
    v_reject := coalesce(s.outside_reject, true);
    v_min    := coalesce(s.outside_min, 0);
    v_fee    := coalesce(s.outside_fee, 0);
    v_msg    := s.outside_message;
  else
    select * into r from public.district_rules where district_id = d.id;
    v_where := d.ar;
    if not found or not r.active then
      return jsonb_build_object('state', 'ok', 'checked', true,
                                'district', d.ar, 'district_id', d.id);
    end if;
    v_reject := r.reject; v_min := r.min_people; v_fee := r.fee_amount; v_msg := r.message;
  end if;

  if v_reject then
    return jsonb_build_object('state', 'reject', 'checked', true,
      'district', v_where, 'district_id', d.id,
      'message', coalesce(nullif(btrim(v_msg), ''), 'لا نستقبل حجوزات في هذا الموقع حاليًا.'));
  end if;

  if v_min > 1 and v_people < v_min then
    return jsonb_build_object('state', 'blocked', 'checked', true,
      'district', v_where, 'district_id', d.id, 'min_people', v_min, 'fee', v_fee,
      'message', coalesce(nullif(btrim(v_msg), ''),
        format('هذا الموقع يتطلّب حجزًا لـ %s أشخاص فأكثر.', v_min)));
  end if;

  if v_fee > 0 or v_min > 1 then
    return jsonb_build_object('state', 'condition', 'checked', true,
      'district', v_where, 'district_id', d.id, 'min_people', v_min, 'fee', v_fee,
      'message', coalesce(nullif(btrim(v_msg), ''),
        case when v_fee > 0 then 'على هذا الموقع رسوم مواصلات إضافية.'
             else 'على هذا الموقع شرط.' end));
  end if;

  return jsonb_build_object('state', 'ok', 'checked', true,
                            'district', v_where, 'district_id', d.id);
end $fn$;
revoke all on function public.check_location(numeric, numeric, integer) from public;
grant execute on function public.check_location(numeric, numeric, integer) to anon, authenticated;

/* ═══ ٦) الرسوم في الحجز ═══════════════════════════════════════════════
   سطرٌ مستقلّ باسم الحيّ، لا رقمٌ مبهم داخل الإجمالي. ويُحفظ اسم الحيّ
   ومبلغه مع الحجز: الشرط قد يتغيّر لاحقًا، والحجز القديم يجب أن يبقى
   مفسَّرًا كما حُسب يومه. والعربون يبقى على الخدمات وحدها. */

alter table public.bookings
  add column if not exists loc_fee        numeric(10,2) not null default 0,
  add column if not exists loc_district   text,
  add column if not exists loc_district_id bigint;

create or replace function public.bookings_apply_override()
returns trigger
language plpgsql
as $fn$
begin
  -- تجاوز الإدارة كلمةٌ أخيرة: إن كتبت إجماليًا فهو الإجمالي بلا خصم ولا
  -- رسمٍ فوقه.
  new.price := greatest(
    coalesce(new.price_override,
             new.items_total - new.discount + coalesce(new.loc_fee, 0)), 0);
  if new.deposit > new.price then new.deposit := new.price; end if;
  if new.deposit < 0 then new.deposit := 0; end if;
  return new;
end $fn$;

/* ═══ ٧) الاستيراد من اللوحة ═══════════════════════════════════════════
   يُرفع الملفّ مرّة، فتُبنى الحدود والصناديق المحيطة. والشروط لا تُمسّ:
   تُربط بالمعرّف فتبقى بعد أيّ تحديثٍ للحدود. */

create or replace function public.admin_import_districts(p_rows jsonb)
returns jsonb
language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
declare n_in int := 0; n_now int; n_rules int;
begin
  if not public.is_admin() then
    raise exception 'not authorised' using errcode = '42501';
  end if;
  if jsonb_typeof(p_rows) <> 'array' then
    raise exception 'الملفّ غير مقروء' using errcode = '22023';
  end if;

  with src as (
    select (x->>'id')::bigint                                as id,
           btrim(x->>'ar')                                   as ar,
           nullif(btrim(coalesce(x->>'en', '')), '')         as en,
           (x->'c'->>0)::numeric                             as lat,
           (x->'c'->>1)::numeric                             as lng,
           x->'rings'                                        as rings
      from jsonb_array_elements(p_rows) x
     where (x->>'id') ~ '^[0-9]+$'
       and btrim(coalesce(x->>'ar', '')) <> ''
       and jsonb_typeof(x->'rings') = 'array'
  ), box as (
    select s.*,
           (select min((p->>0)::numeric) from jsonb_array_elements(s.rings) r,
                   jsonb_array_elements(r) p) as min_lat,
           (select max((p->>0)::numeric) from jsonb_array_elements(s.rings) r,
                   jsonb_array_elements(r) p) as max_lat,
           (select min((p->>1)::numeric) from jsonb_array_elements(s.rings) r,
                   jsonb_array_elements(r) p) as min_lng,
           (select max((p->>1)::numeric) from jsonb_array_elements(s.rings) r,
                   jsonb_array_elements(r) p) as max_lng
      from src s
  ), ins as (
    insert into public.districts (id, ar, en, lat, lng, rings,
                                  min_lat, max_lat, min_lng, max_lng)
    select id, ar, en, lat, lng, rings, min_lat, max_lat, min_lng, max_lng
      from box where min_lat is not null
    on conflict (id) do update
      set ar = excluded.ar, en = excluded.en, lat = excluded.lat, lng = excluded.lng,
          rings = excluded.rings, min_lat = excluded.min_lat, max_lat = excluded.max_lat,
          min_lng = excluded.min_lng, max_lng = excluded.max_lng
    returning 1)
  select count(*) into n_in from ins;

  select count(*) into n_now   from public.districts;
  select count(*) into n_rules from public.district_rules;
  return jsonb_build_object('imported', n_in, 'districts', n_now, 'rules_kept', n_rules);
end $fn$;
revoke all on function public.admin_import_districts(jsonb) from public, anon;
grant execute on function public.admin_import_districts(jsonb) to authenticated;

/** حفظ شرطٍ واحد على عدّة أحياء دفعةً واحدة — وهو ما تفعله صاحبة العمل. */
create or replace function public.admin_set_district_rule(
  p_ids bigint[], p_reject boolean, p_min integer, p_fee numeric,
  p_message text, p_active boolean default true)
returns integer
language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
declare n int;
begin
  if not public.is_admin() then
    raise exception 'not authorised' using errcode = '42501';
  end if;
  if p_ids is null or array_length(p_ids, 1) is null then return 0; end if;

  with ins as (
    insert into public.district_rules (district_id, reject, min_people, fee_amount, message, active)
    select unnest(p_ids), coalesce(p_reject, false),
           least(greatest(coalesce(p_min, 0), 0), 12),
           least(greatest(coalesce(p_fee, 0), 0), 100000),
           nullif(btrim(coalesce(p_message, '')), ''), coalesce(p_active, true)
    on conflict (district_id) do update
      set reject = excluded.reject, min_people = excluded.min_people,
          fee_amount = excluded.fee_amount, message = excluded.message,
          active = excluded.active, updated_at = now()
    returning 1)
  select count(*) into n from ins;
  return n;
end $fn$;
revoke all on function public.admin_set_district_rule(bigint[], boolean, integer, numeric, text, boolean) from public, anon;
grant execute on function public.admin_set_district_rule(bigint[], boolean, integer, numeric, text, boolean) to authenticated;

create or replace function public.admin_clear_district_rule(p_ids bigint[])
returns integer
language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
declare n int;
begin
  if not public.is_admin() then
    raise exception 'not authorised' using errcode = '42501';
  end if;
  delete from public.district_rules where district_id = any(coalesce(p_ids, '{}'));
  get diagnostics n = row_count;
  return n;
end $fn$;
revoke all on function public.admin_clear_district_rule(bigint[]) from public, anon;
grant execute on function public.admin_clear_district_rule(bigint[]) to authenticated;

/** ما تعرضه اللوحة: كلّ حيٍّ وشرطُه إن كان. */
create or replace function public.admin_districts()
returns table (id bigint, ar text, lat numeric, lng numeric,
               reject boolean, min_people smallint, fee_amount numeric,
               message text, active boolean)
language sql stable security definer set search_path to 'public', 'pg_temp'
as $$
  select d.id, d.ar, d.lat, d.lng,
         r.reject, r.min_people, r.fee_amount, r.message, r.active
    from public.districts d
    left join public.district_rules r on r.district_id = d.id
   where public.is_admin()
   order by d.ar;
$$;
revoke all on function public.admin_districts() from public, anon;
grant execute on function public.admin_districts() to authenticated;
