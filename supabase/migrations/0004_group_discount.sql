-- ═══════════════════════════════════════════════════════════════════════
-- 0004 — خصم المجموعة
--
-- طُبِّق على القاعدة الحيّة في 2026-08-21، ويُعاد تشغيله بلا ضرر.
--
-- مبلغ ثابت عن كل شخص، يُطبَّق تلقائيًا حين تحجز العميلة خدمةً مؤهَّلة
-- لشخصين فأكثر. الأهليّة خانةٌ على الخدمة نفسها لا مطابقةٌ لاسمها: إعادة
-- تسمية «ميك اب سهرة» لا تُسقط الخصم، وإضافة خدمة جماعية أخرى لا تحتاج
-- تعديل كود.
--
-- ما يُلقَط لحظة الحجز: أهليّة كل عنصر، والمبلغ للفرد. بذلك يبقى حجزٌ
-- قديم على خصمه حتى لو غيّرت صاحبة العمل المبلغ أو الأهليّة لاحقًا،
-- ويظلّ إعادة الحساب بعد تعديل العناصر صحيحًا.
-- ═══════════════════════════════════════════════════════════════════════

alter table public.settings
  add column if not exists group_discount_amount numeric(10,2) not null default 0;

alter table public.services
  add column if not exists group_discount boolean not null default false;

alter table public.booking_items
  add column if not exists group_discount boolean not null default false;

alter table public.bookings
  add column if not exists discount_per_person numeric(10,2) not null default 0,
  add column if not exists discount            numeric(10,2) not null default 0;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'settings_group_discount_ck') then
    alter table public.settings
      add constraint settings_group_discount_ck check (group_discount_amount >= 0);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'bookings_discount_ck') then
    alter table public.bookings
      add constraint bookings_discount_ck check (discount >= 0 and discount_per_person >= 0);
  end if;
end $$;

-- العتبة: شخصان فأكثر. مكتوبة هنا وحدها، ويقابلها GROUP_MIN في index.html.
create or replace function public.group_discount_for(p_booking_id uuid)
returns numeric
language sql stable
set search_path = public, pg_temp
as $$
  select case
           when count(*) filter (where i.group_discount) >= 2
             then count(*) filter (where i.group_discount) * b.discount_per_person
           else 0
         end
    from public.bookings b
    left join public.booking_items i on i.booking_id = b.id
   where b.id = p_booking_id
   group by b.discount_per_person;
$$;

-- معادلة السعر في مكان واحد: المجاميع تُحدَّث هنا، والسعر يحسبه المشغّل.
create or replace function public.recalc_booking(p_booking_id uuid)
returns void
language plpgsql
set search_path = public, pg_temp
as $function$
declare
  v_total numeric(10,2);
  v_dur   integer;
  v_disc  numeric(10,2);
begin
  select coalesce(sum(price), 0), coalesce(sum(duration_min), 0)
    into v_total, v_dur
  from public.booking_items
  where booking_id = p_booking_id;

  v_disc := coalesce(public.group_discount_for(p_booking_id), 0);

  update public.bookings
     set items_total  = v_total,
         discount     = least(v_disc, v_total),
         duration_min = greatest(v_dur, 15)
   where id = p_booking_id;
end;
$function$;

create or replace function public.bookings_apply_override()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $function$
begin
  -- تجاوز الإدارة كلمةٌ أخيرة: إن كتبت إجماليًا فهو الإجمالي بلا خصم فوقه.
  new.price := greatest(coalesce(new.price_override, new.items_total - new.discount), 0);
  if new.deposit > new.price then new.deposit := new.price; end if;
  if new.deposit < 0 then new.deposit := 0; end if;
  return new;
end;
$function$;

-- الإعدادات العامة تحمل مبلغ الخصم لتعرضه الصفحة قبل الإرسال.
drop view if exists public.public_settings;
create view public.public_settings
with (security_invoker = off) as
  select business_name, tagline, timezone, slot_step_min,
         min_lead_hours, max_advance_days, whatsapp_phone,
         accepting_bookings, closed_message,
         deposit_rate, bank_name, iban, beneficiary_name,
         instagram_url, tiktok_url, group_discount_amount
  from public.settings where id = 1;
grant select on public.public_settings to anon, authenticated;

drop function if exists public.get_public_settings();
create function public.get_public_settings()
returns table (
  business_name text, tagline text, timezone text, slot_step_min integer,
  min_lead_hours integer, max_advance_days integer, whatsapp_phone text,
  accepting_bookings boolean, closed_message text, deposit_rate numeric,
  bank_name text, iban text, beneficiary_name text,
  instagram_url text, tiktok_url text, group_discount_amount numeric
)
language sql stable security definer
set search_path = public, pg_temp
as $$
  select s.business_name, s.tagline, s.timezone, s.slot_step_min,
         s.min_lead_hours, s.max_advance_days, s.whatsapp_phone,
         s.accepting_bookings, s.closed_message, s.deposit_rate,
         s.bank_name, s.iban, s.beneficiary_name,
         s.instagram_url, s.tiktok_url, s.group_discount_amount
  from public.settings s where s.id = 1;
$$;
revoke execute on function public.get_public_settings() from public;
grant execute on function public.get_public_settings() to anon, authenticated;

-- صفحة المتابعة تُظهر الخصم كسطر مستقل.
drop function if exists public.get_booking_by_token(uuid);
create function public.get_booking_by_token(p_token uuid)
returns table (
  ref text, client_name text, the_date date, start_time time,
  duration_min integer, status public.booking_status, price numeric,
  deposit numeric, loc_text text, client_notes text,
  cancel_requested boolean, created_at timestamptz,
  receipt_received boolean, items_total numeric, discount numeric, items jsonb
)
language plpgsql stable security definer
set search_path = public, pg_temp
as $$
begin
  return query
    select b.ref, b.client_name, b.the_date, b.start_time, b.duration_min,
           b.status, b.price, b.deposit, b.loc_text, b.client_notes,
           b.cancel_requested, b.created_at,
           (b.receipt_path is not null), b.items_total, b.discount,
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

-- الخصم يُحسب على الخادم من الخدمات نفسها، فلا تستطيع صفحةٌ معدَّلة
-- أن تطلب خصمًا لم تستحقّه.
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
  v_open    boolean;
  v_phone   text;
  v_name    text;
  v_receipt text;
  v_rate    numeric;
  v_dur     integer := 0;
  v_booking public.bookings%rowtype;
  v_service public.services%rowtype;
  v_id      uuid;
  i         integer;
begin
  select accepting_bookings, group_discount_amount
    into v_open, v_rate
    from public.settings where id = 1;
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
    status, source, loc_text, loc_map, client_notes, receipt_path,
    discount_per_person
  ) values (
    v_name, v_phone, p_date, p_time, greatest(v_dur, 15),
    'pending', 'client', nullif(btrim(coalesce(p_loc_text, '')), ''),
    nullif(btrim(coalesce(p_loc_map, '')), ''), nullif(btrim(coalesce(p_notes, '')), ''),
    v_receipt, coalesce(v_rate, 0)
  ) returning id into v_id;

  -- أهليّة الخصم تُلقَط على العنصر لحظة الحجز.
  for i in 1 .. array_length(p_service_ids, 1) loop
    select * into v_service from public.services where id = p_service_ids[i];
    insert into public.booking_items (
      booking_id, service_id, service_name, service_icon, person_name,
      price, duration_min, sort, group_discount
    ) values (
      v_id, v_service.id, v_service.name, v_service.icon,
      nullif(btrim(coalesce(p_person_names[i], '')), ''),
      v_service.price, v_service.duration_min, i, v_service.group_discount
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
