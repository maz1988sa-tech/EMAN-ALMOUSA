-- Schema tests. Self-contained and order-independent: every section resets
-- the state it depends on, so the file can be run whole or re-run at will.
\set ON_ERROR_STOP on
\pset border 2

-- ── Baseline ───────────────────────────────────────────────────────────────
-- 2026-09-05 and 2026-09-12 are Saturdays; 2026-09-06 is a Sunday.
delete from public.booking_items;
delete from public.activity_log;
delete from public.bookings;
delete from public.date_overrides;
delete from public.availability_rules;
insert into public.availability_rules (weekday, start_time, end_time) values (6, '16:00', '22:00');
update public.settings
   set min_lead_hours = 0, slot_step_min = 30, travel_buffer_min = 40,
       max_advance_days = 365, accepting_bookings = true;
update public.services set price = 1500, duration_min = 60 where icon = 'bride';
update public.services set price =  600, duration_min = 45 where icon = 'evening';

\echo ''
\echo '=== Availability ==========================================='

\echo '--- 1. Empty Saturday, 60-min job: every slot whose job ends by 22:00'
select string_agg(slot::text, ' ' order by slot) as slots
from public.available_slots('2026-09-05', 60);

\echo '--- 2. Same day, 240-min group: far fewer slots (duration is honoured)'
select string_agg(slot::text, ' ' order by slot) as slots
from public.available_slots('2026-09-05', 240);

\echo '--- 3. A weekday with no rule offers nothing'
select count(*) as sunday_slots from public.available_slots('2026-09-06', 60);

\echo ''
\echo '=== Booking and conflicts =================================='

\echo '--- 4. A client books a bride at 18:00'
select ref, the_date, start_time, price from public.create_booking(
  'نورة العتيبي', '0501234567', '2026-09-05', '18:00',
  array[(select id from public.services where icon = 'bride')]);

\echo '--- 5. That job (60m) plus travel (40m) blocks 18:00-19:40 both ways'
select string_agg(slot::text, ' ' order by slot) as remaining
from public.available_slots('2026-09-05', 60);

\echo '--- 6. A stale page cannot rebook the taken 18:00'
do $$ begin
  perform public.create_booking('متأخرة', '0559998888', '2026-09-05', '18:00',
    array[(select id from public.services where icon = 'bride')]);
  raise notice 'FAIL: double booking accepted';
exception when others then raise notice 'PASS: refused — %', SQLERRM; end $$;

\echo '--- 7. Nor a time outside the working window'
do $$ begin
  perform public.create_booking('خارج الدوام', '0559998888', '2026-09-05', '09:00',
    array[(select id from public.services where icon = 'bride')]);
  raise notice 'FAIL: out-of-hours accepted';
exception when others then raise notice 'PASS: refused — %', SQLERRM; end $$;

\echo '--- 8. A 150-min group cannot start where only 60 min is free'
do $$ begin
  perform public.create_booking('مجموعة', '0559998888', '2026-09-05', '16:00',
    array[(select id from public.services where icon = 'bride'),
          (select id from public.services where icon = 'evening'),
          (select id from public.services where icon = 'evening')]);
  raise notice 'FAIL: oversized group squeezed into a short gap';
exception when others then raise notice 'PASS: refused — %', SQLERRM; end $$;

\echo ''
\echo '=== Phone normalisation ==================================='

\echo '--- 9. Seven ways a Saudi client writes the same number'
do $$
declare f text; ok int := 0; bad text := '';
begin
  foreach f in array array['0501234567', '+966501234567', '00966501234567',
                           '966501234567', '050 123 4567', '050-123-4567', '٠٥٠١٢٣٤٥٦٧'] loop
    begin
      perform public.create_booking('اختبار', f, '2026-09-12', '16:00',
        array[(select id from public.services where icon = 'evening')]);
      ok := ok + 1;
      delete from public.bookings where client_name = 'اختبار';
    exception when others then bad := bad || f || ' -> ' || SQLERRM || '; ';
    end;
  end loop;
  raise notice '% accepted % of 7 formats', case when ok = 7 then 'PASS:' else 'FAIL:' end, ok;
  if bad <> '' then raise notice '  rejected: %', bad; end if;
end $$;

\echo '--- 10. Junk numbers are refused'
do $$
declare f text; leaked text := '';
begin
  foreach f in array array['0401234567', '12345', '05012345678', 'abcdefghij'] loop
    begin
      perform public.create_booking('رفض', f, '2026-09-12', '16:00',
        array[(select id from public.services where icon = 'evening')]);
      leaked := leaked || f || ' ';
      delete from public.bookings where client_name = 'رفض';
    exception when others then null;
    end;
  end loop;
  if leaked = '' then raise notice 'PASS: all four refused';
  else raise notice 'FAIL: accepted %', leaked; end if;
end $$;

\echo ''
\echo '=== Group bookings and money ==============================='

\echo '--- 11. Group on a clear Saturday: bride + 2 evening = 150 min'
select ref, start_time, price from public.create_booking(
  'ريم القحطاني', '0555554444', '2026-09-12', '16:00',
  array[(select id from public.services where icon = 'bride'),
        (select id from public.services where icon = 'evening'),
        (select id from public.services where icon = 'evening')],
  array['ريم', 'سارة', 'هند']);

\echo '--- 12. Totals and duration derive from the people, never typed twice'
select duration_min, items_total, price,
       (select count(*) from public.booking_items i where i.booking_id = b.id) as people
from public.bookings b where b.client_name = 'ريم القحطاني';

\echo '--- 13. A discount is its own number; line items keep their real prices'
update public.bookings set price_override = 2200 where client_name = 'ريم القحطاني';
select items_total, price_override, price from public.bookings where client_name = 'ريم القحطاني';
select person_name, service_name, price from public.booking_items
where booking_id = (select id from public.bookings where client_name = 'ريم القحطاني')
order by sort;

\echo '--- 14. A deposit above the total is clamped, not rejected'
update public.bookings set deposit = 9999 where client_name = 'ريم القحطاني';
select price, deposit from public.bookings where client_name = 'ريم القحطاني';

\echo '--- 15. A real partial deposit is kept exactly'
update public.bookings set deposit = 700 where client_name = 'ريم القحطاني';
select price, deposit from public.bookings where client_name = 'ريم القحطاني';

\echo '--- 16. Removing a person re-derives the total; deposit follows it down'
delete from public.booking_items where person_name = 'ريم';
update public.bookings set price_override = null where client_name = 'ريم القحطاني';
select duration_min, items_total, price, deposit from public.bookings where client_name = 'ريم القحطاني';

\echo '--- 17. A negative deposit floors at zero'
update public.bookings set deposit = -50 where client_name = 'ريم القحطاني';
select deposit from public.bookings where client_name = 'ريم القحطاني';

\echo ''
\echo '=== Client tracking link ==================================='

\echo '--- 18. The token returns that one booking, with its items'
select ref, client_name, status, price, jsonb_array_length(items) as people
from public.get_booking_by_token(
  (select public_token from public.bookings where client_name = 'ريم القحطاني'));

\echo '--- 19. A wrong token returns nothing'
select count(*) as rows_returned
from public.get_booking_by_token('00000000-0000-0000-0000-000000000000');

\echo '--- 20. A cancellation request flags, never deletes'
select public.request_cancel(
  (select public_token from public.bookings where client_name = 'ريم القحطاني')) as accepted;
select cancel_requested, status from public.bookings where client_name = 'ريم القحطاني';

\echo ''
\echo '=== Schedule overrides ====================================='

\echo '--- 21. A day off beats the weekly rule'
insert into public.date_overrides (the_date, kind, note) values ('2026-09-19', 'closed', 'إجازة');
select count(*) as slots_on_day_off from public.available_slots('2026-09-19', 60);

\echo '--- 22. Special hours for one date beat the weekly rule — mornings work'
insert into public.date_overrides (the_date, kind, start_time, end_time, note)
values ('2026-09-26', 'custom', '09:00', '12:00', 'دوام صباحي');
select string_agg(slot::text, ' ' order by slot) as morning_slots
from public.available_slots('2026-09-26', 60);

\echo '--- 23. Lead time and the booking horizon are both respected'
update public.settings set min_lead_hours = 48;
select (select count(*) from public.available_slots(public.local_today() + 1, 60))   as tomorrow_should_be_0,
       (select count(*) from public.available_slots('2026-09-05', 60))               as far_future_ok;
update public.settings set min_lead_hours = 0, max_advance_days = 120;
select count(*) as beyond_horizon from public.available_slots(public.local_today() + 400, 60);
update public.settings set max_advance_days = 365;

\echo ''
\echo '=== Security ==============================================='

\echo '--- 24. As anon: every route to the client list is closed'
do $$
declare n int; leaked text := '';
begin
  set local role anon;
  begin select count(*) into n from public.bookings;
        leaked := leaked || format('bookings SELECT -> %s rows; ', n);
  exception when others then null; end;
  begin select count(*) into n from public.booking_items;
        leaked := leaked || format('booking_items SELECT -> %s rows; ', n);
  exception when others then null; end;
  begin select count(*) into n from public.settings;
        leaked := leaked || format('settings SELECT -> %s rows; ', n);
  exception when others then null; end;
  begin select count(*) into n from public.activity_log;
        leaked := leaked || format('activity_log SELECT -> %s rows; ', n);
  exception when others then null; end;
  begin select count(*) into n from public.admins;
        leaked := leaked || format('admins SELECT -> %s rows; ', n);
  exception when others then null; end;
  begin insert into public.bookings (client_name, client_phone, the_date, start_time)
        values ('تسلل', '966501111111', '2026-09-05', '20:00');
        leaked := leaked || 'direct INSERT succeeded; ';
  exception when others then null; end;
  begin update public.bookings set status = 'confirmed';
        if found then leaked := leaked || 'UPDATE succeeded; '; end if;
  exception when others then null; end;
  reset role;
  if leaked = '' then raise notice 'PASS: anon reached nothing';
  else raise notice 'FAIL: %', leaked; end if;
end $$;

\echo '--- 25. But anon does get the price list and the published hours'
begin;
set local role anon;
select (select count(*) from public.services)           as services,
       (select count(*) from public.availability_rules) as rules,
       (select business_name from public.public_settings) as business;
commit;

\echo '--- 26. Signing in is not enough — admin rights need the allowlist'
insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'eman@example.com'),
  ('22222222-2222-2222-2222-222222222222', 'stranger@example.com')
on conflict (id) do nothing;
insert into public.admins (user_id, email)
values ('11111111-1111-1111-1111-111111111111', 'eman@example.com')
on conflict (user_id) do nothing;

do $$
declare n int; problems text := '';
begin
  -- Someone who signed themselves up with the public key.
  perform set_config('request.jwt.claim.sub', '22222222-2222-2222-2222-222222222222', true);
  set local role authenticated;
  select count(*) into n from public.bookings;
  if n > 0 then problems := problems || format('stranger read %s bookings; ', n); end if;
  update public.bookings set status = 'cancelled';
  if found then problems := problems || 'stranger could update; '; end if;
  select count(*) into n from public.settings;
  if n > 0 then problems := problems || format('stranger read settings (%s); ', n); end if;
  reset role;

  -- The real administrator.
  perform set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', true);
  set local role authenticated;
  select count(*) into n from public.bookings;
  if n = 0 then problems := problems || 'ADMIN LOCKED OUT; '; end if;
  reset role;

  if problems = '' then raise notice 'PASS: stranger sees nothing, admin sees everything';
  else raise notice 'FAIL: %', problems; end if;
end $$;

\echo ''
\echo '=== done ==================================================='

\echo '--- 27. anon may execute the five public functions and nothing else'
do $$
declare r record; problems text := '';
  expected constant text[] := array['available_slots','create_booking',
    'days_with_availability','get_booking_by_token','request_cancel'];
begin
  for r in
    select p.proname,
           has_function_privilege('anon', p.oid, 'execute') as anon_may
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      -- only the functions this schema defines; on Supabase pgcrypto lives in
      -- `extensions`, but a local `create extension` puts it in public.
      and p.proname = any(array[
        'available_slots','create_booking','days_with_availability',
        'get_booking_by_token','request_cancel','recalc_booking',
        'gen_booking_ref','bookings_set_ref','booking_items_sync',
        'bookings_apply_override','busy_intervals','day_windows',
        'local_now','local_today','is_admin'])
  loop
    if r.anon_may and not (r.proname = any(expected)) then
      problems := problems || format('anon can call %s; ', r.proname);
    elsif not r.anon_may and r.proname = any(expected) then
      problems := problems || format('anon CANNOT call %s; ', r.proname);
    end if;
  end loop;
  if problems = '' then raise notice 'PASS: anon execute surface is exactly the five entry points';
  else raise notice 'FAIL: %', problems; end if;
end $$;
