-- ============================================================================
-- تطبيق المخطط من الصفر
--
-- الصق هذا الملف كاملًا في: لوحة Supabase ← SQL Editor ← Run.
--
-- يبدأ بحذف كائنات النظام إن وُجدت، ثم ينشئها من جديد. هذا يجعله صالحًا
-- للتشغيل سواء كانت القاعدة فارغة أو مطبَّقة جزئيًا.
--
-- تحذير: الحذف يشمل الحجوزات. شغّله ما دام النظام لم يستقبل حجوزات حقيقية
-- بعد. بعد أن يبدأ العمل الفعلي، استخدم ملفات الترحيل في migrations/ بدل هذا.
-- ============================================================================

-- ── حذف ما سبق ──────────────────────────────────────────────────────────────
drop table if exists public.activity_log      cascade;
drop table if exists public.booking_items     cascade;
drop table if exists public.bookings          cascade;
drop table if exists public.date_overrides    cascade;
drop table if exists public.availability_rules cascade;
drop table if exists public.services          cascade;
drop table if exists public.admins            cascade;
drop view  if exists public.public_settings   cascade;
drop table if exists public.settings          cascade;
drop type  if exists public.booking_status    cascade;

drop function if exists public.available_slots(date, integer, uuid)            cascade;
drop function if exists public.days_with_availability(date, integer, integer)  cascade;
drop function if exists public.create_booking(text, text, date, time, uuid[], text[], text, text, text) cascade;
drop function if exists public.get_booking_by_token(uuid)  cascade;
drop function if exists public.request_cancel(uuid)        cascade;
drop function if exists public.day_windows(date)           cascade;
drop function if exists public.busy_intervals(date, uuid)  cascade;
drop function if exists public.recalc_booking(uuid)        cascade;
drop function if exists public.booking_items_sync()        cascade;
drop function if exists public.bookings_apply_override()   cascade;
drop function if exists public.bookings_set_ref()          cascade;
drop function if exists public.gen_booking_ref()           cascade;
drop function if exists public.local_now()                 cascade;
drop function if exists public.local_today()               cascade;
drop function if exists public.is_admin()                  cascade;

-- النشر اللحظي: أُعيد بناؤه في نهاية المخطط.
do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    begin
      alter publication supabase_realtime drop table public.bookings;
    exception when others then null; end;
    begin
      alter publication supabase_realtime drop table public.booking_items;
    exception when others then null; end;
  end if;
end $$;

-- ── ثم المخطط كاملًا ────────────────────────────────────────────────────────
-- ما يلي نسخة طبق الأصل من supabase/migrations/0001_init.sql
-- ============================================================================
-- Iman Almousa — booking system, initial schema
--
-- Two audiences share one database:
--   * the public booking page, which runs as `anon` and may never read a
--     client list. Everything it needs goes through a security-definer
--     function that returns times and totals, never other people's rows.
--   * the admin dashboard, which runs as an authenticated user and owns
--     everything.
--
-- Appointment dates and times are stored as `date` + `time`, deliberately
-- not as timestamptz. The business runs in one city; storing wall-clock
-- values keeps "4 PM on the 12th" true regardless of where a browser or a
-- server thinks it is.
-- ============================================================================

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- settings — one row, the knobs the artist controls
-- ---------------------------------------------------------------------------
create table public.settings (
  id                smallint primary key default 1 check (id = 1),
  business_name     text        not null default 'إيمان آل موسى',
  tagline           text                 default 'ميك اب عرائس ومناسبات',
  timezone          text        not null default 'Asia/Riyadh',
  travel_buffer_min integer     not null default 40  check (travel_buffer_min between 0 and 240),
  slot_step_min     integer     not null default 30  check (slot_step_min in (15, 20, 30, 60)),
  min_lead_hours    integer     not null default 4   check (min_lead_hours between 0 and 720),
  max_advance_days  integer     not null default 120 check (max_advance_days between 1 and 730),
  driver_phone      text,
  whatsapp_phone    text,
  accepting_bookings boolean    not null default true,
  closed_message    text                 default 'الحجز مغلق مؤقتًا، تواصلي معنا عبر واتساب.',
  updated_at        timestamptz not null default now()
);

insert into public.settings (id) values (1);

-- The public page needs a handful of these values. It must not see the
-- driver's phone number, so it reads this view instead of the table.
create view public.public_settings
with (security_invoker = off) as
  select business_name, tagline, timezone, slot_step_min,
         min_lead_hours, max_advance_days, whatsapp_phone,
         accepting_bookings, closed_message
  from public.settings
  where id = 1;

-- ---------------------------------------------------------------------------
-- services — the price list
-- ---------------------------------------------------------------------------
create table public.services (
  id                uuid primary key default gen_random_uuid(),
  name              text        not null check (length(btrim(name)) between 2 and 60),
  icon              text        not null default 'sparkle',
  price             numeric(10,2) not null default 0 check (price >= 0),
  duration_min      integer     not null default 45 check (duration_min between 15 and 600),
  description       text,
  sort              integer     not null default 0,
  active            boolean     not null default true,
  bookable_by_client boolean    not null default true,
  created_at        timestamptz not null default now()
);

create index services_active_idx on public.services (active, sort);

insert into public.services (name, icon, price, duration_min, description, sort) values
  ('ميك اب عروس',  'bride',    0, 60, 'مكياج زفاف كامل مع التثبيت', 1),
  ('ميك اب سهرة',  'evening',  0, 45, 'مكياج مناسبات وسهرات',       2);

-- ---------------------------------------------------------------------------
-- availability_rules — the recurring weekly schedule
--
-- weekday follows Postgres `extract(dow)`: 0 = Sunday … 6 = Saturday, which
-- matches how the Saudi week is displayed in the UI.
-- Several rows may cover the same weekday (a morning window and an evening
-- window, for instance); the slot builder unions them.
-- ---------------------------------------------------------------------------
create table public.availability_rules (
  id         uuid primary key default gen_random_uuid(),
  label      text,
  weekday    smallint    not null check (weekday between 0 and 6),
  start_time time        not null,
  end_time   time        not null,
  active     boolean     not null default true,
  valid_from date,
  valid_to   date,
  created_at timestamptz not null default now(),
  constraint availability_rules_window_ck check (end_time > start_time),
  constraint availability_rules_validity_ck check (valid_to is null or valid_from is null or valid_to >= valid_from)
);

create index availability_rules_weekday_idx on public.availability_rules (weekday, active);

-- A sensible starting schedule: Saturday through Thursday, 4 PM to 10 PM.
insert into public.availability_rules (label, weekday, start_time, end_time)
select 'الدوام الافتراضي', d, '16:00', '22:00'
from unnest(array[6, 0, 1, 2, 3, 4]) as d;

-- ---------------------------------------------------------------------------
-- date_overrides — exceptions that beat the weekly rules
--   'closed' : that whole day is off
--   'custom' : that day uses these hours instead of its weekday rules
-- ---------------------------------------------------------------------------
create table public.date_overrides (
  id         uuid primary key default gen_random_uuid(),
  the_date   date        not null,
  kind       text        not null check (kind in ('closed', 'custom')),
  start_time time,
  end_time   time,
  note       text,
  created_at timestamptz not null default now(),
  constraint date_overrides_hours_ck check (
    kind = 'closed'
    or (start_time is not null and end_time is not null and end_time > start_time)
  )
);

create index date_overrides_date_idx on public.date_overrides (the_date);
create unique index date_overrides_closed_uq on public.date_overrides (the_date) where kind = 'closed';

-- ---------------------------------------------------------------------------
-- bookings
--
-- Solo and group bookings are the same shape: every booking owns one or more
-- rows in booking_items. A "solo" booking is simply a booking with one item.
-- Keeping one code path removes the entire class of solo/group divergence.
--
-- price and duration_min are maintained by trigger from the items, so the
-- summary can never disagree with the detail. price_override, when set,
-- replaces the computed total — the discount stays visible instead of being
-- smeared across the line items.
-- ---------------------------------------------------------------------------
create type public.booking_status as enum
  ('pending', 'confirmed', 'done', 'cancelled', 'rejected', 'no_show');

create table public.bookings (
  id             uuid primary key default gen_random_uuid(),
  ref            text        not null unique,
  public_token   uuid        not null default gen_random_uuid(),
  client_name    text        not null check (length(btrim(client_name)) between 2 and 80),
  client_phone   text        not null check (client_phone ~ '^9665[0-9]{8}$'),
  the_date       date        not null,
  start_time     time        not null,
  duration_min   integer     not null default 45 check (duration_min between 15 and 900),
  status         public.booking_status not null default 'pending',
  items_total    numeric(10,2) not null default 0 check (items_total >= 0),
  price_override numeric(10,2) check (price_override >= 0),
  price          numeric(10,2) not null default 0 check (price >= 0),
  deposit        numeric(10,2) not null default 0 check (deposit >= 0),
  loc_text       text,
  loc_map        text,
  client_notes   text,
  admin_notes    text,
  source         text        not null default 'client' check (source in ('client', 'admin')),
  cancel_requested boolean   not null default false,
  created_at     timestamptz not null default now(),
  confirmed_at   timestamptz,
  completed_at   timestamptz,
  constraint bookings_deposit_ck check (deposit <= price)
);

create index bookings_date_idx    on public.bookings (the_date, start_time);
create index bookings_status_idx  on public.bookings (status, the_date);
create index bookings_phone_idx   on public.bookings (client_phone);
create index bookings_token_idx   on public.bookings (public_token);

-- ---------------------------------------------------------------------------
-- booking_items — one row per person served
--
-- service_name, price and duration are snapshots taken at booking time. A
-- service renamed, repriced or deleted later never rewrites history and never
-- orphans an old booking.
-- ---------------------------------------------------------------------------
create table public.booking_items (
  id           uuid primary key default gen_random_uuid(),
  booking_id   uuid        not null references public.bookings(id) on delete cascade,
  service_id   uuid        references public.services(id) on delete set null,
  service_name text        not null,
  service_icon text        not null default 'sparkle',
  person_name  text,
  price        numeric(10,2) not null default 0 check (price >= 0),
  duration_min integer     not null default 45 check (duration_min between 15 and 600),
  sort         integer     not null default 0
);

create index booking_items_booking_idx on public.booking_items (booking_id, sort);

-- ---------------------------------------------------------------------------
-- activity_log — who changed what, so a mistaken tap can be traced back
-- ---------------------------------------------------------------------------
create table public.activity_log (
  id         bigserial primary key,
  booking_id uuid references public.bookings(id) on delete cascade,
  actor      text not null default 'admin',
  action     text not null,
  detail     jsonb,
  created_at timestamptz not null default now()
);

create index activity_log_booking_idx on public.activity_log (booking_id, created_at desc);

-- ============================================================================
-- Helpers
-- ============================================================================

-- Local "now" in the configured timezone. Every date decision in this schema
-- goes through here rather than through now() or CURRENT_DATE, so the system
-- never disagrees with the clock on the artist's wall.
create or replace function public.local_now()
returns timestamp
language sql stable
set search_path = public, pg_temp
as $$
  select (now() at time zone (select timezone from public.settings where id = 1));
$$;

create or replace function public.local_today()
returns date
language sql stable
set search_path = public, pg_temp
as $$
  select public.local_now()::date;
$$;

-- Short, human-speakable reference: IA-7K3QP
create or replace function public.gen_booking_ref()
returns text
language plpgsql volatile
set search_path = public, pg_temp
as $$
declare
  alphabet constant text := '23456789ABCDEFGHJKLMNPQRSTUVWXYZ';
  candidate text;
  i integer;
begin
  loop
    candidate := 'IA-';
    for i in 1..5 loop
      candidate := candidate || substr(alphabet, 1 + floor(random() * length(alphabet))::int, 1);
    end loop;
    exit when not exists (select 1 from public.bookings where ref = candidate);
  end loop;
  return candidate;
end;
$$;

create or replace function public.bookings_set_ref()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  if new.ref is null or btrim(new.ref) = '' then
    new.ref := public.gen_booking_ref();
  end if;
  return new;
end;
$$;

create trigger bookings_set_ref_trg
  before insert on public.bookings
  for each row execute function public.bookings_set_ref();

-- Keep the booking totals honest: they are derived, never typed twice.
create or replace function public.recalc_booking(p_booking_id uuid)
returns void
language plpgsql
set search_path = public, pg_temp
as $$
declare
  v_total numeric(10,2);
  v_dur   integer;
begin
  select coalesce(sum(price), 0), coalesce(sum(duration_min), 0)
    into v_total, v_dur
  from public.booking_items
  where booking_id = p_booking_id;

  update public.bookings
     set items_total  = v_total,
         price        = coalesce(price_override, v_total),
         duration_min = greatest(v_dur, 15)
   where id = p_booking_id;
end;
$$;

create or replace function public.booking_items_sync()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  perform public.recalc_booking(coalesce(new.booking_id, old.booking_id));
  return coalesce(new, old);
end;
$$;

create trigger booking_items_sync_trg
  after insert or update or delete on public.booking_items
  for each row execute function public.booking_items_sync();

-- price_override is the only way to change the charged total by hand.
--
-- This fires on every insert and update rather than on a column list: a
-- deposit typed larger than the total, or a total that drops below a deposit
-- already taken, both have to be reconciled here. Restricting the trigger to
-- `of price_override, items_total` lets a plain deposit edit slip past the
-- clamp and hit the check constraint as a raw database error.
create or replace function public.bookings_apply_override()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  new.price := coalesce(new.price_override, new.items_total);
  if new.deposit > new.price then
    new.deposit := new.price;
  end if;
  if new.deposit < 0 then
    new.deposit := 0;
  end if;
  return new;
end;
$$;

create trigger bookings_apply_override_trg
  before insert or update on public.bookings
  for each row execute function public.bookings_apply_override();

-- ============================================================================
-- Availability
-- ============================================================================

-- The working windows for one date: a date override wins over the weekly
-- rules; a 'closed' override yields nothing at all.
create or replace function public.day_windows(p_date date)
returns table (win_start time, win_end time)
language plpgsql stable
set search_path = public, pg_temp
as $$
begin
  if exists (select 1 from public.date_overrides o
              where o.the_date = p_date and o.kind = 'closed') then
    return;
  end if;

  if exists (select 1 from public.date_overrides o
              where o.the_date = p_date and o.kind = 'custom') then
    return query
      select o.start_time, o.end_time
      from public.date_overrides o
      where o.the_date = p_date and o.kind = 'custom'
      order by o.start_time;
    return;
  end if;

  return query
    select r.start_time, r.end_time
    from public.availability_rules r
    where r.active
      and r.weekday = extract(dow from p_date)::smallint
      and (r.valid_from is null or p_date >= r.valid_from)
      and (r.valid_to   is null or p_date <= r.valid_to)
    order by r.start_time;
end;
$$;

-- Intervals already spoken for on a date, each padded by the travel buffer so
-- the artist can actually get from one address to the next.
create or replace function public.busy_intervals(p_date date, p_exclude uuid default null)
returns table (busy_start time, busy_end time)
language plpgsql stable
set search_path = public, pg_temp
as $$
declare
  v_buffer integer;
begin
  select travel_buffer_min into v_buffer from public.settings where id = 1;

  return query
    select b.start_time,
           (b.start_time + make_interval(mins => b.duration_min + v_buffer))::time
    from public.bookings b
    where b.the_date = p_date
      and b.status in ('pending', 'confirmed', 'done')
      and (p_exclude is null or b.id <> p_exclude);
end;
$$;

-- Free start times on a date for a job of p_duration_min.
--
-- A candidate is offered only when the whole job fits inside a working window
-- AND the job plus its travel buffer overlaps nothing already booked. The
-- duration is a parameter precisely so that a four-hour group is never
-- squeezed into a slot sized for a one-hour face.
create or replace function public.available_slots(
  p_date         date,
  p_duration_min integer default null,
  p_exclude      uuid    default null
)
returns table (slot time)
language plpgsql stable security definer
set search_path = public, pg_temp
as $$
declare
  v_step     integer;
  v_buffer   integer;
  v_lead     integer;
  v_advance  integer;
  v_dur      integer;
  v_today    date;
  v_earliest timestamp;
  w          record;
  b          record;
  t          time;
  job_end    time;
  block_end  time;
  ok         boolean;
begin
  select slot_step_min, travel_buffer_min, min_lead_hours, max_advance_days
    into v_step, v_buffer, v_lead, v_advance
  from public.settings where id = 1;

  v_dur := greatest(coalesce(p_duration_min, 45), 15);
  v_today := public.local_today();

  -- Outside the bookable horizon entirely.
  if p_date < v_today or p_date > v_today + v_advance then
    return;
  end if;

  v_earliest := public.local_now() + make_interval(hours => v_lead);

  for w in select * from public.day_windows(p_date) loop
    t := w.win_start;
    while t + make_interval(mins => v_dur) <= (w.win_end + interval '0') loop
      job_end   := (t + make_interval(mins => v_dur))::time;
      block_end := (t + make_interval(mins => v_dur + v_buffer))::time;

      -- Never offer a time that has already passed the lead deadline.
      ok := (p_date + t) >= v_earliest;

      -- …and never one that collides with an existing job or its travel time.
      if ok then
        for b in select * from public.busy_intervals(p_date, p_exclude) loop
          if t < b.busy_end and block_end > b.busy_start then
            ok := false;
            exit;
          end if;
        end loop;
      end if;

      if ok then
        slot := t;
        return next;
      end if;

      t := (t + make_interval(mins => v_step))::time;
      exit when t < w.win_start;  -- guards a wrap past midnight
    end loop;
  end loop;
end;
$$;

-- Which of the next N days have any room at all — powers the client's week
-- strip without leaking a single client name.
create or replace function public.days_with_availability(
  p_from         date,
  p_days         integer default 14,
  p_duration_min integer default null
)
returns table (the_date date, slot_count integer)
language plpgsql stable security definer
set search_path = public, pg_temp
as $$
declare
  d date;
  i integer;
begin
  for i in 0 .. greatest(coalesce(p_days, 14), 1) - 1 loop
    d := p_from + i;
    the_date := d;
    select count(*)::integer into slot_count
      from public.available_slots(d, p_duration_min);
    return next;
  end loop;
end;
$$;

-- ============================================================================
-- Public booking entry point
--
-- The anon role never touches `bookings` directly. It calls this, which
-- re-checks the slot server-side, forces status='pending' and source='client',
-- and hands back only the new booking's own reference and token.
-- ============================================================================
create or replace function public.create_booking(
  p_client_name  text,
  p_client_phone text,
  p_date         date,
  p_time         time,
  p_service_ids  uuid[],
  p_person_names text[] default null,
  p_loc_text     text default null,
  p_loc_map      text default null,
  p_notes        text default null
)
returns table (ref text, public_token uuid, the_date date, start_time time, price numeric)
language plpgsql volatile security definer
set search_path = public, pg_temp
as $$
declare
  v_open      boolean;
  v_phone     text;
  v_name      text;
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

  -- Accept 05xxxxxxxx, +9665xxxxxxxx, 009665xxxxxxxx, spaces and dashes, and
  -- Arabic-Indic digits; store one canonical form.
  v_phone := translate(coalesce(p_client_phone, ''), '٠١٢٣٤٥٦٧٨٩', '0123456789');
  v_phone := regexp_replace(v_phone, '[^0-9]', '', 'g');
  v_phone := regexp_replace(v_phone, '^00966', '', '');
  v_phone := regexp_replace(v_phone, '^966',   '', '');
  v_phone := regexp_replace(v_phone, '^0',     '', '');
  v_phone := '966' || v_phone;
  if v_phone !~ '^9665[0-9]{8}$' then
    raise exception 'رقم الجوال غير صالح' using errcode = 'P0001';
  end if;

  if p_service_ids is null or array_length(p_service_ids, 1) is null then
    raise exception 'يرجى اختيار خدمة واحدة على الأقل' using errcode = 'P0001';
  end if;
  if array_length(p_service_ids, 1) > 12 then
    raise exception 'عدد الخدمات كبير جدًا، تواصلي معنا مباشرة' using errcode = 'P0001';
  end if;

  -- Total duration decides which slots are legal for this request.
  for i in 1 .. array_length(p_service_ids, 1) loop
    select * into v_service from public.services
     where id = p_service_ids[i] and active and bookable_by_client;
    if not found then
      raise exception 'خدمة غير متاحة' using errcode = 'P0001';
    end if;
    v_dur := v_dur + v_service.duration_min;
  end loop;

  -- The authoritative check. A stale page cannot book a taken slot.
  if not exists (select 1 from public.available_slots(p_date, v_dur) s where s.slot = p_time) then
    raise exception 'هذا الموعد لم يعد متاحًا، اختاري وقتًا آخر' using errcode = 'P0001';
  end if;

  insert into public.bookings (
    client_name, client_phone, the_date, start_time, duration_min,
    status, source, loc_text, loc_map, client_notes
  ) values (
    v_name, v_phone, p_date, p_time, greatest(v_dur, 15),
    'pending', 'client', nullif(btrim(coalesce(p_loc_text, '')), ''),
    nullif(btrim(coalesce(p_loc_map, '')), ''), nullif(btrim(coalesce(p_notes, '')), '')
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
  values (v_id, 'client', 'created', jsonb_build_object('services', array_length(p_service_ids, 1)));

  select * into v_booking from public.bookings where id = v_id;

  ref          := v_booking.ref;
  public_token := v_booking.public_token;
  the_date     := v_booking.the_date;
  start_time   := v_booking.start_time;
  price        := v_booking.price;
  return next;
end;
$$;

-- The client's own booking, by the unguessable token in her tracking link.
create or replace function public.get_booking_by_token(p_token uuid)
returns table (
  ref text, client_name text, the_date date, start_time time,
  duration_min integer, status public.booking_status, price numeric,
  deposit numeric, loc_text text, client_notes text,
  cancel_requested boolean, created_at timestamptz, items jsonb
)
language plpgsql stable security definer
set search_path = public, pg_temp
as $$
begin
  return query
    select b.ref, b.client_name, b.the_date, b.start_time, b.duration_min,
           b.status, b.price, b.deposit, b.loc_text, b.client_notes,
           b.cancel_requested, b.created_at,
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

-- A client may ask to cancel; the artist decides. This never deletes a row.
create or replace function public.request_cancel(p_token uuid)
returns boolean
language plpgsql volatile security definer
set search_path = public, pg_temp
as $$
declare
  v_id uuid;
begin
  select id into v_id from public.bookings
   where public_token = p_token and status in ('pending', 'confirmed');
  if not found then
    return false;
  end if;

  update public.bookings set cancel_requested = true where id = v_id;
  insert into public.activity_log (booking_id, actor, action)
  values (v_id, 'client', 'cancel_requested');
  return true;
end;
$$;

-- ============================================================================
-- Who counts as an administrator
--
-- Being signed in is NOT enough. The public page ships an anon key, and if
-- email signups are ever enabled — by a dashboard toggle, by accident, or by
-- a future change — a stranger with an account would otherwise inherit full
-- read/write over every client's data. Admin rights come from this explicit
-- allowlist instead, so the guarantee lives in the schema rather than in a
-- setting someone can flip.
-- ============================================================================
create table public.admins (
  user_id  uuid primary key references auth.users(id) on delete cascade,
  email    text,
  added_at timestamptz not null default now()
);

create or replace function public.is_admin()
returns boolean
language sql stable security definer
set search_path = public, pg_temp
as $$
  select exists (select 1 from public.admins a where a.user_id = auth.uid());
$$;

revoke all on public.admins from anon, authenticated;

-- ============================================================================
-- Row level security
-- ============================================================================
alter table public.admins             enable row level security;
alter table public.settings           enable row level security;
alter table public.services           enable row level security;
alter table public.availability_rules enable row level security;
alter table public.date_overrides     enable row level security;
alter table public.bookings           enable row level security;
alter table public.booking_items      enable row level security;
alter table public.activity_log       enable row level security;

-- Admin: on the allowlist means full control. Merely signed in means nothing.
create policy admin_all_settings   on public.settings           for all to authenticated using (public.is_admin()) with check (public.is_admin());
create policy admin_all_services   on public.services           for all to authenticated using (public.is_admin()) with check (public.is_admin());
create policy admin_all_rules      on public.availability_rules for all to authenticated using (public.is_admin()) with check (public.is_admin());
create policy admin_all_overrides  on public.date_overrides     for all to authenticated using (public.is_admin()) with check (public.is_admin());
create policy admin_all_bookings   on public.bookings           for all to authenticated using (public.is_admin()) with check (public.is_admin());
create policy admin_all_items      on public.booking_items      for all to authenticated using (public.is_admin()) with check (public.is_admin());
create policy admin_all_activity   on public.activity_log       for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- Admins may see the roster but never edit it; adding an administrator is a
-- deliberate act performed against the database, not something the app does.
create policy admin_read_admins on public.admins
  for select to authenticated using (public.is_admin());

-- Public: the price list and the published working hours, nothing else.
-- There is deliberately no anon policy on bookings, booking_items, settings
-- or activity_log — the public page reaches those only through the
-- security-definer functions above.
create policy anon_read_services on public.services
  for select to anon using (active and bookable_by_client);

create policy anon_read_rules on public.availability_rules
  for select to anon using (active);

create policy anon_read_overrides on public.date_overrides
  for select to anon using (true);

-- ============================================================================
-- Grants
--
-- Policies filter rows; grants decide whether the role may touch the table at
-- all. Both are needed. These are spelled out rather than left to a platform
-- default so the migration behaves the same on any Postgres.
-- ============================================================================
revoke all on all tables in schema public from anon, authenticated;

grant usage on schema public to anon, authenticated;

-- The administrator's reach is still bounded by is_admin() in every policy.
grant select, insert, update, delete on
  public.settings, public.services, public.availability_rules,
  public.date_overrides, public.bookings, public.booking_items,
  public.activity_log
  to authenticated;
grant select on public.admins to authenticated;
grant usage, select on all sequences in schema public to authenticated;

grant select on public.services           to anon;
grant select on public.availability_rules to anon;
grant select on public.date_overrides     to anon;
grant select on public.public_settings    to anon;

grant execute on function public.available_slots(date, integer, uuid)          to anon;
grant execute on function public.days_with_availability(date, integer, integer) to anon;
grant execute on function public.create_booking(text, text, date, time, uuid[], text[], text, text, text) to anon;
grant execute on function public.get_booking_by_token(uuid)                    to anon;
grant execute on function public.request_cancel(uuid)                          to anon;

revoke execute on function public.recalc_booking(uuid) from anon;
revoke execute on function public.gen_booking_ref()    from anon;

-- ============================================================================
-- Realtime — the dashboard learns about a new request the moment it lands.
-- Realtime honours RLS, so only the signed-in admin receives these.
-- ============================================================================
alter publication supabase_realtime add table public.bookings;
alter publication supabase_realtime add table public.booking_items;
