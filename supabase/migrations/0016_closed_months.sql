-- الشهر الذي لم يُفتح بعد: يُقال، لا يُترك فراغًا.
--
-- الحجز مفتوحٌ إلى مدى معيّن (max_advance_days). وما بعده كانت العميلة
-- تراه شبكةً فارغة بلا سبب، فتظنّ الخلل في الموقع لا في التقويم. والفرق
-- بين «لا شيء هنا» و«لم يُفتح بعد» هو الفرق بين من تنصرف ومن تنتظر.
--
-- والكلمة تختارها صاحبته: «غير مفتوحة» تَعِد بفتحٍ قادم، و«غير متاحة»
-- تُغلق البابَ أدبًا. فتُترك لها.

alter table public.settings
  add column if not exists show_closed_months boolean not null default true,
  add column if not exists closed_month_word  text    not null default 'غير مفتوحة';

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'settings_closed_word_ck') then
    alter table public.settings
      add constraint settings_closed_word_ck
      check (closed_month_word in ('غير مفتوحة', 'غير متاحة'));
  end if;
end $$;

drop function if exists public.get_public_settings();
create function public.get_public_settings()
returns table (
  business_name text, tagline text, timezone text, slot_step_min integer,
  min_lead_hours integer, max_advance_days integer, whatsapp_phone text,
  accepting_bookings boolean, closed_message text, deposit_rate numeric,
  bank_name text, iban text, beneficiary_name text,
  instagram_url text, tiktok_url text, group_discount_amount numeric,
  receipt_ocr_required boolean, require_loc_map boolean,
  show_closed_months boolean, closed_month_word text
)
language sql stable security definer set search_path to 'public', 'pg_temp'
as $$
  select s.business_name, s.tagline, s.timezone, s.slot_step_min,
         s.min_lead_hours, s.max_advance_days, s.whatsapp_phone,
         s.accepting_bookings, s.closed_message, s.deposit_rate,
         s.bank_name, s.iban, s.beneficiary_name,
         s.instagram_url, s.tiktok_url, s.group_discount_amount,
         s.receipt_ocr_required, s.require_loc_map,
         s.show_closed_months, s.closed_month_word
  from public.settings s where s.id = 1;
$$;

revoke all on function public.get_public_settings() from public;
grant execute on function public.get_public_settings() to anon, authenticated;
