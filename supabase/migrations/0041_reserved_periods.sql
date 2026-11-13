-- ٠٠٤١ فترةٌ مخصّصة لخدمة (§٧ع في CLAUDE.md).
--
-- تختار إيمان شهرًا، أو نطاقًا من تاريخ إلى تاريخ، أو أيامًا بعينها، وتحدّد
-- الخدمة المخصّصة لها — ميك اب العروس مثلًا. والحكم جملةٌ واحدة:
--
--   في سلّة العميلة خدمةٌ واحدة على الأقل من المخصّصة للفترة ← يُقبل حجزها بكل ما فيه.
--   وإلّا ← يُردّ برسالةٍ تكتبها إيمان.
--
-- اعتمد صاحب المشروع الشكل والحالات الحدّية (١٤ نوفمبر ٢٠٢٦، صفحة المقترحات
-- CVypWFmRJZ9yD563NMseK7).
--
-- - **المخزَّن أيامٌ بعينها** (`dates`) مهما كانت طريقة الإدخال، فالحكم عند الحجز سؤالٌ
--   واحد: «هل اليوم في الفترة؟». و`mode` تلميحٌ للّوحة وحدها لتفتح الفترة بالطريقة التي
--   اختارتها، لا يقرؤه حُكم.
-- - **حكمٌ واحد لكلّ يوم.** مشغّلٌ يردّ فترةً تشارك أخرى يومًا — نشطةً كانت أو موقوفة،
--   فالموقوفة تُفعَّل في موسمها فلا يجوز أن تجد من سبقها. ولا يُصلح التعارضَ بالصمت:
--   يُردّ الحفظ، والّلوحة تعلّم الأيام المأخوذة قبل الاختيار.
-- - **الخدمة تُعرف بمعرّفها لا باسمها** (نمطُ «العروس تُعرف بالصفّ» في §٧د): الاسم يتغيّر
--   والحكم لا يحتمل تخمينًا. وفترةٌ لم تبقَ فيها خدمةٌ موجودة لا تحجب أحدًا، وإلّا أُقفل
--   الشهر على الجميع بحذفِ خدمة.
-- - **القاعدة تحكم والصفحة تعرض.** `days_with_availability` تردّ لكلّ يومٍ هل هو «مخصّص»
--   (كان سيُفتح لولا الفترة) وتردّ رسالته، فيُرسم باهتًا بنمطٍ مخطّط ويُفرَّق عن المقفل؛
--   و`available_slots` لا تفتح اليوم لسلّةٍ لا تناسبه. والوسيط الجديد اختياريّ: بلا
--   خدماتٍ تعمل الدالّتان كما كانتا، فلا تتعطّل صفحةٌ قديمة.
-- - **الحارس الأخير بمصافحة الميزات.** `create_booking` ترفض بالرسالة، لكن لا تفعل إلّا مع
--   صفحةٍ تقول إنها تعرف الفترات (`p_features` بتّ ١) — وإلّا ضاع عربونٌ حُوّل بصفحةٍ لا
--   ترى المنع (وقع في فحص الموقع مرّتين، §٧د). وهي وسيطٌ مستقلّ لا رقمُ نسخةٍ مشترك:
--   صفحة الجذر لا تحمل فحص الموقع، فلو ادّعت `p_client_v = 3` لادّعت معرفته ورُفضت
--   حجوزاتها كلّها يوم يُشعل. والثمنُ مقبول ومقصود: من ينادي مباشرةً بلا بتّ ١ يتخطّى الفترة،
--   والحجز يصل «معلّقًا» فتراه إيمان قبل التأكيد.
-- - **الحجز اليدويّ من اللوحة لا يتقيّد** (لا يمرّ بهذه الدوالّ بخدماتٍ)، والحجوزات القائمة
--   لا تُلغى ولا تتغيّر.
-- - **تدخل النسخة الاحتياطية والاستعادة** (`snapshot_coverage.sql`)، والاستعادة تُعيد الغائب
--   ولا تمسّ القائم، وتتخطّى ما يتعارض مع فترةٍ قائمة بدل أن تسقط كلّها.
--
-- الدوالّ الثلاث (`available_slots` و`days_with_availability` و`create_booking`) يتغيّر
-- توقيعُها، فيُسقط التوقيع القديم قبل الجديد: وجودهما معًا يجعل نداء المتصفّح «غير
-- وحيد» فيسقط. وتُشتقّ من تعريفاتها القائمة (نمطُ ٠٠٣٨ و٠٠٣٩)، وكلّ موضعٍ يُطلب مرّةً
-- واحدة بالضبط وإلّا أُلغي الترحيل بدل أن يمضي على نصٍّ غير ما رُجِع.

create table if not exists public.reserved_periods (
  id          uuid primary key default gen_random_uuid(),
  mode        text not null default 'days' check (mode in ('month', 'range', 'days')),
  dates       date[] not null,
  service_ids uuid[] not null,
  message     text not null,
  active      boolean not null default true,
  created_at  timestamptz not null default now(),
  constraint reserved_dates_ck    check (cardinality(dates) between 1 and 400),
  constraint reserved_services_ck check (cardinality(service_ids) between 1 and 12),
  constraint reserved_message_ck  check (length(btrim(message)) between 1 and 200)
);
comment on table public.reserved_periods is
  'فترةٌ مخصّصة لخدمة: أيامٌ بعينها وخدمةٌ أو أكثر ورسالة. من في سلّتها إحدى الخدمات تُقبل بكل ما معها، وغيرها يُردّ بالرسالة.';

-- المديرة وحدها تقرأ وتكتب مباشرة (نمطُ date_overrides)، والعميلة لا ترى الجدول:
-- ما يخصّها يصلها من days_with_availability.
alter table public.reserved_periods enable row level security;
revoke all on public.reserved_periods from anon;
grant select, insert, update, delete on public.reserved_periods to authenticated;
drop policy if exists admin_all_reserved on public.reserved_periods;
create policy admin_all_reserved on public.reserved_periods
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- هل تشارك هذه الأيام فترةً أخرى؟ (والفترة نفسها لا تُعدّ: p_id هو المستثنى عند التعديل.)
-- دالّةٌ منفصلة لأنّ الحذف والتعديل يُمنعان على الحيّ بلا موافقة، فيُفحص منطقُ التعديل بها
-- وحدها بـ select.
create or replace function public.reserved_overlap(p_id uuid, p_dates date[])
returns boolean language sql stable
set search_path to 'public', 'pg_temp'
as $$
  select exists (select 1 from public.reserved_periods o
                  where o.id is distinct from p_id and o.dates && p_dates);
$$;
revoke execute on function public.reserved_overlap(uuid, date[]) from public, anon, authenticated;

create or replace function public.tg_reserved_periods()
returns trigger
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $fn$
begin
  new.dates := coalesce((select array_agg(distinct d order by d) from unnest(new.dates) d where d is not null), '{}');
  new.service_ids := coalesce((select array_agg(distinct s) from unnest(new.service_ids) s where s is not null), '{}');
  new.message := btrim(coalesce(new.message, ''));
  if public.reserved_overlap(new.id, new.dates) then
    raise exception 'أيامٌ من هذه الفترة داخل فترةٍ مخصّصة أخرى' using errcode = 'P0001';
  end if;
  return new;
end $fn$;
revoke execute on function public.tg_reserved_periods() from public, anon, authenticated;

drop trigger if exists reserved_periods_guard on public.reserved_periods;
create trigger reserved_periods_guard
  before insert or update on public.reserved_periods
  for each row execute function public.tg_reserved_periods();

-- رسالة المنع إن كان اليوم مخصّصًا لخدماتٍ ليس في السلّة منها شيء، وإلّا null.
-- لا تنادَى إلّا من دوالّ القاعدة (مالكة): والسلّة الفارغة تحجب كلّ فترة، فمن يمرّر
-- «لا خدمات» يعني «لا تحكم» يمرّر null ولا ينادي هذه أصلًا.
create or replace function public.reserved_block(p_date date, p_service_ids uuid[])
returns text language sql stable
set search_path to 'public', 'pg_temp'
as $$
  select r.message
    from public.reserved_periods r
   where r.active
     and p_date = any(r.dates)
     and exists (select 1 from public.services s where s.id = any(r.service_ids))
     and not exists (select 1 from unnest(coalesce(p_service_ids, '{}'::uuid[])) c
                      where c = any(r.service_ids))
   limit 1;
$$;
revoke execute on function public.reserved_block(date, uuid[]) from public, anon, authenticated;

-- الأداة المشتركة بين الرقع أدناه: الموضع يُطلب مرّةً واحدة بالضبط.
create or replace function pg_temp.patch_once(p_src text, p_anchor text, p_repl text, p_what text)
returns text language plpgsql as $pf$
declare n int;
begin
  n := (length(p_src) - length(replace(p_src, p_anchor, ''))) / nullif(length(p_anchor), 0);
  if n is distinct from 1 then
    raise exception 'لم يُعثر على موضع % مرّةً واحدة (وُجد % مرّات)', p_what, n;
  end if;
  return replace(p_src, p_anchor, p_repl);
end $pf$;

-- available_slots: وسيطٌ رابع، واليوم لا يُفتح لسلّةٍ لا تناسب الفترة.
do $do$
declare v_src text; v_new text;
begin
  select pg_get_functiondef(p.oid) into v_src
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'available_slots'
     and pg_get_function_identity_arguments(p.oid) = 'p_date date, p_duration_min integer, p_exclude uuid';
  if v_src is null then
    if exists (select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
                where n.nspname = 'public' and p.proname = 'available_slots'
                  and pg_get_function_identity_arguments(p.oid) like '%p_service_ids uuid[]') then
      return;   -- طُبّق من قبل
    end if;
    raise exception 'available_slots غير موجودة بتوقيعها المعروف';
  end if;
  v_new := pg_temp.patch_once(v_src,
    $a$p_exclude uuid DEFAULT NULL::uuid)$a$,
    $b$p_exclude uuid DEFAULT NULL::uuid, p_service_ids uuid[] DEFAULT NULL::uuid[])$b$,
    'ترويسة available_slots');
  v_new := pg_temp.patch_once(v_new,
    $a$  if p_date > v_today + v_advance and not public.custom_day(p_date) then return; end if;
$a$,
    $b$  if p_date > v_today + v_advance and not public.custom_day(p_date) then return; end if;
  -- فترةٌ مخصّصة لخدمة (٠٠٤١): اليوم لا يُفتح لسلّةٍ لا تضمّ الخدمة المخصّصة.
  -- بلا خدماتٍ (null) لا حكم: تعمل الدالّة كما كانت.
  if p_service_ids is not null and public.reserved_block(p_date, p_service_ids) is not null then
    return;
  end if;
$b$,
    'شرط المدى في available_slots');
  drop function public.available_slots(date, integer, uuid);
  execute v_new;
end $do$;
revoke execute on function public.available_slots(date, integer, uuid, uuid[]) from public;
grant execute on function public.available_slots(date, integer, uuid, uuid[]) to anon, authenticated, service_role;

-- days_with_availability: لكلّ يومٍ هل هو «مخصّص» (كان سيُفتح لولا الفترة) ورسالته.
-- يُعلَّم «مخصّص» لا «مقفل»: المقفل (إجازة أو يوم راحة أو ممتلئ) يبقى باهتًا كما كان.
drop function if exists public.days_with_availability(date, integer, integer);
create or replace function public.days_with_availability(
  p_from date, p_days integer default 14, p_duration_min integer default null,
  p_service_ids uuid[] default null)
returns table(the_date date, slot_count integer, reserved boolean, reserved_msg text)
language plpgsql stable security definer
set search_path to 'public', 'pg_temp'
as $fn$
declare
  d date; i integer; v_msg text; v_base integer;
begin
  for i in 0 .. greatest(coalesce(p_days, 14), 1) - 1 loop
    d := p_from + i;
    the_date := d; reserved := false; reserved_msg := null;
    select count(*)::integer into slot_count
      from public.available_slots(d, p_duration_min, null, p_service_ids);
    if p_service_ids is not null and slot_count = 0 then
      v_msg := public.reserved_block(d, p_service_ids);
      if v_msg is not null then
        select count(*)::integer into v_base from public.available_slots(d, p_duration_min);
        if v_base > 0 then reserved := true; reserved_msg := v_msg; end if;
      end if;
    end if;
    return next;
  end loop;
end;
$fn$;
revoke execute on function public.days_with_availability(date, integer, integer, uuid[]) from public;
grant execute on function public.days_with_availability(date, integer, integer, uuid[]) to anon, authenticated, service_role;

-- create_booking: الحارس الأخير. بعد التحقّق من الخدمات وقبل الإيصال والفحص، فمن ردّته
-- الفترة تسمع رسالتها لا «الإيصال غير صحيح».
do $do$
declare v_src text; v_new text;
begin
  select pg_get_functiondef(p.oid) into v_src
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'create_booking'
     and pg_get_function_identity_arguments(p.oid) =
         'p_client_name text, p_client_phone text, p_date date, p_time time without time zone, p_service_ids uuid[], p_person_names text[], p_loc_text text, p_loc_map text, p_notes text, p_receipt_path text, p_lat numeric, p_lng numeric, p_client_v integer';
  if v_src is null then
    if exists (select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
                where n.nspname = 'public' and p.proname = 'create_booking'
                  and pg_get_function_identity_arguments(p.oid) like '%p_features integer') then
      return;   -- طُبّق من قبل
    end if;
    raise exception 'create_booking غير موجودة بتوقيعها المعروف';
  end if;
  v_new := pg_temp.patch_once(v_src,
    $a$p_client_v integer DEFAULT 1)$a$,
    $b$p_client_v integer DEFAULT 1, p_features integer DEFAULT 0)$b$,
    'ترويسة create_booking');
  v_new := pg_temp.patch_once(v_new,
    $a$  v_price numeric(10,2);
$a$,
    $b$  v_price numeric(10,2); v_rmsg text;
$b$,
    'تصريح المتغيّرات في create_booking');
  v_new := pg_temp.patch_once(v_new,
    $a$  v_people := array_length(p_service_ids, 1);
$a$,
    $b$  v_people := array_length(p_service_ids, 1);

  -- فترةٌ مخصّصة لخدمة (٠٠٤١): لا تُلزم إلّا صفحةً تقول إنها تعرفها (بتّ ١ في p_features)،
  -- وإلّا ضاع عربونٌ حُوّل بصفحةٍ لا ترى المنع. والرسالة رسالةُ إيمان نفسُها.
  if (coalesce(p_features, 0) & 1) = 1 then
    v_rmsg := public.reserved_block(p_date, p_service_ids);
    if v_rmsg is not null then
      raise exception '%', v_rmsg using errcode = 'P0001';
    end if;
  end if;
$b$,
    'ما بعد عدّ الخدمات في create_booking');
  drop function public.create_booking(text, text, date, time without time zone, uuid[], text[], text, text, text, text, numeric, numeric, integer);
  execute v_new;
end $do$;
grant execute on function public.create_booking(text, text, date, time without time zone, uuid[], text[], text, text, text, text, numeric, numeric, integer, integer)
  to anon, authenticated, service_role;

-- اللقطة والاستعادة: الجدول يدخل النسخة الاحتياطية (§٧ج).
do $do$
declare v_src text; v_new text;
begin
  select pg_get_functiondef(p.oid) into v_src from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'admin_snapshot';
  if v_src like '%reserved_periods%' then return; end if;    -- طُبّق من قبل
  v_new := pg_temp.patch_once(v_src,
    $a$    'client_history',       coalesce((select jsonb_agg(to_jsonb(x) order by x.booked_at) from public.client_history x), '[]'::jsonb),
$a$,
    $b$    'client_history',       coalesce((select jsonb_agg(to_jsonb(x) order by x.booked_at) from public.client_history x), '[]'::jsonb),
    'reserved_periods',     coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at) from public.reserved_periods x), '[]'::jsonb),
$b$,
    'مفتاح العميلات في اللقطة');
  v_new := pg_temp.patch_once(v_new,
    $a$    'client_history', jsonb_array_length(v->'client_history'),
$a$,
    $b$    'client_history', jsonb_array_length(v->'client_history'),
    'reserved_periods', jsonb_array_length(v->'reserved_periods'),
$b$,
    'عدّاد العميلات في اللقطة');
  execute v_new;

  select pg_get_functiondef(p.oid) into v_src from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'admin_restore_snapshot';
  v_new := pg_temp.patch_once(v_src,
    $a$  n_hg int := 0; n_hgd int := 0; n_hgp int := 0; n_ch int := 0;$a$,
    $b$  n_hg int := 0; n_hgd int := 0; n_hgp int := 0; n_ch int := 0; n_rp int := 0;$b$,
    'تصريح الاستعادة');
  v_new := pg_temp.patch_once(v_new,
    $a$  select count(*) into n_ch from ins;
$a$,
    $b$  select count(*) into n_ch from ins;

  -- الفترات المخصّصة: تعود الغائبة ولا تمسّ القائمة، وما يشارك يومًا مع فترةٍ قائمة
  -- يُتخطّى بدل أن يُسقط الاستعادة كلَّها (حكمٌ واحد لكلّ يوم).
  with src as (select * from jsonb_populate_recordset(null::public.reserved_periods,
                                 coalesce(p_data->'reserved_periods', '[]'::jsonb)))
  , ins as (insert into public.reserved_periods
            select s.* from src s
             where not exists (select 1 from public.reserved_periods o
                                where o.id = s.id or o.dates && s.dates)
            returning 1)
  select count(*) into n_rp from ins;
$b$,
    'كتلة العميلات في الاستعادة');
  v_new := pg_temp.patch_once(v_new,
    $a$'client_history', n_ch,$a$,
    $b$'client_history', n_ch, 'reserved_periods', n_rp,$b$,
    'سطر الحصيلة في الاستعادة');
  execute v_new;
end $do$;
grant execute on function public.admin_snapshot() to authenticated, service_role;
revoke all on function public.admin_restore_snapshot(jsonb, boolean) from public, anon;
grant execute on function public.admin_restore_snapshot(jsonb, boolean) to authenticated;
