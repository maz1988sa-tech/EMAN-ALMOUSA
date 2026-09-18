-- ٠٠٣٧ — النافذة تُقال لا تُشرح.
--
-- العميلة في منتصف الحجز، والنافذة تعترضها. فجملةٌ واحدة تكفي، وما
-- زاد — «بندٌ مستقلّ»، «لا يدخل العربون» — شرحُ محاسبةٍ في غير موضعه؛
-- موضعُه الملخّص، وهو أمامها بعد سطرين.
--
-- **وتوليد الجملة انتقل إلى الصفحة.** الرسالة صارت شرطيّة: الرسم يُذكر
-- إن اختيرت الخدمة التي عليه، وسقوطُ الخصم إن كان سيقع خصمٌ أصلًا. وذلك
-- تركيبُ عرضٍ من حقولٍ تعرفها الصفحة (`svc_fee`، `no_group_discount`،
-- `min_people`)، لا نصٌّ يُخيَّط في القاعدة. فالقاعدة تردّ الحقول، وتبقى
-- تردّ جملةً واحدة للحالتين اللتين تُقالان من الخادم: الرفض والمنع —
-- لأنّ `create_booking` ترفع بهما استثناءً نصُّه ما يصل العميلة.

-- جملةُ الحدّ الأدنى في موضعٍ واحد: تُقال من القاعدة عند المنع، ومن
-- الصفحة عند العرض — والعربية تُثنّي فـ«٢ أشخاص» ركيك و«شخصين» صواب.
create or replace function public.min_people_line(p_min integer)
returns text language sql immutable
as $$
  select format('الخدمة متاحة في هذا الموقع للحجوزات من %s فأكثر.',
    case when p_min = 2 then 'شخصين' else p_min || ' أشخاص' end);
$$;
grant execute on function public.min_people_line(integer) to anon, authenticated, service_role;

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
      'message',coalesce(nullif(btrim(v_msg),''),
                         'عذرًا، الخدمة غير متاحة حاليًا في هذا الموقع.'));
  end if;

  if v_min > 1 and v_people < v_min then
    -- الاستثناء قبل المنع: خدمةٌ موسومة «تُقبل وحدها» تمرّ.
    if not public.hood_solo_ok(v_gid, p_service_ids) then
      return jsonb_build_object('state','blocked','checked',true,'district',v_where,
        'district_id',d.id,'group_id',v_gid,'min_people',v_min,'fee',v_fee,'prices',v_prices,
        'no_group_discount',v_nodisc,
        'message',coalesce(nullif(btrim(v_msg),''), public.min_people_line(v_min)));
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
  end if;

  if v_fee > 0 or jsonb_array_length(v_prices) > 0 or v_nodisc then
    -- ولا تُخاط هنا جملةُ الشرط: الصفحة تركّبها من الحقول، فتُذكر البنود
    -- التي تخصّ ما اختارته هذه العميلة وحدها. ويبقى `message` لما كتبته
    -- صاحبة العمل بيدها إن كتبت.
    return jsonb_build_object('state','condition','checked',true,'district',v_where,
      'district_id',d.id,'group_id',v_gid,'min_people',v_min,'fee',v_fee,'prices',v_prices,
      'no_group_discount',v_nodisc,'solo',v_solo_on,'svc_fee',v_svc,
      'fee_services',v_names,
      'message',nullif(btrim(coalesce(v_msg,'')),''));
  end if;

  return jsonb_build_object('state','ok','checked',true,'district',v_where,
    'district_id',d.id,'group_id',v_gid,'prices',v_prices,
    'no_group_discount',v_nodisc,'min_people',v_min,'solo',v_solo_on,'svc_fee',v_svc);
end $function$;

grant execute on function public.check_location(numeric, numeric, integer, boolean, uuid[])
  to anon, authenticated, service_role;
