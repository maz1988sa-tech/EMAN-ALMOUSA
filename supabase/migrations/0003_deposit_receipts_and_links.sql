-- ═══════════════════════════════════════════════════════════════════════
-- 0003 — العربون وإيصال التحويل وروابط التواصل
--
-- طُبِّق على القاعدة الحيّة في 2026-08-21. الملف مكتوب ليُعاد تشغيله بلا
-- ضرر على قاعدة طُبِّق عليها من قبل.
--
-- ثلاثة تغييرات مترابطة:
--   ١. العربون صار إعدادًا تملكه صاحبة العمل بدل رقم ضمني في قالب واتساب.
--   ٢. الحجز لا يُسجَّل بلا صورة تحويل مرفوعة فعلًا في مخزن خاص.
--   ٣. روابط إنستقرام وتيك توك انتقلت من الكود إلى الإعدادات.
-- ═══════════════════════════════════════════════════════════════════════

-- ── ١) أعمدة الإعدادات ────────────────────────────────────────────────
alter table public.settings
  add column if not exists deposit_rate     numeric(5,4) not null default 0.25,
  add column if not exists bank_name        text,
  add column if not exists iban             text,
  add column if not exists beneficiary_name text,
  add column if not exists instagram_url    text,
  add column if not exists tiktok_url       text;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'settings_deposit_rate_ck') then
    alter table public.settings
      add constraint settings_deposit_rate_ck check (deposit_rate >= 0 and deposit_rate <= 1);
  end if;
  -- الآيبان السعودي: SA ثم 22 رقمًا، مخزّن بلا مسافات.
  if not exists (select 1 from pg_constraint where conname = 'settings_iban_ck') then
    alter table public.settings
      add constraint settings_iban_ck check (iban is null or iban ~ '^SA[0-9]{22}$');
  end if;
  -- روابط https فقط: خانة الرابط ليست مكانًا لجافاسكربت مموّه.
  if not exists (select 1 from pg_constraint where conname = 'settings_instagram_ck') then
    alter table public.settings
      add constraint settings_instagram_ck check (instagram_url is null or instagram_url ~* '^https://[^\s]+$');
  end if;
  if not exists (select 1 from pg_constraint where conname = 'settings_tiktok_ck') then
    alter table public.settings
      add constraint settings_tiktok_ck check (tiktok_url is null or tiktok_url ~* '^https://[^\s]+$');
  end if;
end $$;

-- ── ٢) مسار الإيصال على الحجز ─────────────────────────────────────────
alter table public.bookings
  add column if not exists receipt_path text;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'bookings_receipt_path_ck') then
    alter table public.bookings
      add constraint bookings_receipt_path_ck
      check (receipt_path is null or receipt_path ~ '^pending/[0-9a-f-]{36}\.(jpg|jpeg|png|webp|heic|pdf)$');
  end if;
end $$;

-- ── ٣) مخزن الإيصالات ─────────────────────────────────────────────────
-- خاص: العميلة ترفع ولا تقرأ، وصاحبة اللوحة تقرأ برابط موقّع قصير العمر.
-- لو كان عامًّا لأمكن تخمين مسارات الأخريات، والإيصال يحمل اسمًا وحسابًا.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('receipts', 'receipts', false, 5242880,
        array['image/jpeg','image/png','image/webp','image/heic','image/heif','application/pdf'])
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "receipt upload by client"   on storage.objects;
drop policy if exists "receipt read by owner only" on storage.objects;
drop policy if exists "receipt cleanup by owner"   on storage.objects;

create policy "receipt upload by client"
  on storage.objects for insert to anon, authenticated
  with check (bucket_id = 'receipts' and name like 'pending/%');

create policy "receipt read by owner only"
  on storage.objects for select to authenticated
  using (bucket_id = 'receipts');

create policy "receipt cleanup by owner"
  on storage.objects for delete to authenticated
  using (bucket_id = 'receipts');

-- الرفع يسبق الحجز، فمن رفعت ثم تركت الصفحة تخلّف ملفًا بلا حجز.
-- Supabase يمنع الحذف المباشر من storage.objects (مشغّل protect_delete)،
-- فالقاعدة تسمّي اليتيم فقط، وتحذفه لوحة التحكم عبر واجهة التخزين عند فتحها.
create or replace function public.orphan_receipts(p_older_than interval default interval '1 day')
returns setof text
language sql stable security definer
set search_path = public, storage, pg_temp
as $$
  select o.name
    from storage.objects o
   where o.bucket_id = 'receipts'
     and o.created_at < now() - p_older_than
     and not exists (select 1 from public.bookings b where b.receipt_path = o.name)
   limit 200;
$$;

revoke execute on function public.orphan_receipts(interval) from public, anon;
grant  execute on function public.orphan_receipts(interval) to authenticated;

-- ── ٤) الإعدادات العامة تحمل بيانات التحويل والروابط ─────────────────
-- الآيبان حساب استقبال وعرضه للعميلة هو الغرض منه؛ جوال السائق يبقى
-- خارج العرض العام كما كان.
drop view if exists public.public_settings;

create view public.public_settings
with (security_invoker = off) as
  select business_name, tagline, timezone, slot_step_min,
         min_lead_hours, max_advance_days, whatsapp_phone,
         accepting_bookings, closed_message,
         deposit_rate, bank_name, iban, beneficiary_name,
         instagram_url, tiktok_url
  from public.settings
  where id = 1;

grant select on public.public_settings to anon, authenticated;

drop function if exists public.get_public_settings();

create function public.get_public_settings()
returns table (
  business_name      text,
  tagline            text,
  timezone           text,
  slot_step_min      integer,
  min_lead_hours     integer,
  max_advance_days   integer,
  whatsapp_phone     text,
  accepting_bookings boolean,
  closed_message     text,
  deposit_rate       numeric,
  bank_name          text,
  iban               text,
  beneficiary_name   text,
  instagram_url      text,
  tiktok_url         text
)
language sql stable security definer
set search_path = public, pg_temp
as $$
  select s.business_name, s.tagline, s.timezone,
         s.slot_step_min, s.min_lead_hours, s.max_advance_days,
         s.whatsapp_phone, s.accepting_bookings, s.closed_message,
         s.deposit_rate, s.bank_name, s.iban, s.beneficiary_name,
         s.instagram_url, s.tiktok_url
  from public.settings s
  where s.id = 1;
$$;

revoke execute on function public.get_public_settings() from public;
grant execute on function public.get_public_settings() to anon, authenticated;

-- ── ٥) صفحة المتابعة تطمئن العميلة أن الإيصال وصل ────────────────────
-- يُعاد وجود الإيصال لا مساره: المسار يخص اللوحة وحدها.
drop function if exists public.get_booking_by_token(uuid);

create function public.get_booking_by_token(p_token uuid)
returns table (
  ref text, client_name text, the_date date, start_time time,
  duration_min integer, status public.booking_status, price numeric,
  deposit numeric, loc_text text, client_notes text,
  cancel_requested boolean, created_at timestamptz,
  receipt_received boolean, items jsonb
)
language plpgsql stable security definer
set search_path = public, pg_temp
as $$
begin
  return query
    select b.ref, b.client_name, b.the_date, b.start_time, b.duration_min,
           b.status, b.price, b.deposit, b.loc_text, b.client_notes,
           b.cancel_requested, b.created_at,
           (b.receipt_path is not null) as receipt_received,
           coalesce((
             select jsonb_agg(jsonb_build_object(
                      'service_name', i.service_name,
                      'service_icon', i.service_icon,
                      'person_name',  i.person_name,
                      'price',        i.price,
                      'duration_min', i.duration_min
                    ) order by i.sort)
             from public.booking_items i where i.booking_id = b.id
           ), '[]'::jsonb)
    from public.bookings b
    where b.public_token = p_token;
end;
$$;

revoke execute on function public.get_booking_by_token(uuid) from public;
grant execute on function public.get_booking_by_token(uuid) to anon, authenticated;

-- ── ٦) الحجز لا يُسجَّل بلا إيصال ──────────────────────────────────────
-- المعامل الأخير له قيمة افتراضية فلا تنكسر النداءات القديمة ترجمةً،
-- لكنها تُرفض برسالة عربية مفهومة تظهر للعميلة كما هي.
drop function if exists public.create_booking(text, text, date, time, uuid[], text[], text, text, text);
drop function if exists public.create_booking(text, text, date, time, uuid[], text[], text, text, text, text);

create function public.create_booking(
  p_client_name  text,
  p_client_phone text,
  p_date         date,
  p_time         time,
  p_service_ids  uuid[],
  p_person_names text[] default null,
  p_loc_text     text default null,
  p_loc_map      text default null,
  p_notes        text default null,
  p_receipt_path text default null
)
returns table (ref text, public_token uuid, the_date date, start_time time, price numeric)
language plpgsql volatile security definer
set search_path = public, pg_temp
as $$
declare
  v_open      boolean;
  v_phone     text;
  v_name      text;
  v_receipt   text;
  v_dur       integer := 0;
  v_booking   public.bookings%rowtype;
  v_service   public.services%rowtype;
  v_id        uuid;
  i           integer;
begin
  select accepting_bookings into v_open from public.settings where id = 1;
  if not v_open then
    raise exception 'الحجز مغلق حاليًا' using errcode = 'P0001';
  end if;

  v_name := btrim(coalesce(p_client_name, ''));
  if length(v_name) < 2 or length(v_name) > 80 then
    raise exception 'الاسم غير صالح' using errcode = 'P0001';
  end if;

  v_phone := translate(coalesce(p_client_phone, ''), '٠١٢٣٤٥٦٧٨٩', '0123456789');
  v_phone := regexp_replace(v_phone, '[^0-9]', '', 'g');
  v_phone := regexp_replace(v_phone, '^00966', '', '');
  v_phone := regexp_replace(v_phone, '^966',   '', '');
  v_phone := regexp_replace(v_phone, '^0',     '', '');
  v_phone := '966' || v_phone;
  if v_phone !~ '^9665[0-9]{8}$' then
    raise exception 'رقم الجوال غير صالح' using errcode = 'P0001';
  end if;

  -- الإيصال شرط، ولا يكفي أن يرسل المتصفح نصًّا يشبه المسار.
  v_receipt := nullif(btrim(coalesce(p_receipt_path, '')), '');
  if v_receipt is null then
    raise exception 'يلزم إرفاق صورة تحويل العربون لتثبيت الموعد' using errcode = 'P0001';
  end if;
  if v_receipt !~ '^pending/[0-9a-f-]{36}\.(jpg|jpeg|png|webp|heic|pdf)$' then
    raise exception 'ملف الإيصال غير صالح' using errcode = 'P0001';
  end if;
  if not exists (select 1 from storage.objects o
                  where o.bucket_id = 'receipts' and o.name = v_receipt) then
    raise exception 'لم يصل ملف الإيصال، حاولي رفعه مرة أخرى' using errcode = 'P0001';
  end if;
  if exists (select 1 from public.bookings b where b.receipt_path = v_receipt) then
    raise exception 'ملف الإيصال مستخدم في حجز آخر' using errcode = 'P0001';
  end if;

  if p_service_ids is null or array_length(p_service_ids, 1) is null then
    raise exception 'يرجى اختيار خدمة واحدة على الأقل' using errcode = 'P0001';
  end if;
  if array_length(p_service_ids, 1) > 12 then
    raise exception 'عدد الخدمات كبير جدًا، تواصلي معنا مباشرة' using errcode = 'P0001';
  end if;

  for i in 1 .. array_length(p_service_ids, 1) loop
    select * into v_service from public.services
     where id = p_service_ids[i] and active and bookable_by_client;
    if not found then
      raise exception 'خدمة غير متاحة' using errcode = 'P0001';
    end if;
    v_dur := v_dur + v_service.duration_min;
  end loop;

  if not exists (select 1 from public.available_slots(p_date, v_dur) s where s.slot = p_time) then
    raise exception 'هذا الموعد لم يعد متاحًا، اختاري وقتًا آخر' using errcode = 'P0001';
  end if;

  insert into public.bookings (
    client_name, client_phone, the_date, start_time, duration_min,
    status, source, loc_text, loc_map, client_notes, receipt_path
  ) values (
    v_name, v_phone, p_date, p_time, greatest(v_dur, 15),
    'pending', 'client', nullif(btrim(coalesce(p_loc_text, '')), ''),
    nullif(btrim(coalesce(p_loc_map, '')), ''), nullif(btrim(coalesce(p_notes, '')), ''),
    v_receipt
  ) returning id into v_id;

  for i in 1 .. array_length(p_service_ids, 1) loop
    select * into v_service from public.services where id = p_service_ids[i];
    insert into public.booking_items (
      booking_id, service_id, service_name, service_icon, person_name,
      price, duration_min, sort
    ) values (
      v_id, v_service.id, v_service.name, v_service.icon,
      nullif(btrim(coalesce(p_person_names[i], '')), ''),
      v_service.price, v_service.duration_min, i
    );
  end loop;

  insert into public.activity_log (booking_id, actor, action, detail)
  values (v_id, 'client', 'created',
          jsonb_build_object('services', array_length(p_service_ids, 1), 'receipt', true));

  select * into v_booking from public.bookings where id = v_id;

  ref          := v_booking.ref;
  public_token := v_booking.public_token;
  the_date     := v_booking.the_date;
  start_time   := v_booking.start_time;
  price        := v_booking.price;
  return next;
end;
$$;

revoke execute on function public.create_booking(text, text, date, time, uuid[], text[], text, text, text, text) from public;
grant  execute on function public.create_booking(text, text, date, time, uuid[], text[], text, text, text, text) to anon, authenticated;
