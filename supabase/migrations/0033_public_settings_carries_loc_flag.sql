-- مفتاحُ فحص الموقع لم يكن يصل صفحة العميلة أصلًا.
--
-- الصفحة تقرأ إعداداتها من `get_public_settings`، وهي دالّةٌ تُعدِّد
-- أعمدتها بالاسم. وأُضيف `loc_check_enabled` إلى جدول الإعدادات ولم
-- يُضف إليها — فكان `state.settings.loc_check_enabled` عند العميلة
-- **غيرَ معرَّف دائمًا**، و`runLocCheck` تخرج من أوّل سطر.
--
-- أي أنّ فحص الموقع لم يعمل على صفحة حجزٍ حقيقية ولا مرّة، مهما أُشعل
-- المفتاح. والحكم في `create_booking` كان يعمل — فلو أُشعل المفتاح
-- ورُقّيت الصفحة لرُدّت العميلة عند الإرسال بلا نافذةٍ سبقتها.
--
-- ولم تكشفه الطُّقُم لأنّ محاكي التطوير كان يردّ جدول الإعدادات كلَّه،
-- والدالّة تردّ أعمدةً معدودة — فعاشت الميزة في الطُّقُم ولم تعمل عند
-- أحد. وهذا عطبٌ سبق بصيغةٍ أخرى: «محاكٍ يكذب يُعطّل التغطية بصمت».
-- فصار المحاكي يُسقط على قائمة أعمدة الدالّة، ويحرس التطابقَ فحصان:
-- `tests/check_pubset.py` و`supabase/tests/public_settings_coverage.sql`.
--
-- وإضافةُ عمودٍ إلى `returns table` تستلزم إسقاط الدالّة وإنشاءها،
-- والإسقاط يمحو الصلاحيات — فتُعاد.

drop function if exists public.get_public_settings();

create function public.get_public_settings()
returns table(business_name text, tagline text, timezone text, slot_step_min integer,
              min_lead_hours integer, max_advance_days integer, whatsapp_phone text,
              accepting_bookings boolean, closed_message text, deposit_rate numeric,
              bank_name text, iban text, beneficiary_name text, instagram_url text,
              tiktok_url text, group_discount_amount numeric, receipt_ocr_required boolean,
              require_loc_map boolean, show_closed_months boolean, closed_month_word text,
              loc_check_enabled boolean)
language sql stable security definer set search_path to 'public', 'pg_temp'
as $fn$
  select s.business_name, s.tagline, s.timezone, s.slot_step_min,
         s.min_lead_hours, s.max_advance_days, s.whatsapp_phone,
         s.accepting_bookings, s.closed_message, s.deposit_rate,
         s.bank_name, s.iban, s.beneficiary_name,
         s.instagram_url, s.tiktok_url, s.group_discount_amount,
         s.receipt_ocr_required, s.require_loc_map,
         s.show_closed_months, s.closed_month_word,
         coalesce(s.loc_check_enabled, false)
  from public.settings s where s.id = 1;
$fn$;

grant execute on function public.get_public_settings() to anon, authenticated, service_role;
