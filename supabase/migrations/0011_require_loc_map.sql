-- رابط الموقع: إلزاميّ أو لا، بمفتاحٍ تقلبه صاحبة العمل.
--
-- الموقع النصّي وحده لا يكفي سائقًا يبحث عن بيتٍ في حيّ كبير، ورابط
-- الخرائط يحسم ذلك. لكنّ إلزامه على كل عميلة يصدّ من لا تعرف كيف تنسخه.
-- فالقرار لصاحبته: مفتاحٌ في الإعدادات، والافتراضي غير إلزاميّ كما كان.

alter table public.settings
  add column if not exists require_loc_map boolean not null default false;

-- الواجهة العامّة تقرأ المفتاح لتعرف كيف ترسم الحقل.
create or replace view public.public_settings as
  select business_name, tagline, timezone, slot_step_min, min_lead_hours,
         max_advance_days, whatsapp_phone, accepting_bookings, closed_message,
         deposit_rate, bank_name, iban, beneficiary_name,
         instagram_url, tiktok_url, group_discount_amount, require_loc_map
  from settings where id = 1;

drop function if exists public.get_public_settings();
create function public.get_public_settings()
returns table (
  business_name text, tagline text, timezone text, slot_step_min integer,
  min_lead_hours integer, max_advance_days integer, whatsapp_phone text,
  accepting_bookings boolean, closed_message text, deposit_rate numeric,
  bank_name text, iban text, beneficiary_name text,
  instagram_url text, tiktok_url text, group_discount_amount numeric,
  receipt_ocr_required boolean, require_loc_map boolean
)
language sql stable security definer set search_path to 'public', 'pg_temp'
as $$
  select s.business_name, s.tagline, s.timezone, s.slot_step_min,
         s.min_lead_hours, s.max_advance_days, s.whatsapp_phone,
         s.accepting_bookings, s.closed_message, s.deposit_rate,
         s.bank_name, s.iban, s.beneficiary_name,
         s.instagram_url, s.tiktok_url, s.group_discount_amount,
         s.receipt_ocr_required, s.require_loc_map
  from public.settings s where s.id = 1;
$$;

revoke all on function public.get_public_settings() from public;
grant execute on function public.get_public_settings() to anon, authenticated;

-- والخادم يفرضه أيضًا: المتصفّح يمنع الإرسال، والمُصِرّ يتجاوز المتصفّح.
-- الشرط على حجوزات الرابط وحدها؛ الحجز اليدويّ تُدخله صاحبته وقد لا يكون
-- بيدها رابط، فلا يصحّ أن يقف المفتاح في وجهها.
create or replace function public.bookings_require_map()
returns trigger language plpgsql security definer
set search_path to 'public', 'pg_temp' as $$
declare v_need boolean;
begin
  if new.source = 'client' then
    select require_loc_map into v_need from public.settings where id = 1;
    if coalesce(v_need, false)
       and nullif(btrim(coalesce(new.loc_map, '')), '') is null then
      raise exception 'رابط الموقع من خرائط قوقل مطلوب لتثبيت الموعد'
        using errcode = 'P0001';
    end if;
  end if;
  return new;
end $$;

drop trigger if exists bookings_require_map on public.bookings;
create trigger bookings_require_map
  before insert on public.bookings
  for each row execute function public.bookings_require_map();
