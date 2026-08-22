-- الكتابة الإدارية: صفقةٌ واحدة، ومفتاحٌ يمنع تكرارها.
--
-- كانت اللوحة تكتب الحجز ثمّ بنوده في طلبين منفصلين، وهي الطريق الوحيد في
-- النظام الذي يكتب في الجداول مباشرة. نتج عن ذلك عيبان:
--
--   الأوّل أنّ المشغّلات تعمل عندئذٍ بصلاحيات المستخدمة نفسها، فكان الحفظ
--   يسقط بـ permission denied for function gen_booking_ref حتى مُنحت.
--
--   والثاني أخطر: على شبكة الجوّال قد ينجح الطلب الأوّل ويسقط الثاني،
--   فيبقى في الأجندة حجزٌ بلا خدمات ولا سعر — ولا شيء يدلّ على نقصه.
--
-- الدالّتان أدناه تجعلان الكتابة كلّها صفقة واحدة تتمّ أو لا تُبقي أثرًا،
-- وتعملان بصلاحية المالك فتستغنيان عن المنح لكل مشغّل. وبما أنّ المتصفّح
-- لا يفرّق بين طلبٍ لم يصل وطلبٍ وصل وضاع جوابه، تحمل الأولى مفتاح تكرار
-- تولّده اللوحة مرّة وتُعيده مع كل محاولة: فإن كان الحجز قد تمّ رُدّ كما هو.

alter table public.bookings
  add column if not exists idem_key uuid;

create unique index if not exists bookings_idem_key_uidx
  on public.bookings (idem_key) where idem_key is not null;

create or replace function public.admin_create_booking(
  p_booking jsonb,
  p_items   jsonb,
  p_idem    uuid default null
)
returns public.bookings
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $$
declare
  v_row public.bookings;
begin
  -- الدالة تتجاوز سياسات الصفوف، فالبوّابة هنا صراحةً.
  if not public.is_admin() then
    raise exception 'not authorised' using errcode = '42501';
  end if;

  if coalesce(jsonb_array_length(p_items), 0) = 0 then
    raise exception 'booking needs at least one item' using errcode = '22023';
  end if;

  -- محاولةٌ مكرّرة لطلبٍ سبق أن تمّ: يُردّ الحجز نفسه، ولا يُنشأ غيره.
  if p_idem is not null then
    select * into v_row from public.bookings where idem_key = p_idem;
    if found then return v_row; end if;
  end if;

  insert into public.bookings (
    client_name, client_phone, the_date, start_time, duration_min, status,
    source, loc_text, loc_map, client_notes, admin_notes,
    discount_per_person, confirmed_at, idem_key
  )
  select
    p_booking->>'client_name',
    p_booking->>'client_phone',
    (p_booking->>'the_date')::date,
    (p_booking->>'start_time')::time,
    coalesce((p_booking->>'duration_min')::integer, 45),
    coalesce((p_booking->>'status')::public.booking_status, 'confirmed'),
    'admin',
    nullif(p_booking->>'loc_text', ''),
    nullif(p_booking->>'loc_map', ''),
    nullif(p_booking->>'client_notes', ''),
    nullif(p_booking->>'admin_notes', ''),
    coalesce((p_booking->>'discount_per_person')::numeric, 0),
    coalesce((p_booking->>'confirmed_at')::timestamptz, now()),
    p_idem
  returning * into v_row;

  insert into public.booking_items (
    booking_id, service_id, service_name, service_icon, person_name,
    price, duration_min, group_discount, deposit_amount, sort
  )
  select
    v_row.id,
    nullif(it->>'service_id', '')::uuid,
    it->>'service_name',
    -- تمرير NULL صراحةً يُبطل قيمة العمود الافتراضية، وهو إلزامي.
    coalesce(nullif(it->>'service_icon', ''), 'sparkle'),
    nullif(it->>'person_name', ''),
    coalesce((it->>'price')::numeric, 0),
    coalesce((it->>'duration_min')::integer, 45),
    coalesce((it->>'group_discount')::boolean, false),
    coalesce((it->>'deposit_amount')::numeric, 0),
    ord
  from jsonb_array_elements(p_items) with ordinality as t(it, ord);

  -- المشغّلات حدّثت المجاميع بعد إدراج البنود، فنقرأ الصفّ ثانيةً.
  select * into v_row from public.bookings where id = v_row.id;
  return v_row;
end;
$$;

-- استبدال بنود حجزٍ قائم، بالمنطق نفسه: حذفٌ وإدراجٌ وتحديث في صفقة واحدة،
-- فلا يبقى حجزٌ فارغًا إن سقطت الشبكة بين الحذف والإدراج.
create or replace function public.admin_replace_items(
  p_booking_id uuid,
  p_items      jsonb,
  p_discount_per_person numeric default null
)
returns public.bookings
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $$
declare
  v_row public.bookings;
begin
  if not public.is_admin() then
    raise exception 'not authorised' using errcode = '42501';
  end if;

  if coalesce(jsonb_array_length(p_items), 0) = 0 then
    raise exception 'booking needs at least one item' using errcode = '22023';
  end if;

  delete from public.booking_items where booking_id = p_booking_id;

  insert into public.booking_items (
    booking_id, service_id, service_name, service_icon, person_name,
    price, duration_min, group_discount, deposit_amount, sort
  )
  select
    p_booking_id,
    nullif(it->>'service_id', '')::uuid,
    it->>'service_name',
    coalesce(nullif(it->>'service_icon', ''), 'sparkle'),
    nullif(it->>'person_name', ''),
    coalesce((it->>'price')::numeric, 0),
    coalesce((it->>'duration_min')::integer, 45),
    coalesce((it->>'group_discount')::boolean, false),
    coalesce((it->>'deposit_amount')::numeric, 0),
    ord
  from jsonb_array_elements(p_items) with ordinality as t(it, ord);

  if p_discount_per_person is not null then
    update public.bookings set discount_per_person = p_discount_per_person
     where id = p_booking_id;
    perform public.recalc_booking(p_booking_id);
  end if;

  select * into v_row from public.bookings where id = p_booking_id;
  return v_row;
end;
$$;

-- النسخة ذات الوسيطين تُزال حتى لا يبقى طريقان أحدهما بلا حماية التكرار.
drop function if exists public.admin_create_booking(jsonb, jsonb);

revoke all on function public.admin_create_booking(jsonb, jsonb, uuid)     from public;
revoke all on function public.admin_replace_items(uuid, jsonb, numeric)    from public;
grant execute on function public.admin_create_booking(jsonb, jsonb, uuid)  to authenticated;
grant execute on function public.admin_replace_items(uuid, jsonb, numeric) to authenticated;
