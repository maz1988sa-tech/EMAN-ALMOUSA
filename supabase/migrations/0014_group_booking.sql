-- حجز المجموعة: عدّة عميلاتٍ في مناسبةٍ واحدة، بضغطة حفظٍ واحدة.
--
-- كانت زوجتك تفتح ورقة الإضافة وتغلقها لكلِّ عميلة: أربع دوراتٍ كاملة تُعيد
-- في كلٍّ منها التاريخ والحيّ ورابط الخريطة. والأسوأ أنّ الشبكة قد تقطع بين
-- الثانية والثالثة، فتبقى مناسبةٌ نصفها محجوز ونصفها لا.
--
-- الحجوزات تبقى مستقلّةً كما هي — لكلٍّ رقمُه وسعرُه وبطاقتُه — ويجمعها
-- group_id فتُعرَض كتلةً واحدة تحت اسم المناسبة.

alter table public.bookings
  add column if not exists group_id    uuid,
  add column if not exists group_label text;

create index if not exists bookings_group_idx
  on public.bookings (group_id) where group_id is not null;

-- المجموعة كلُّها في صفقةٍ واحدة: تتمّ أو لا تُبقي أثرًا.
create or replace function public.admin_create_group(
  p_people jsonb,
  p_label  text default null,
  p_idem   uuid default null
)
returns setof public.bookings
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $$
declare
  v_gid uuid;
  v_row public.bookings;
  v_p   jsonb;
  v_ord int := 0;
begin
  if not public.is_admin() then
    raise exception 'not authorised' using errcode = '42501';
  end if;

  if coalesce(jsonb_array_length(p_people), 0) = 0 then
    raise exception 'group needs at least one client' using errcode = '22023';
  end if;

  -- محاولةٌ مكرّرة لمجموعةٍ سبق حفظها: تُردّ كما هي ولا تُنشأ ثانية.
  if p_idem is not null then
    select group_id into v_gid from public.bookings
     where idem_key = p_idem limit 1;
    if v_gid is not null then
      return query select * from public.bookings
                    where group_id = v_gid order by the_date, start_time;
      return;
    end if;
  end if;

  v_gid := gen_random_uuid();

  for v_p in select * from jsonb_array_elements(p_people) loop
    v_ord := v_ord + 1;

    if coalesce(jsonb_array_length(v_p->'items'), 0) = 0 then
      raise exception 'client % has no services', v_ord using errcode = '22023';
    end if;

    insert into public.bookings (
      client_name, client_phone, the_date, start_time, duration_min, status,
      source, loc_text, loc_map, client_notes, admin_notes,
      discount_per_person, deposit, confirmed_at, group_id, group_label,
      idem_key
    )
    select
      v_p->>'client_name',
      v_p->>'client_phone',
      (v_p->>'the_date')::date,
      (v_p->>'start_time')::time,
      coalesce((v_p->>'duration_min')::integer, 45),
      coalesce((v_p->>'status')::public.booking_status, 'confirmed'),
      'admin',
      nullif(v_p->>'loc_text', ''),
      nullif(v_p->>'loc_map', ''),
      nullif(v_p->>'client_notes', ''),
      nullif(v_p->>'admin_notes', ''),
      coalesce((v_p->>'discount_per_person')::numeric, 0),
      greatest(coalesce((v_p->>'deposit')::numeric, 0), 0),
      coalesce((v_p->>'confirmed_at')::timestamptz, now()),
      v_gid,
      nullif(p_label, ''),
      -- المفتاح على الأولى وحدها: وجودُه يدلّ على المجموعة كلّها.
      case when v_ord = 1 then p_idem else null end
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
    from jsonb_array_elements(v_p->'items') with ordinality as t(it, ord);
  end loop;

  return query select * from public.bookings
                where group_id = v_gid order by the_date, start_time;
end;
$$;

grant execute on function public.admin_create_group(jsonb, text, uuid) to authenticated;
