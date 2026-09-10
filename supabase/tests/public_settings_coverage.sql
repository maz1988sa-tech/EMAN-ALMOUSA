-- هل تردّ `get_public_settings` كلَّ ما تحتاجه صفحة العميلة؟
--
-- الدالّة تُعدِّد أعمدتها بالاسم، فعمودٌ يُضاف إلى جدول الإعدادات ولا
-- يُضاف إليها لا يصل الصفحة — والصفحة تقرؤه `undefined` فتتصرّف كأنّه
-- مُطفأ، صامتةً بلا خطأ. وقع مع `loc_check_enabled`: بقي فحص الموقع لا
-- يعمل على صفحة حجزٍ حقيقية ولا مرّة.
--
--   psql "$DB_URL" -f supabase/tests/public_settings_coverage.sql
--
-- والقائمة أدناه هي نفسها في `dev/mock-supabase.js` تحت
-- `PUBLIC_SETTING_KEYS` — فإن تباعدتا سقط أحد الفحصين.

do $do$
declare
  need text[] := array[
    'business_name','tagline','timezone','slot_step_min','min_lead_hours',
    'max_advance_days','whatsapp_phone','accepting_bookings','closed_message',
    'deposit_rate','bank_name','iban','beneficiary_name','instagram_url',
    'tiktok_url','group_discount_amount','receipt_ocr_required','require_loc_map',
    'show_closed_months','closed_month_word','loc_check_enabled'];
  got text[];
  missing text[];
  extra text[];
begin
  select coalesce(array_agg(a.attname::text order by a.attnum), '{}')
    into got
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    join lateral unnest(p.proargnames, p.proargmodes) with ordinality
         as a(attname, mode, attnum) on true
   where n.nspname = 'public' and p.proname = 'get_public_settings'
     and a.mode = 't';

  select coalesce(array_agg(x), '{}') into missing
    from unnest(need) x where not (x = any(got));
  select coalesce(array_agg(x), '{}') into extra
    from unnest(got) x where not (x = any(need));

  raise exception 'ROLLBACK_OK % — ناقص=[%] زائد=[%]',
    case when missing = '{}' and extra = '{}'
         then 'الدالّة تطابق ما تحتاجه الصفحة' else '✗ تباعُد' end,
    array_to_string(missing, ','), array_to_string(extra, ',');
end $do$;
