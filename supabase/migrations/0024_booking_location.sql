-- الحكم في موضعه: `create_booking` تُطبّق شرط الحيّ بنفسها.
--
-- الفحص المسبق (`check_location`) للعرض وحده. ولو اكتُفي به لأمكن تجاوزه
-- من أدوات المطوّر: تُحذف نافذة الشرط ويُرسل الحجز. فالقاعدة تُعيد
-- الحساب من الإحداثيّتين لا من شيءٍ أرسله المتصفّح.
--
-- والحارس مُطفأ حتى تُشعله صاحبة العمل (`settings.loc_check_enabled`)،
-- فلا يتغيّر شيء على العميلات قبل أن تضبط الأحياء وشروطها.

drop function if exists public.create_booking(
  text, text, date, time without time zone, uuid[], text[], text, text, text, text);

create function public.create_booking(
  p_client_name text, p_client_phone text, p_date date, p_time time without time zone,
  p_service_ids uuid[], p_person_names text[] default null::text[],
  p_loc_text text default null::text, p_loc_map text default null::text,
  p_notes text default null::text, p_receipt_path text default null::text,
  p_lat numeric default null, p_lng numeric default null)
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
  v_locchk    boolean;
  v_dur       integer := 0;
  v_total     numeric(10,2) := 0;
  v_dep       numeric(10,2) := 0;
  v_grp       integer := 0;
  v_disc      numeric(10,2) := 0;
  v_need      numeric(10,2);
  v_state     text;
  v_people    integer;
  v_loc       jsonb;
  v_fee       numeric(10,2) := 0;
  v_dname     text;
  v_did       bigint;
  v_booking   public.bookings%rowtype;
  v_service   public.services%rowtype;
  v_id        uuid;
  i           integer;
begin
  select accepting_bookings, group_discount_amount, receipt_ocr_required, loc_check_enabled
    into v_open, v_rate, v_guard, v_locchk
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
  v_people := array_length(p_service_ids, 1);

  -- ── شرط الحيّ ─────────────────────────────────────────────────────
  -- يقول سببه: العميلة لا تختار حيَّها فلا شيء يُزوَّر، وكتمانُ السبب
  -- يجعلها تظنّ بالمنصّة عطبًا. (يقابله حارس الإيصال الذي يكتم — §٦.)
  if coalesce(v_locchk, false) then
    if p_lat is null or p_lng is null then
      raise exception 'نحتاج تحديد موقعك على الخريطة لإتمام الحجز'
        using errcode = 'P0001';
    end if;
    v_loc := public.check_location(p_lat, p_lng, v_people);
    if v_loc->>'state' in ('reject', 'blocked') then
      raise exception '%', coalesce(nullif(btrim(v_loc->>'message'), ''),
                                    'لا نستقبل حجوزات في هذا الموقع حاليًا.')
        using errcode = 'P0001';
    end if;
    v_fee   := coalesce((v_loc->>'fee')::numeric, 0);
    v_dname := v_loc->>'district';
    v_did   := nullif(v_loc->>'district_id', '')::bigint;
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
  -- العربون على الخدمات وحدها: الرسوم تُحصَّل يوم الموعد، فلا يرتفع
  -- المطلوب تحويله ولا يختلف عمّا فحصه حارس الإيصال.
  v_need := least(v_dep, greatest(v_total - v_disc, 0));

  if v_guard and v_need > 0 then
    v_state := public.receipt_state(v_receipt, v_need);
    if v_state = 'wait' then
      raise exception 'لم يكتمل فحص الإيصال، انتظري لحظة ثم أعيدي الإرسال'
        using errcode = 'P0001';
    elsif v_state <> 'ok' then
      raise exception 'الإيصال غير صحيح' using errcode = 'P0001';
    end if;
  end if;

  if not exists (select 1 from public.available_slots(p_date, v_dur) s where s.slot = p_time) then
    raise exception 'هذا الموعد لم يعد متاحًا، اختاري وقتًا آخر' using errcode = 'P0001';
  end if;

  insert into public.bookings (
    client_name, client_phone, the_date, start_time, duration_min,
    status, source, loc_text, loc_map, client_notes, receipt_path,
    discount_per_person, loc_fee, loc_district, loc_district_id
  ) values (
    v_name, v_phone, p_date, p_time, greatest(v_dur, 15),
    'pending', 'client', nullif(btrim(coalesce(p_loc_text, '')), ''),
    nullif(btrim(coalesce(p_loc_map, '')), ''), nullif(btrim(coalesce(p_notes, '')), ''),
    v_receipt, coalesce(v_rate, 0), v_fee, v_dname, v_did
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
                             'receipt_checked', coalesce(v_guard, false),
                             'district', v_dname, 'loc_fee', v_fee));

  select * into v_booking from public.bookings where id = v_id;

  ref          := v_booking.ref;
  public_token := v_booking.public_token;
  the_date     := v_booking.the_date;
  start_time   := v_booking.start_time;
  price        := v_booking.price;
  return next;
end;
$function$;

revoke all on function public.create_booking(
  text, text, date, time without time zone, uuid[], text[], text, text, text, text,
  numeric, numeric) from public;
grant execute on function public.create_booking(
  text, text, date, time without time zone, uuid[], text[], text, text, text, text,
  numeric, numeric) to anon, authenticated;

/* ═══ اللقطة تشمل الجديد ═══════════════════════════════════════════════
   `snapshot_coverage.sql` يقارن مفاتيح اللقطة بجداول المخطّط، فجدولان
   جديدان بلا مفتاحٍ يُسقطانه. وهذا ما يُبقي النسخة كاملة بلا تذكّر. */

create or replace function public.admin_snapshot()
returns jsonb
language plpgsql stable security definer set search_path to 'public', 'pg_temp'
as $fn$
declare v jsonb;
begin
  if not public.is_admin() then
    raise exception 'not authorised' using errcode = '42501';
  end if;

  select jsonb_build_object(
    'version', 2,
    'taken_at', now(),
    'settings',           (select to_jsonb(s) from public.settings s where s.id = 1),
    'services',           coalesce((select jsonb_agg(to_jsonb(x) order by x.sort)       from public.services x), '[]'::jsonb),
    'availability_rules', coalesce((select jsonb_agg(to_jsonb(x))                       from public.availability_rules x), '[]'::jsonb),
    'date_overrides',     coalesce((select jsonb_agg(to_jsonb(x) order by x.the_date)   from public.date_overrides x), '[]'::jsonb),
    'bookings',           coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at) from public.bookings x), '[]'::jsonb),
    'booking_items',      coalesce((select jsonb_agg(to_jsonb(x))                       from public.booking_items x), '[]'::jsonb),
    'message_templates',  coalesce((select jsonb_agg(to_jsonb(x) order by x.sort)       from public.message_templates x), '[]'::jsonb),
    'message_outbox',     coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at) from public.message_outbox x), '[]'::jsonb),
    'ref_counters',       coalesce((select jsonb_agg(to_jsonb(x))                       from public.ref_counters x), '[]'::jsonb),
    'visits',             coalesce((select jsonb_agg(to_jsonb(x) order by x.started_at) from public.visits x), '[]'::jsonb),
    'activity_log',       coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at) from public.activity_log x), '[]'::jsonb),
    'districts',          coalesce((select jsonb_agg(to_jsonb(x) order by x.id)         from public.districts x), '[]'::jsonb),
    'district_rules',     coalesce((select jsonb_agg(to_jsonb(x) order by x.district_id) from public.district_rules x), '[]'::jsonb),
    'receipt_scans',      coalesce((select jsonb_agg(to_jsonb(x) - 'raw_text' order by x.scanned_at)
                                      from public.receipt_scans x), '[]'::jsonb)
  ) into v;

  return v || jsonb_build_object('counts', jsonb_build_object(
    'bookings',          jsonb_array_length(v->'bookings'),
    'booking_items',     jsonb_array_length(v->'booking_items'),
    'services',          jsonb_array_length(v->'services'),
    'rules',             jsonb_array_length(v->'availability_rules'),
    'overrides',         jsonb_array_length(v->'date_overrides'),
    'message_templates', jsonb_array_length(v->'message_templates'),
    'message_outbox',    jsonb_array_length(v->'message_outbox'),
    'ref_counters',      jsonb_array_length(v->'ref_counters'),
    'visits',            jsonb_array_length(v->'visits'),
    'activity_log',      jsonb_array_length(v->'activity_log'),
    'districts',         jsonb_array_length(v->'districts'),
    'district_rules',    jsonb_array_length(v->'district_rules'),
    'receipt_scans',     jsonb_array_length(v->'receipt_scans'),
    'receipts',          (select count(*) from public.bookings where receipt_path is not null)
  ));
end $fn$;
revoke all on function public.admin_snapshot() from public, anon;
grant execute on function public.admin_snapshot() to authenticated;
