-- ٠٠٣٦ — الرسم على الخدمة لا على حال «وحدها».
--
-- في ٠٠٣٤ عُلّق المبلغ بشرط الاستثناء: لا يُحصَّل إلّا حين تمرّ العميلة
-- وحدها. وأوّل تجربةٍ حقيقية كشفت أنّ المقصود غير ذلك: «ميك اب عروس في
-- هذه الأحياء عليه ثلاثمائة» — سواء جاءت وحدها أو مع غيرها.
--
-- فالحقلان صارا مستقلَّين: `solo_ok` إذنُ مرورٍ من أقلّ العدد، و`svc_fee`
-- رسمٌ على الخدمة في هذه المجموعة يُحصَّل كلّما اختيرت. ورَبطُهما كان
-- يُخفي الرسم عن الحال الأشيع.
--
-- **ويُغني عن تعديل السعر.** كان الطريق الوحيد لجعل العروس ٢٣٠٠ في
-- العمارية هو كتابة ٢٣٠٠ في خانة السعر — فتُعرض ٢٣٠٠ رقمًا واحدًا لا
-- يفسّره شيء. والآن: السعر ٢٠٠٠ كما هو، و٣٠٠ بندٌ باسم الحيّ تحته.
-- وخانة السعر باقية لمن أراد تسعيرةً مختلفة حقًّا، لا فرقًا يُضاف.
--
-- **ويُجمع لا يُؤخذ أكبرُه.** كان في ٠٠٣٤ `max` لأنّه فُهم ثمنَ ذهاب،
-- والذهاب واحد. وهو الآن رسمٌ على الخدمة: عروسان في العمارية ٢٣٠٠ لكلٍّ
-- كما تقول صاحبة العمل، فيُجمع بعدد ما اختير.

alter table public.hood_group_prices rename column solo_fee to svc_fee;

alter table public.hood_group_prices drop constraint if exists hood_group_prices_solo_fee_ck;
alter table public.hood_group_prices drop constraint if exists hood_group_prices_svc_fee_ck;
alter table public.hood_group_prices
  add constraint hood_group_prices_svc_fee_ck check (svc_fee >= 0 and svc_fee <= 100000);

-- وصفٌّ يحمل رسمًا وحده صفٌّ ذو معنى، فيُقبل بلا سعرٍ وبلا استثناء.
alter table public.hood_group_prices drop constraint if exists hood_group_prices_not_empty_ck;
alter table public.hood_group_prices
  add constraint hood_group_prices_not_empty_ck
  check (price is not null or solo_ok or svc_fee > 0);

comment on column public.hood_group_prices.svc_fee is
  'رسمٌ يُضاف لكلّ مرّةٍ تُختار فيها هذه الخدمة في هذه المجموعة — بندٌ مستقلّ باسم الحيّ.';

-- الحقلان انفصلا، فدالّتاهما كذلك. وواحدةٌ تردّ رقمًا وشرطًا معًا كانت
-- ستُعيد التباس ٠٠٣٤ نفسه: صفرٌ لا يُدرى أهو «بلا رسم» أم «بلا استثناء».
drop function if exists public.hood_solo_fee(uuid, uuid[]);

create or replace function public.hood_solo_ok(p_group uuid, p_service_ids uuid[])
returns boolean language sql stable set search_path to 'public', 'pg_temp'
as $$
  select p_group is not null
     and p_service_ids is not null
     and array_length(p_service_ids, 1) is not null
     and not exists (
       select 1 from unnest(p_service_ids) as t(sid)
        where not exists (
          select 1 from public.hood_group_prices p
           where p.group_id = p_group and p.service_id = t.sid and p.solo_ok));
$$;
grant execute on function public.hood_solo_ok(uuid, uuid[]) to anon, authenticated, service_role;

-- يُجمع بعدد ما اختير: `unnest` يُبقي المكرّر، فعروسان رسمان.
create or replace function public.hood_svc_fee(p_group uuid, p_service_ids uuid[])
returns numeric language sql stable set search_path to 'public', 'pg_temp'
as $$
  select coalesce((
    select sum(p.svc_fee)
      from unnest(coalesce(p_service_ids, '{}'::uuid[])) as t(sid)
      join public.hood_group_prices p
        on p.group_id = p_group and p.service_id = t.sid), 0);
$$;
grant execute on function public.hood_svc_fee(uuid, uuid[]) to anon, authenticated, service_role;

-- والرسالة تُسمّي الخدمة. «أسعار الخدمات في هذا الموقع تختلف» جملةٌ صحيحة
-- ولا تقول شيئًا: العميلة لا تعرف أيَّ خدمةٍ ولا كم. وقعت في أوّل تجربة.
create or replace function public.check_location(
  p_lat numeric, p_lng numeric, p_people integer default 1,
  p_preview boolean default false, p_service_ids uuid[] default null
) returns jsonb
language plpgsql stable security definer
set search_path to 'public', 'pg_temp'
as $function$
declare
  d public.districts%rowtype; grp public.hood_groups%rowtype; s public.settings%rowtype;
  v_people int := greatest(coalesce(p_people,1),1);
  v_reject boolean; v_min int; v_fee numeric; v_msg text; v_where text; v_gid uuid;
  v_prices jsonb := '[]'::jsonb; v_nodisc boolean := false;
  v_live boolean; v_svc numeric := 0; v_solo_on boolean := false; v_names text;
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
    -- صفٌّ بلا سعر يحمل رسمًا أو استثناءً، فلا يُعدّ تسعيرة.
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
    -- الاستثناء قبل المنع: خدمةٌ موسومة «تُقبل وحدها» تمرّ.
    if not public.hood_solo_ok(v_gid, p_service_ids) then
      return jsonb_build_object('state','blocked','checked',true,'district',v_where,
        'district_id',d.id,'group_id',v_gid,'min_people',v_min,'fee',v_fee,'prices',v_prices,
        'no_group_discount',v_nodisc,
        'message',coalesce(nullif(btrim(v_msg),''),
          format('هذا الموقع يتطلّب حجزًا لـ %s أشخاص فأكثر.', v_min)));
    end if;
    v_solo_on := true;
  end if;

  -- الرسم على الخدمة: يُحسب في كلّ حال، لا في حال الاستثناء وحدها.
  v_svc := public.hood_svc_fee(v_gid, p_service_ids);
  if v_svc > 0 then
    v_fee := coalesce(v_fee,0) + v_svc;
    select string_agg(distinct sv.name, ' و') into v_names
      from unnest(p_service_ids) as t(sid)
      join public.services sv on sv.id = t.sid
     where exists (select 1 from public.hood_group_prices p
                    where p.group_id = v_gid and p.service_id = t.sid and p.svc_fee > 0);
    -- ورسالةُ المجموعة تصف حكمها العامّ، وهذه واقعةٌ بعينها بمبلغٍ بعينه.
    v_msg := format('%sرسوم إضافية %s ر.س في هذا الموقع — بندٌ مستقلّ يُدفع يوم الموعد ولا يدخل العربون.',
                    coalesce(v_names || ': ', ''),
                    trim(to_char(v_svc, 'FM999999990.99')));
  end if;

  if v_fee > 0 or jsonb_array_length(v_prices) > 0 or v_nodisc then
    return jsonb_build_object('state','condition','checked',true,'district',v_where,
      'district_id',d.id,'group_id',v_gid,'min_people',v_min,'fee',v_fee,'prices',v_prices,
      'no_group_discount',v_nodisc,'solo',v_solo_on,'svc_fee',v_svc,
      'message',coalesce(nullif(btrim(v_msg),''),
        case when jsonb_array_length(v_prices) > 0 then 'أسعار الخدمات في هذا الموقع تختلف.'
             when v_fee > 0 then 'على هذا الموقع رسوم مواصلات إضافية.'
             else 'على هذا الموقع شرط.' end));
  end if;

  return jsonb_build_object('state','ok','checked',true,'district',v_where,
    'district_id',d.id,'group_id',v_gid,'prices',v_prices,
    'no_group_discount',v_nodisc,'min_people',v_min,'solo',v_solo_on,'svc_fee',v_svc);
end $function$;

grant execute on function public.check_location(numeric, numeric, integer, boolean, uuid[])
  to anon, authenticated, service_role;

-- واللوحة تقرأ الاسم الجديد وتكتبه.
create or replace function public.admin_hood_groups()
returns jsonb language sql stable security definer
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
                            'solo_ok', p.solo_ok, 'svc_fee', p.svc_fee))
                            from public.hood_group_prices p where p.group_id = g.id), '[]'::jsonb))
      order by g.sort, g.created_at) from public.hood_groups g), '[]'::jsonb) end;
$function$;
grant execute on function public.admin_hood_groups() to authenticated, service_role;

do $do$
declare v_src text; v_new text;
begin
  select pg_get_functiondef(p.oid) into v_src
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'admin_save_hood_group';
  if v_src is null then raise exception 'admin_save_hood_group غير موجودة'; end if;

  v_new := replace(v_src,
    E'  insert into public.hood_group_prices (group_id, service_id, price, solo_ok, solo_fee)',
    E'  insert into public.hood_group_prices (group_id, service_id, price, solo_ok, svc_fee)');
  if v_new = v_src then raise exception 'لم يُعثر على سطر الإدراج'; end if;
  v_src := v_new;

  v_new := replace(v_src,
    E'         least(greatest(coalesce(nullif(x->>''solo_fee'','''')::numeric, 0), 0), 100000)',
    E'         least(greatest(coalesce(nullif(x->>''svc_fee'','''')::numeric, 0), 0), 100000)');
  if v_new = v_src then raise exception 'لم يُعثر على سطر المبلغ'; end if;
  v_src := v_new;

  -- وصفٌّ يحمل رسمًا وحده يُحفظ: كان الشرط على السعر أو الاستثناء، فرسمٌ
  -- بلا واحدٍ منهما كان يسقط صامتًا.
  v_new := replace(v_src,
    E'     and ((x->>''price'') ~ ''^[0-9]+(\\.[0-9]+)?$'' or coalesce((x->>''solo_ok'')::boolean, false))',
    E'     and ((x->>''price'') ~ ''^[0-9]+(\\.[0-9]+)?$'' or coalesce((x->>''solo_ok'')::boolean, false)\n'
     '          or coalesce(nullif(x->>''svc_fee'','''')::numeric, 0) > 0)');
  if v_new = v_src then raise exception 'لم يُعثر على شرط بقاء الصفّ'; end if;

  execute v_new;
end $do$;
grant execute on function public.admin_save_hood_group(jsonb) to authenticated, service_role;
