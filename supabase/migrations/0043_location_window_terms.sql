-- ٠٠٤٣ نافذة شرط الموقع بأقسامها (§٧د في CLAUDE.md).
--
-- اعتمد صاحب المشروع (٢٦ نوفمبر ٢٠٢٦) نافذةً جديدة لشرط الموقع: العنوان حيث العميلة، وتحته اسم
-- المجموعة إن اختلف، ثمّ قسمٌ لكلّ خدمةٍ في سلّتها وحدها — سعرها، وأقلّ عدد، وسقوط خصم المجموعات،
-- ورسمها (https://claude.ai/artifact/8z2NudVex6kNsvvexrWZfu). والصفحة تركّبها من الحقول كما قرّر
-- ٠٠٣٧، لكنّ الردّ كان ينقصه شيئان:
--
-- - **`group_name`**: اسم المجموعة كما سمّتها صاحبة العمل. كان الردّ يحمل معرّفها وحده.
-- - **`svc_terms`**: صفوف المجموعة كلُّها بخدمتها وسعرها ورسمها وإذن «تُقبل وحدها». كان الردّ يحمل
--   `prices` (ما له سعرٌ وحده — ٠٠٣٦: صفٌّ بلا سعر ليس تسعيرة) ومجموعَ الرسم وأسماءَ خدماته نصًّا،
--   فلا يُعرف أيُّ خدمةٍ عليها الرسم ولا أيُّها تُقبل وحدها. و`prices` باقٍ كما هو: منه تُسعَّر الصفحة.
--
-- متوافقٌ مع الصفحات القديمة: مفتاحان جديدان لا يقرؤهما من لا يعرفهما، ولا يتغيّر مفتاحٌ قائم ولا حكم.
-- و`create_booking` تنادي الدالّة وتقرأ منها ما كانت تقرأ.

create or replace function public.check_location(
  p_lat numeric, p_lng numeric, p_people integer default 1, p_preview boolean default false,
  p_service_ids uuid[] default null::uuid[])
returns jsonb
language plpgsql
stable security definer
set search_path to 'public', 'pg_temp'
as $function$
declare
  d public.districts%rowtype; grp public.hood_groups%rowtype; s public.settings%rowtype;
  v_people int := greatest(coalesce(p_people,1),1);
  v_reject boolean; v_min int; v_fee numeric; v_msg text; v_where text; v_gid uuid;
  v_prices jsonb := '[]'::jsonb; v_nodisc boolean := false;
  v_live boolean; v_svc numeric := 0; v_solo_on boolean := false; v_names text;
  v_gname text; v_terms jsonb := '[]'::jsonb;
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
    v_gname := grp.name;
    -- صفٌّ بلا سعر يحمل رسمًا أو استثناءً، فلا يُعدّ تسعيرة.
    select coalesce(jsonb_agg(jsonb_build_object('service_id',p.service_id,'price',p.price)
                              order by p.service_id) filter (where p.price is not null),
                    '[]'::jsonb)
      into v_prices from public.hood_group_prices p where p.group_id = grp.id;
    -- ونافذة الشرط تحتاج الصفوف كلَّها (٠٠٤٣): الرسم و«تُقبل وحدها» حكمُ خدمةٍ ولو بلا سعر.
    select coalesce(jsonb_agg(jsonb_build_object('service_id',p.service_id,'price',p.price,
                              'svc_fee',coalesce(p.svc_fee,0),'solo_ok',coalesce(p.solo_ok,false))
                              order by p.service_id), '[]'::jsonb)
      into v_terms from public.hood_group_prices p where p.group_id = grp.id;
  end if;

  if v_reject then
    return jsonb_build_object('state','reject','checked',true,'district',v_where,
      'district_id',d.id,'group_id',v_gid,'group_name',v_gname,
      'message',coalesce(nullif(btrim(v_msg),''),
                         'عذرًا، الخدمة غير متاحة حاليًا في هذا الموقع.'));
  end if;

  if v_min > 1 and v_people < v_min then
    -- الاستثناء قبل المنع: خدمةٌ موسومة «تُقبل وحدها» تمرّ.
    if not public.hood_solo_ok(v_gid, p_service_ids) then
      return jsonb_build_object('state','blocked','checked',true,'district',v_where,
        'district_id',d.id,'group_id',v_gid,'group_name',v_gname,'min_people',v_min,'fee',v_fee,
        'prices',v_prices,'svc_terms',v_terms,'no_group_discount',v_nodisc,
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
    -- ولا تُخاط هنا جملةُ الشرط: الصفحة تركّبها من الحقول فتُذكر البنود
    -- التي تخصّ ما اختارته هذه العميلة وحدها. ويبقى `message` لما كتبته
    -- صاحبة العمل بيدها إن كتبت.
    return jsonb_build_object('state','condition','checked',true,'district',v_where,
      'district_id',d.id,'group_id',v_gid,'group_name',v_gname,'min_people',v_min,'fee',v_fee,
      'prices',v_prices,'svc_terms',v_terms,'no_group_discount',v_nodisc,'solo',v_solo_on,
      'svc_fee',v_svc,'fee_services',v_names,
      'message',nullif(btrim(coalesce(v_msg,'')),''));
  end if;

  return jsonb_build_object('state','ok','checked',true,'district',v_where,
    'district_id',d.id,'group_id',v_gid,'group_name',v_gname,'prices',v_prices,
    'no_group_discount',v_nodisc,'min_people',v_min,'solo',v_solo_on,'svc_fee',v_svc);
end $function$;
