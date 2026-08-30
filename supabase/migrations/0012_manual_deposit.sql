-- العربون في الحجز اليدوي.
--
-- حين تُسجِّل زوجتك حجزًا بيدها — واتساب أو اتصال — تكون العميلة قد حوّلت
-- عربونًا قبل ذلك في الغالب. وكانت اللوحة تحفظ الحجز بعربونٍ صفر دائمًا:
-- لا مكان لكتابته في ورقة الإضافة، ولا سبيل إليه بعدها إلّا بفتح الحجز
-- وتعديله. فيظهر المتبقّي خطأً في رسالة التأكيد وفي تقرير الدخل.
--
-- العمود موجود منذ البداية، والمشغّل يحرسه (لا يتجاوز السعر ولا ينزل عن
-- صفر)؛ الناقص أنّ الدالّة الذرّية لم تكن تمرّره. هذا كلّ ما تفعله هذه
-- الهجرة: تضيف deposit إلى الأعمدة المكتوبة.

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
  if not public.is_admin() then
    raise exception 'not authorised' using errcode = '42501';
  end if;

  if coalesce(jsonb_array_length(p_items), 0) = 0 then
    raise exception 'booking needs at least one item' using errcode = '22023';
  end if;

  if p_idem is not null then
    select * into v_row from public.bookings where idem_key = p_idem;
    if found then return v_row; end if;
  end if;

  insert into public.bookings (
    client_name, client_phone, the_date, start_time, duration_min, status,
    source, loc_text, loc_map, client_notes, admin_notes,
    discount_per_person, deposit, confirmed_at, idem_key
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
    -- المشغّل يقصُّه إلى السعر إن زاد، فلا حاجة لحدٍّ هنا.
    greatest(coalesce((p_booking->>'deposit')::numeric, 0), 0),
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
    coalesce(nullif(it->>'service_icon', ''), 'sparkle'),
    nullif(it->>'person_name', ''),
    coalesce((it->>'price')::numeric, 0),
    coalesce((it->>'duration_min')::integer, 45),
    coalesce((it->>'group_discount')::boolean, false),
    coalesce((it->>'deposit_amount')::numeric, 0),
    ord
  from jsonb_array_elements(p_items) with ordinality as t(it, ord);

  -- البنود حرّكت المجاميع، والعربون قد يكون قُصَّ إلى السعر: نقرأ ثانيةً.
  select * into v_row from public.bookings where id = v_row.id;
  return v_row;
end;
$$;

grant execute on function public.admin_create_booking(jsonb, jsonb, uuid) to authenticated;
