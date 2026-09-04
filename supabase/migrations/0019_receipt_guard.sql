-- الإيصال: دليلٌ لا رقمٌ كبير.
--
-- كان الحارس يقبل صورةً فيها كلمةٌ من قاموس الإيصالات ورقمٌ يبلغ العربون.
-- وفاتورة سينما تحمل الاثنين: فيها SAR وفيها ١٧١. فقُبلت وليست إيصالًا.
--
-- والعلّة أنّ الآيبان كان يُقرأ ويُسجَّل ثم يُهمَل عند الحكم. وهو الدليل
-- الوحيد الذي لا تحمله صورةٌ من مكانٍ آخر: رقم حسابٍ بعينه. فصار شرطًا
-- لا قرينة، ومعه المبلغ. ولا يُقبل إيصالٌ إلّا باجتماعهما.
--
-- ولا يُقال للعميلة أيُّ الشرطين سقط. من عرف أنّ المبلغ هو المطلوب زوّر
-- مبلغًا، ومن عرف أنّ الآيبان مطلوب ألصقه. فالجواب واحد في الحالتين:
-- «الإيصال غير صحيح» — ويبقى السبب في السجلّ لصاحبة العمل وحدها.
--
-- وثلاثة أحوال لا حالان: «تمّ» و«غير صحيح» و«لم يكتمل الفحص بعد». والثالث
-- ليس رفضًا، فلا يُعامَل معاملته: تُطمأَن العميلة وتُعاد المحاولة.

/* ═══ ١) طول ذيل الآيبان — مقياسٌ يُضبَط لا رقمٌ مدفون ═══════════════ */

alter table public.settings
  add column if not exists receipt_iban_digits smallint not null default 6;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'settings_iban_digits_ck') then
    alter table public.settings add constraint settings_iban_digits_ck
      check (receipt_iban_digits between 5 and 24);
  end if;
end $$;

/* ═══ ٢) العربون المطلوب — حسابٌ واحد لا اثنان ══════════════════════
   كان محسوبًا داخل create_booking وحدها، فلم يكن للفحص المسبق سبيلٌ إلى
   الرقم نفسه. أُخرج ليُستعمل في الموضعين، فلا يفترق حكمُ اللحظتين. */

create or replace function public.deposit_needed(p_service_ids uuid[])
returns numeric
language plpgsql stable security definer set search_path to 'public', 'pg_temp'
as $fn$
declare
  v_service public.services%rowtype;
  v_rate    numeric;
  v_total   numeric := 0;
  v_dep     numeric := 0;
  v_disc    numeric := 0;
  v_grp     integer := 0;
  i         integer;
begin
  if p_service_ids is null or array_length(p_service_ids, 1) is null then return 0; end if;
  select group_discount_amount into v_rate from public.settings where id = 1;

  for i in 1 .. array_length(p_service_ids, 1) loop
    select * into v_service from public.services
     where id = p_service_ids[i] and active and bookable_by_client;
    if not found then return 0; end if;
    v_total := v_total + v_service.price;
    v_dep   := v_dep   + v_service.deposit_amount;
    if v_service.group_discount then v_grp := v_grp + 1; end if;
  end loop;

  if v_grp >= 2 then
    v_disc := least(coalesce(v_rate, 0) * v_grp, v_total);
  end if;
  return least(v_dep, greatest(v_total - v_disc, 0));
end $fn$;
revoke all on function public.deposit_needed(uuid[]) from public;
grant execute on function public.deposit_needed(uuid[]) to anon, authenticated;

/* ═══ ٣) الحكم ═════════════════════════════════════════════════════════
   'ok'   قُبل — آيبانها فيه، ومبلغٌ يبلغ العربون
   'bad'  رُفض — ولا يُقال أيُّ الشرطين سقط
   'wait' لم يكتمل الفحص بعد — وليس رفضًا */

create or replace function public.receipt_state(p_path text, p_need numeric)
returns text
language plpgsql stable security definer set search_path to 'public', 'pg_temp'
as $fn$
declare v public.receipt_scans%rowtype; s record;
begin
  select * into s from public.settings where id = 1;
  if not coalesce(s.receipt_ocr_required, false) then return 'ok'; end if;
  if coalesce(p_need, 0) <= 0 then return 'ok'; end if;

  select * into v from public.receipt_scans where path = p_path;
  if not found then return 'wait'; end if;

  -- تعذّرت القراءة لا لعيبٍ في الإيصال: لا يُتّهم من رفعه.
  if v.engine in ('none', 'failed') then return 'wait'; end if;
  if v.engine = 'too_large' then return 'bad'; end if;

  -- الشرط الأوّل: آيبان صاحبة العمل. لا تحمله صورةٌ من مكانٍ آخر.
  if not coalesce(v.iban_hit, false) then return 'bad'; end if;

  -- الشرط الثاني: مبلغٌ يساوي العربون أو يزيد. ومن المبالغ الموسومة
  -- بعملةٍ وحدها — لا كلِّ رقمٍ في الصورة، وإلّا مرّ رقمُ مرجعٍ أو رصيد.
  if not exists (
    select 1 from unnest(coalesce(v.numbers, '{}'::numeric[])) n where n >= p_need
  ) then
    return 'bad';
  end if;

  return 'ok';
end $fn$;
revoke all on function public.receipt_state(text, numeric) from public;
grant execute on function public.receipt_state(text, numeric) to anon, authenticated;

/* ═══ ٤) الفحص المسبق — قبل الإرسال لا بعده ═══════════════════════════
   تعرف العميلة أنّ الصورة لا تصلح وهي واقفةٌ عندها. والجواب حرفٌ واحد:
   لا مبلغَ فيه ولا سببَ يُبنى عليه تزوير. */

drop function if exists public.check_receipt(text, uuid[]);
create function public.check_receipt(p_path text, p_service_ids uuid[])
returns text
language plpgsql stable security definer set search_path to 'public', 'pg_temp'
as $fn$
begin
  if p_path is null
     or p_path !~ '^pending/[0-9a-f-]{36}\.(jpg|jpeg|png|webp|heic|pdf)$' then
    return 'bad';
  end if;
  return public.receipt_state(p_path, public.deposit_needed(p_service_ids));
end $fn$;
revoke all on function public.check_receipt(text, uuid[]) from public;
grant execute on function public.check_receipt(text, uuid[]) to anon, authenticated;

/* ═══ ٥) الحارس في موضع الحكم ══════════════════════════════════════════
   المتصفّح لا يُصدَّق: ما يمنعه الفحص المسبق يمنعه هذا أيضًا، بالقاعدة
   نفسها. والرسالة واحدة لا تُفصح. */

create or replace function public.create_booking(
  p_client_name text, p_client_phone text, p_date date, p_time time without time zone,
  p_service_ids uuid[], p_person_names text[] default null::text[],
  p_loc_text text default null::text, p_loc_map text default null::text,
  p_notes text default null::text, p_receipt_path text default null::text)
returns TABLE(ref text, public_token uuid, the_date date, start_time time without time zone, price numeric)
language plpgsql security definer set search_path to 'public', 'pg_temp'
as $function$
declare
  v_open      boolean;
  v_phone     text;
  v_name      text;
  v_receipt   text;
  v_rate      numeric;
  v_guard     boolean;
  v_dur       integer := 0;
  v_total     numeric(10,2) := 0;
  v_dep       numeric(10,2) := 0;
  v_grp       integer := 0;
  v_disc      numeric(10,2) := 0;
  v_need      numeric(10,2);
  v_state     text;
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

  if v_grp >= 2 then
    v_disc := least(coalesce(v_rate, 0) * v_grp, v_total);
  end if;
  v_need := least(v_dep, greatest(v_total - v_disc, 0));

  -- ── حارس الإيصال ──────────────────────────────────────────────────
  if v_guard and v_need > 0 then
    v_state := public.receipt_state(v_receipt, v_need);
    if v_state = 'wait' then
      raise exception 'لم يكتمل فحص الإيصال، انتظري لحظة ثم أعيدي الإرسال'
        using errcode = 'P0001';
    elsif v_state <> 'ok' then
      -- لا يُقال أيُّ الشرطين سقط: من عرف السبب صنع صورةً تتجاوزه.
      raise exception 'الإيصال غير صحيح' using errcode = 'P0001';
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
