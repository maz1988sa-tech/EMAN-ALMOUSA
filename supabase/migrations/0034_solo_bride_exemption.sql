-- ٠٠٣٤ — الحكم السادس: تُقبل وحدها، ومعها رسوم.
--
-- الأحكام الخمسة السابقة تصف الموقع كلَّه: رفض · أقلّ عدد · رسوم · تسعيرة
-- · سعرٌ صافٍ. وكلُّها تسري على كلّ خدمة سواء. وهذا لا يكفي لحال وقعت
-- فعلًا: العمارية «لشخصين فأكثر» — إلّا العروس، فصاحبة العمل تذهب إليها
-- وحدها بمقابلٍ إضافيّ.
--
-- فالاستثناء ليس على المجموعة بل على **الخدمة داخلها**: لكلّ خدمةٍ في
-- المجموعة صحُّ «تُقبل وحدها» ومبلغٌ يُضاف. وموضعُه هذا لا اسمُ الخدمة:
-- «العروس» تُعرف بالصفّ الذي وُضع فيه الصحّ، لا بمطابقة نصّ — والاسم
-- يتغيّر والمال لا يحتمل تخمينًا.
--
-- والمبلغ **بندٌ مستقلّ** لا سعرٌ مبيَّت: العميلة ترى ٢٠٠٠ للعروس ثمّ
-- «رسوم العمارية ٣٠٠» تحتها. ويسلك مسلكَ `loc_fee` القائم، فيُحصَّل يوم
-- الموعد ولا يدخل العربون — وهو حكمُ الرسوم منذ §٧د.

-- ١) العمودان. و`price` تصير اختيارية: خدمةٌ تُقبل وحدها بلا تعديل سعر
--    تحتاج صفًّا في الجدول ولا تحتاج سعرًا.
alter table public.hood_group_prices
  alter column price drop not null;

alter table public.hood_group_prices
  add column if not exists solo_ok  boolean       not null default false,
  add column if not exists solo_fee numeric(10,2) not null default 0;

alter table public.hood_group_prices
  drop constraint if exists hood_group_prices_solo_fee_ck;
alter table public.hood_group_prices
  add constraint hood_group_prices_solo_fee_ck
  check (solo_fee >= 0 and solo_fee <= 100000);

-- صفٌّ لا يحمل سعرًا ولا استثناءً لا معنى له، ووجودُه يُربك القراءة.
alter table public.hood_group_prices
  drop constraint if exists hood_group_prices_not_empty_ck;
alter table public.hood_group_prices
  add constraint hood_group_prices_not_empty_ck
  check (price is not null or solo_ok);

comment on column public.hood_group_prices.solo_ok is
  'تُقبل هذه الخدمة وحدها في هذه المجموعة ولو لم يبلغ العدد أقلَّ عددٍ مطلوب.';
comment on column public.hood_group_prices.solo_fee is
  'رسوم تُضاف بندًا مستقلًّا حين يمرّ الحجز بهذا الاستثناء وحده.';

-- ٢) حسابُ الاستثناء في موضعٍ واحد: تناديه دالّة العرض ودالّة الحجز
--    فلا يتباعد الحكمان (§٩).
--
--    يردّ `null` إذا لم ينطبق — أي إن كانت خدمةٌ واحدة من المختارات لا
--    تُقبل وحدها. ولو ردّ صفرًا لالتبس «لا استثناء» بـ«استثناءٌ بلا رسوم».
--
--    والرسوم **أكبرُ مبلغ لا مجموعُه**: هي ثمن ذهابٍ إلى الموقع، والذهاب
--    واحد. جمعُها يحاسب العميلة على الطريق مرّتين.
create or replace function public.hood_solo_fee(p_group uuid, p_service_ids uuid[])
returns numeric
language sql
stable
set search_path to 'public', 'pg_temp'
as $$
  select case
    when p_group is null
      or p_service_ids is null
      or array_length(p_service_ids, 1) is null then null
    when exists (
      select 1 from unnest(p_service_ids) as t(sid)
       where not exists (
         select 1 from public.hood_group_prices p
          where p.group_id = p_group and p.service_id = t.sid and p.solo_ok)
    ) then null
    else coalesce((
      select max(p.solo_fee) from public.hood_group_prices p
       where p.group_id = p_group
         and p.service_id = any(p_service_ids)), 0)
  end;
$$;

grant execute on function public.hood_solo_fee(uuid, uuid[]) to anon, authenticated, service_role;

-- ٣) `check_location` تعرف الآن ما اختارت العميلة.
--    إضافةُ وسيطٍ بقيمةٍ افتراضية تصنع حِملًا زائدًا (overload) فتلتبس على
--    PostgREST — فالقديمة تُسقط أوّلًا ثمّ تُمنح الصلاحيات من جديد (§٤).
drop function if exists public.check_location(numeric, numeric, integer, boolean);

create or replace function public.check_location(
  p_lat numeric, p_lng numeric,
  p_people integer default 1,
  p_preview boolean default false,
  p_service_ids uuid[] default null
) returns jsonb
language plpgsql
stable
security definer
set search_path to 'public', 'pg_temp'
as $function$
declare
  d public.districts%rowtype; grp public.hood_groups%rowtype; s public.settings%rowtype;
  v_people int := greatest(coalesce(p_people,1),1);
  v_reject boolean; v_min int; v_fee numeric; v_msg text; v_where text; v_gid uuid;
  v_prices jsonb := '[]'::jsonb; v_nodisc boolean := false;
  v_live boolean; v_solo numeric; v_solo_on boolean := false;
begin
  select * into s from public.settings where id = 1;

  -- المعاينة صلاحيةُ مديرٍ لا وسمٌ يرسله المتصفّح.
  v_live := coalesce(s.loc_check_enabled, false)
            or (coalesce(p_preview, false) and public.is_admin());

  if not v_live or p_lat is null or p_lng is null then
    return jsonb_build_object('state','ok','checked',false);
  end if;

  select * into d from public.district_at(p_lat, p_lng);

  if d.id is null then
    v_where := 'خارج الأحياء المعروفة';
    v_reject := coalesce(s.outside_reject,true); v_min := coalesce(s.outside_min,0);
    v_fee := coalesce(s.outside_fee,0); v_msg := s.outside_message;
  else
    v_where := d.ar;
    select hg.* into grp from public.hood_groups hg
      join public.hood_group_districts m on m.group_id = hg.id
     where m.district_id = d.id;
    if not found or not grp.active then
      return jsonb_build_object('state','ok','checked',true,'district',d.ar,'district_id',d.id);
    end if;
    v_gid := grp.id; v_reject := grp.reject; v_min := grp.min_people;
    v_fee := grp.fee_amount; v_msg := grp.message;
    v_nodisc := coalesce(grp.no_group_discount, false);
    select coalesce(jsonb_agg(jsonb_build_object('service_id',p.service_id,'price',p.price)
                              order by p.service_id) filter (where p.price is not null),
                    '[]'::jsonb)
      into v_prices from public.hood_group_prices p where p.group_id = grp.id;
  end if;

  if v_reject then
    return jsonb_build_object('state','reject','checked',true,'district',v_where,
      'district_id',d.id,'group_id',v_gid,
      'message',coalesce(nullif(btrim(v_msg),''),'لا نستقبل حجوزات في هذا الموقع حاليًا.'));
  end if;

  if v_min > 1 and v_people < v_min then
    -- الاستثناء قبل المنع: خدمةٌ موسومة «تُقبل وحدها» تمرّ ومعها رسومها.
    v_solo := public.hood_solo_fee(v_gid, p_service_ids);
    if v_solo is null then
      return jsonb_build_object('state','blocked','checked',true,'district',v_where,
        'district_id',d.id,'group_id',v_gid,'min_people',v_min,'fee',v_fee,'prices',v_prices,
        'no_group_discount',v_nodisc,
        'message',coalesce(nullif(btrim(v_msg),''),
          format('هذا الموقع يتطلّب حجزًا لـ %s أشخاص فأكثر.', v_min)));
    end if;
    v_solo_on := true;
    v_fee := coalesce(v_fee,0) + v_solo;
    -- ورسالةُ المجموعة تصف الحكم العامّ («لشخصين فأكثر»)، وهذه حالُ
    -- استثنائه — فتُقال جملتُها هي لا جملتُه.
    v_msg := case when v_solo > 0
      then format('يُطبَّق مبلغ %s ر.س رسوم الخدمة في %s.',
                  trim(to_char(v_solo, 'FM999999990.99')), v_where)
      else null end;
  end if;

  if v_fee > 0 or jsonb_array_length(v_prices) > 0 or v_nodisc then
    return jsonb_build_object('state','condition','checked',true,'district',v_where,
      'district_id',d.id,'group_id',v_gid,'min_people',v_min,'fee',v_fee,'prices',v_prices,
      'no_group_discount',v_nodisc,'solo',v_solo_on,
      'message',coalesce(nullif(btrim(v_msg),''),
        case when jsonb_array_length(v_prices) > 0 then 'أسعار الخدمات في هذا الموقع تختلف.'
             when v_fee > 0 then 'على هذا الموقع رسوم مواصلات إضافية.'
             else 'على هذا الموقع شرط.' end));
  end if;

  return jsonb_build_object('state','ok','checked',true,'district',v_where,
    'district_id',d.id,'group_id',v_gid,'prices',v_prices,
    'no_group_discount',v_nodisc,'min_people',v_min,'solo',v_solo_on);
end $function$;

grant execute on function public.check_location(numeric, numeric, integer, boolean, uuid[])
  to anon, authenticated, service_role;

-- ٤) `create_booking` تُعيد الحكم من الخدمات الفعليّة — الحارس الأخير.
--    بدون تمرير المعرّفات كانت تردّ العروسَ الواحدة `blocked` وقد قبلتها
--    الصفحة، فينكسر الحجز عند الإرسال وقد حوّلت العربون.
--
--    والتعديل سطران في دالّةٍ من مئة سطر، فيُشتقّ من تعريفها القائم لا
--    يُعاد كتابتُه: نسخةٌ تُكتب باليد تتباعد عن أصلها في أوّل ترحيلٍ يُنسى.
do $do$
declare v_src text; v_new text;
begin
  select pg_get_functiondef(p.oid) into v_src
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'create_booking';
  if v_src is null then raise exception 'create_booking غير موجودة'; end if;

  v_new := replace(v_src,
    'v_loc := public.check_location(p_lat, p_lng, v_people);',
    'v_loc := public.check_location(p_lat, p_lng, v_people, false, p_service_ids);');
  if v_new = v_src then raise exception 'لم يُعثر على نداء check_location داخل create_booking'; end if;

  v_src := v_new;
  v_new := replace(v_src,
    '''hood_group'', v_gid, ''loc_skipped''',
    '''hood_group'', v_gid, ''loc_solo'', coalesce((v_loc->>''solo'')::boolean, false), ''loc_skipped''');
  if v_new = v_src then raise exception 'لم يُعثر على سطر السجلّ داخل create_booking'; end if;

  execute v_new;
end $do$;

-- ٥) اللوحة: تقرأ العمودين وتكتبهما.
create or replace function public.admin_hood_groups()
returns jsonb
language sql
stable
security definer
set search_path to 'public', 'pg_temp'
as $function$
  select case when not public.is_admin() then '[]'::jsonb else
    coalesce((select jsonb_agg(jsonb_build_object(
      'id', g.id, 'name', g.name, 'sort', g.sort, 'active', g.active,
      'reject', g.reject, 'min_people', g.min_people, 'fee_amount', g.fee_amount,
      'message', g.message, 'no_group_discount', g.no_group_discount,
      'districts', coalesce((select jsonb_agg(m.district_id order by m.district_id)
                               from public.hood_group_districts m where m.group_id = g.id), '[]'::jsonb),
      'prices', coalesce((select jsonb_agg(jsonb_build_object(
                            'service_id', p.service_id, 'price', p.price,
                            'solo_ok', p.solo_ok, 'solo_fee', p.solo_fee))
                            from public.hood_group_prices p where p.group_id = g.id), '[]'::jsonb))
      order by g.sort, g.created_at) from public.hood_groups g), '[]'::jsonb) end;
$function$;

grant execute on function public.admin_hood_groups() to authenticated, service_role;

create or replace function public.admin_save_hood_group(p_group jsonb)
returns uuid
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $function$
declare v_id uuid; v_ids bigint[]; v_taken text;
begin
  if not public.is_admin() then
    raise exception 'not authorised' using errcode = '42501';
  end if;
  if btrim(coalesce(p_group->>'name','')) = '' then
    raise exception 'اكتبي اسمًا للمجموعة' using errcode = 'P0001';
  end if;

  v_id := nullif(p_group->>'id','')::uuid;
  select coalesce(array_agg((x)::bigint), '{}')
    into v_ids from jsonb_array_elements_text(coalesce(p_group->'districts','[]'::jsonb)) x;

  select string_agg(d.ar, '، ') into v_taken
    from public.hood_group_districts m join public.districts d on d.id = m.district_id
   where m.district_id = any(v_ids) and (v_id is null or m.group_id <> v_id);
  if v_taken is not null then
    raise exception 'هذه الأحياء في مجموعة أخرى: %', v_taken using errcode = 'P0001';
  end if;

  if v_id is null then
    insert into public.hood_groups (name, sort, active, reject, min_people, fee_amount, message, no_group_discount)
    values (btrim(p_group->>'name'),
            coalesce((p_group->>'sort')::smallint, 0),
            coalesce((p_group->>'active')::boolean, true),
            coalesce((p_group->>'reject')::boolean, false),
            least(greatest(coalesce((p_group->>'min_people')::int, 0), 0), 12),
            least(greatest(coalesce((p_group->>'fee_amount')::numeric, 0), 0), 100000),
            nullif(btrim(coalesce(p_group->>'message','')), ''),
            coalesce((p_group->>'no_group_discount')::boolean, false))
    returning id into v_id;
  else
    update public.hood_groups set
      name = btrim(p_group->>'name'),
      sort = coalesce((p_group->>'sort')::smallint, sort),
      active = coalesce((p_group->>'active')::boolean, active),
      reject = coalesce((p_group->>'reject')::boolean, false),
      min_people = least(greatest(coalesce((p_group->>'min_people')::int, 0), 0), 12),
      fee_amount = least(greatest(coalesce((p_group->>'fee_amount')::numeric, 0), 0), 100000),
      message = nullif(btrim(coalesce(p_group->>'message','')), ''),
      no_group_discount = coalesce((p_group->>'no_group_discount')::boolean, false),
      updated_at = now()
     where id = v_id;
    if not found then raise exception 'المجموعة غير موجودة' using errcode = 'P0001'; end if;
  end if;

  delete from public.hood_group_districts where group_id = v_id;
  insert into public.hood_group_districts (district_id, group_id)
  select unnest(v_ids), v_id
  on conflict (district_id) do update set group_id = excluded.group_id;

  -- صفُّ الخدمة يبقى إن حمل سعرًا **أو** استثناءً. وكان الشرط على السعر
  -- وحده، فخدمةٌ تُقبل وحدها بلا تعديل سعر كانت تسقط صامتة.
  delete from public.hood_group_prices where group_id = v_id;
  insert into public.hood_group_prices (group_id, service_id, price, solo_ok, solo_fee)
  select v_id, (x->>'service_id')::uuid,
         case when (x->>'price') ~ '^[0-9]+(\.[0-9]+)?$' then (x->>'price')::numeric end,
         coalesce((x->>'solo_ok')::boolean, false),
         least(greatest(coalesce(nullif(x->>'solo_fee','')::numeric, 0), 0), 100000)
    from jsonb_array_elements(coalesce(p_group->'prices','[]'::jsonb)) x
   where (x->>'service_id') ~ '^[0-9a-f-]{36}$'
     and ((x->>'price') ~ '^[0-9]+(\.[0-9]+)?$' or coalesce((x->>'solo_ok')::boolean, false))
     and exists (select 1 from public.services s where s.id = (x->>'service_id')::uuid);

  return v_id;
end $function$;

grant execute on function public.admin_save_hood_group(jsonb) to authenticated, service_role;
