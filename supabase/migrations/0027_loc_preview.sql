-- مُعاينةُ الحكم لصاحبة العمل — بلا إشعال الحارس على العميلات.
--
-- درسٌ من عطبٍ وقع: المفتاح `loc_check_enabled` مشترك بين المختبر والحيّ
-- لأنّ القاعدة واحدة. فأُشعل لتجربة الشروط، والصفحةُ الحيّة لا ترسل
-- إحداثيّات، فصار `create_booking` يرفض **كلّ** حجز. الطريق الوحيد
-- لتجربة شرطٍ كان إشعالَ حارسٍ على الناس.
--
-- فصارت المعاينة بابًا آخر: `p_preview` يتخطّى المفتاح **للحكم وحده**،
-- ولا يمسّ `create_booking` بشيء — الإلزام يبقى على المفتاح. ولا يفتحه
-- إلّا مديرٌ: `is_admin()` تُفحص هنا لا في المتصفّح.

create or replace function public.check_location(
  p_lat numeric, p_lng numeric, p_people integer default 1,
  p_preview boolean default false)
returns jsonb language plpgsql stable security definer
set search_path to 'public', 'pg_temp'
as $fn$
declare
  d public.districts%rowtype; grp public.hood_groups%rowtype; s public.settings%rowtype;
  v_people int := greatest(coalesce(p_people,1),1);
  v_reject boolean; v_min int; v_fee numeric; v_msg text; v_where text; v_gid uuid;
  v_prices jsonb := '[]'::jsonb;
  v_live boolean;
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
    /* لا تُسمَّ الأسماء المستعارة بحرفٍ يطابق متغيّرًا: `g` كان يعني
       الاثنين معًا فسقط الاستعلام بـ«ambiguous». */
    select hg.* into grp from public.hood_groups hg
      join public.hood_group_districts m on m.group_id = hg.id
     where m.district_id = d.id;
    if not found or not grp.active then
      return jsonb_build_object('state','ok','checked',true,'district',d.ar,'district_id',d.id);
    end if;
    v_gid := grp.id; v_reject := grp.reject; v_min := grp.min_people;
    v_fee := grp.fee_amount; v_msg := grp.message;
    select coalesce(jsonb_agg(jsonb_build_object('service_id',p.service_id,'price',p.price)),'[]'::jsonb)
      into v_prices from public.hood_group_prices p where p.group_id = grp.id;
  end if;

  if v_reject then
    return jsonb_build_object('state','reject','checked',true,'district',v_where,
      'district_id',d.id,'group_id',v_gid,
      'message',coalesce(nullif(btrim(v_msg),''),'لا نستقبل حجوزات في هذا الموقع حاليًا.'));
  end if;

  if v_min > 1 and v_people < v_min then
    return jsonb_build_object('state','blocked','checked',true,'district',v_where,
      'district_id',d.id,'group_id',v_gid,'min_people',v_min,'fee',v_fee,'prices',v_prices,
      'message',coalesce(nullif(btrim(v_msg),''),
        format('هذا الموقع يتطلّب حجزًا لـ %s أشخاص فأكثر.', v_min)));
  end if;

  if v_fee > 0 or v_min > 1 or jsonb_array_length(v_prices) > 0 then
    return jsonb_build_object('state','condition','checked',true,'district',v_where,
      'district_id',d.id,'group_id',v_gid,'min_people',v_min,'fee',v_fee,'prices',v_prices,
      'message',coalesce(nullif(btrim(v_msg),''),
        case when jsonb_array_length(v_prices) > 0 then 'أسعار الخدمات في هذا الموقع تختلف.'
             when v_fee > 0 then 'على هذا الموقع رسوم مواصلات إضافية.'
             else 'على هذا الموقع شرط.' end));
  end if;

  return jsonb_build_object('state','ok','checked',true,'district',v_where,'district_id',d.id);
end $fn$;

/* والقديمةُ ذاتُ الثلاثة تُسقط. لو بقيت لصار للاسم توقيعان، وPostgREST
   لا يفاضل بينهما فيردّ «تعذّر اختيار الأنسب». و`create_booking` تنادي
   بالموضع لا بالاسم، والوسيط الرابع له افتراض — فلا ينكسر شيء. */
drop function if exists public.check_location(numeric, numeric, integer);

grant execute on function public.check_location(numeric, numeric, integer, boolean)
  to anon, authenticated;
