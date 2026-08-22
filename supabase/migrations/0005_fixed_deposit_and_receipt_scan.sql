-- 0005 — العربون مبلغ ثابت لكل خدمة، وفحص إيصال التحويل قبل تسجيل الحجز.
--
-- ١) العربون: كان نسبة واحدة من الإجمالي في الإعدادات. صار مبلغًا ثابتًا
--    تضعه صاحبة العمل بجانب كل خدمة، ويُجمع على عناصر الحجز — عنصر لكل
--    شخص — فيكبر العربون بكبر الحجز كما يكبر السعر.
--    عمود settings.deposit_rate يبقى في مكانه ولا يُستعمل، لئلا تنكسر
--    نسخة قديمة من الواجهة لم تُحدَّث بعد.
--
-- ٢) الفحص: تُقرأ صورة الإيصال في دالّة حافّة وتُسجَّل الأرقام والكلمات
--    التي رُئيت فيها. الحكم هنا لا هناك: المتصفّح لا يُصدَّق في مبلغ،
--    والعربون المطلوب يُحسب من قاعدة البيانات لحظة الحجز.
--    الحارس يبقى مطفأً حتى تُقلب settings.receipt_ocr_required.

-- ── ١. العربون الثابت ────────────────────────────────────────────────
alter table public.services
  add column if not exists deposit_amount numeric(10,2) not null default 0;

alter table public.booking_items
  add column if not exists deposit_amount numeric(10,2) not null default 0;

alter table public.bookings
  add column if not exists deposit_due numeric(10,2) not null default 0;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'services_deposit_ck') then
    alter table public.services
      add constraint services_deposit_ck
      check (deposit_amount >= 0 and deposit_amount <= price);
  end if;
end $$;

-- ── ٢. حارس الإيصال ──────────────────────────────────────────────────
alter table public.settings
  add column if not exists receipt_ocr_required boolean not null default false;

create table if not exists public.receipt_scans (
  path        text primary key,
  numbers     numeric[]   not null default '{}',   -- المبالغ الأقرب (بجانبها عملة أو كسور)
  all_numbers numeric[]   not null default '{}',   -- كل رقم صالح رُئي
  keywords    text[]      not null default '{}',
  text_len    integer     not null default 0,
  engine      text        not null default 'none',
  scanned_at  timestamptz not null default now()
);

alter table public.receipt_scans enable row level security;
-- بلا سياسات: لا يقرؤه ولا يكتبه أحد عبر الواجهة العامّة. الدالّة الحافّة
-- تكتب بمفتاح الخدمة، و create_booking تقرأ لأنها SECURITY DEFINER.

-- ── ٣. إعادة الحساب تشمل العربون ─────────────────────────────────────
create or replace function public.recalc_booking(p_booking_id uuid)
returns void
language plpgsql
set search_path to 'public', 'pg_temp'
as $function$
declare
  v_total numeric(10,2);
  v_dur   integer;
  v_disc  numeric(10,2);
  v_dep   numeric(10,2);
begin
  select coalesce(sum(price), 0), coalesce(sum(duration_min), 0),
         coalesce(sum(deposit_amount), 0)
    into v_total, v_dur, v_dep
  from public.booking_items
  where booking_id = p_booking_id;

  v_disc := coalesce(public.group_discount_for(p_booking_id), 0);

  update public.bookings
     set items_total  = v_total,
         discount     = least(v_disc, v_total),
         duration_min = greatest(v_dur, 15),
         -- العربون لا يتجاوز المستحقّ بعد الخصم
         deposit_due  = least(v_dep, greatest(v_total - least(v_disc, v_total), 0))
   where id = p_booking_id;
end;
$function$;

-- ── ٤. الإعدادات العامّة تُبلّغ الواجهة بحالة الحارس ──────────────────
drop function if exists public.get_public_settings();
create or replace function public.get_public_settings()
returns table(business_name text, tagline text, timezone text, slot_step_min integer,
              min_lead_hours integer, max_advance_days integer, whatsapp_phone text,
              accepting_bookings boolean, closed_message text, deposit_rate numeric,
              bank_name text, iban text, beneficiary_name text, instagram_url text,
              tiktok_url text, group_discount_amount numeric, receipt_ocr_required boolean)
language sql
stable security definer
set search_path to 'public', 'pg_temp'
as $function$
  select s.business_name, s.tagline, s.timezone, s.slot_step_min,
         s.min_lead_hours, s.max_advance_days, s.whatsapp_phone,
         s.accepting_bookings, s.closed_message, s.deposit_rate,
         s.bank_name, s.iban, s.beneficiary_name,
         s.instagram_url, s.tiktok_url, s.group_discount_amount,
         s.receipt_ocr_required
  from public.settings s where s.id = 1;
$function$;

revoke execute on function public.get_public_settings() from public;
grant  execute on function public.get_public_settings() to anon, authenticated;

-- ── ٥. تسجيل الحجز: عربون مجموع، وحارس إيصال ────────────────────────
create or replace function public.create_booking(
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
) returns table(ref text, public_token uuid, the_date date,
                start_time time, price numeric)
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $function$
declare
  v_open      boolean;
  v_phone     text;
  v_name      text;
  v_receipt   text;
  v_rate      numeric;          -- مبلغ خصم المجموعة للشخص الواحد
  v_guard     boolean;
  v_dur       integer := 0;
  v_total     numeric(10,2) := 0;
  v_dep       numeric(10,2) := 0;
  v_grp       integer := 0;
  v_disc      numeric(10,2) := 0;
  v_need      numeric(10,2);
  v_scan      public.receipt_scans%rowtype;
  v_booking   public.bookings%rowtype;
  v_service   public.services%rowtype;
  v_id        uuid;
  i           integer;
begin
  select accepting_bookings, group_discount_amount, receipt_ocr_required
    into v_open, v_rate, v_guard
    from public.settings where id = 1;
  if not v_open then
    raise exception 'الحجز مغلق حاليًا' using errcode = 'P0001';
  end if;

  v_name := btrim(coalesce(p_client_name, ''));
  if length(v_name) < 2 or length(v_name) > 80 then
    raise exception 'الاسم غير صالح' using errcode = 'P0001';
  end if;

  v_phone := translate(coalesce(p_client_phone, ''), '٠١٢٣٤٥٦٧٨٩', '0123456789');
  v_phone := translate(v_phone, '۰۱۲۳۴۵۶۷۸۹', '0123456789');
  v_phone := regexp_replace(v_phone, '[^0-9]', '', 'g');
  v_phone := regexp_replace(v_phone, '^00966', '', '');
  v_phone := regexp_replace(v_phone, '^966',   '', '');
  v_phone := regexp_replace(v_phone, '^0',     '', '');
  v_phone := '966' || v_phone;
  if v_phone !~ '^9665[0-9]{8}$' then
    raise exception 'رقم الجوال غير صالح' using errcode = 'P0001';
  end if;

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
    v_dur   := v_dur   + v_service.duration_min;
    v_total := v_total + v_service.price;
    v_dep   := v_dep   + v_service.deposit_amount;
    if v_service.group_discount then v_grp := v_grp + 1; end if;
  end loop;

  -- الخصم يُطبَّق من شخصين فأكثر، كما في group_discount_for
  if v_grp >= 2 then
    v_disc := least(coalesce(v_rate, 0) * v_grp, v_total);
  end if;
  v_need := least(v_dep, greatest(v_total - v_disc, 0));

  -- ── حارس الإيصال ──────────────────────────────────────────────────
  -- يُقرأ ما رأته القراءة في الصورة، ويُقارن بالعربون المحسوب هنا لا
  -- بما أرسله المتصفّح. يُقبل مبلغ يساوي المطلوب أو يزيد: من حوّلت أكثر
  -- لا تُمنع، وهو ما يفعله الناس حين يقرّبون المبلغ.
  if v_guard and v_need > 0 then
    select * into v_scan from public.receipt_scans where path = v_receipt;
    if not found or v_scan.engine in ('none', 'failed') then
      raise exception 'لم يكتمل فحص الإيصال، انتظري لحظة ثم أعيدي الإرسال'
        using errcode = 'P0001';
    end if;
    if v_scan.engine = 'too_large' then
      raise exception 'حجم صورة الإيصال كبير، أرفقي لقطة شاشة أصغر'
        using errcode = 'P0001';
    end if;
    if coalesce(array_length(v_scan.keywords, 1), 0) = 0 then
      raise exception 'الصورة لا تبدو إيصال تحويل — أرفقي صورة إشعار التحويل من تطبيق البنك'
        using errcode = 'P0001';
    end if;
    if not exists (
      select 1 from unnest(v_scan.numbers || v_scan.all_numbers) n
       where n >= v_need
    ) then
      raise exception 'لم نجد مبلغ العربون (%) في صورة الإيصال، تأكدي من وضوح الصورة والمبلغ',
        trim(to_char(v_need, 'FM999999990.99')) using errcode = 'P0001';
    end if;
  end if;

  if not exists (select 1 from public.available_slots(p_date, v_dur) s where s.slot = p_time) then
    raise exception 'هذا الموعد لم يعد متاحًا، اختاري وقتًا آخر' using errcode = 'P0001';
  end if;

  insert into public.bookings (
    client_name, client_phone, the_date, start_time, duration_min,
    status, source, loc_text, loc_map, client_notes, receipt_path,
    discount_per_person
  ) values (
    v_name, v_phone, p_date, p_time, greatest(v_dur, 15),
    'pending', 'client', nullif(btrim(coalesce(p_loc_text, '')), ''),
    nullif(btrim(coalesce(p_loc_map, '')), ''), nullif(btrim(coalesce(p_notes, '')), ''),
    v_receipt, coalesce(v_rate, 0)
  ) returning id into v_id;

  -- أهليّة الخصم والعربون تُلقَطان على العنصر لحظة الحجز، فتغيير
  -- الإعدادات لاحقًا لا يغيّر حجزًا سُجّل.
  for i in 1 .. array_length(p_service_ids, 1) loop
    select * into v_service from public.services where id = p_service_ids[i];
    insert into public.booking_items (
      booking_id, service_id, service_name, service_icon, person_name,
      price, duration_min, sort, group_discount, deposit_amount
    ) values (
      v_id, v_service.id, v_service.name, v_service.icon,
      nullif(btrim(coalesce(p_person_names[i], '')), ''),
      v_service.price, v_service.duration_min, i,
      v_service.group_discount, v_service.deposit_amount
    );
  end loop;

  insert into public.activity_log (booking_id, actor, action, detail)
  values (v_id, 'client', 'created',
          jsonb_build_object('services', array_length(p_service_ids, 1),
                             'receipt', true, 'deposit_due', v_need,
                             'receipt_checked', coalesce(v_guard, false)));

  select * into v_booking from public.bookings where id = v_id;

  ref          := v_booking.ref;
  public_token := v_booking.public_token;
  the_date     := v_booking.the_date;
  start_time   := v_booking.start_time;
  price        := v_booking.price;
  return next;
end;
$function$;

revoke execute on function public.create_booking(text, text, date, time, uuid[], text[], text, text, text, text) from public;
grant  execute on function public.create_booking(text, text, date, time, uuid[], text[], text, text, text, text) to anon, authenticated;
