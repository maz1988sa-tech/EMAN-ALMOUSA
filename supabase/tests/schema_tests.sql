\set ON_ERROR_STOP on
\pset border 2
-- Deterministic baseline: Saturday 2026-09-05, one window 16:00-22:00, step 30, travel 40.
delete from public.availability_rules;
insert into public.availability_rules (weekday, start_time, end_time) values (6, '16:00', '22:00');
update public.settings set min_lead_hours = 0, slot_step_min = 30, travel_buffer_min = 40;

\echo '### 1. Empty Saturday, 60-min job -> every slot that fits before 22:00'
select string_agg(slot::text, ' ' order by slot) as slots from public.available_slots('2026-09-05', 60);

\echo '### 2. Same day, 240-min group -> far fewer slots (duration is honoured)'
select string_agg(slot::text, ' ' order by slot) as slots from public.available_slots('2026-09-05', 240);

\echo '### 3. Sunday has no rule -> no slots'
select count(*) as sunday_slots from public.available_slots('2026-09-06', 60);
\pset border 2
\echo '### 6. Phone normalisation — every format a Saudi client actually types'
do $$
declare f text; ok int := 0; bad text := '';
begin
  foreach f in array array['0501234567','+966501234567','00966501234567','966501234567',
                           '050 123 4567','050-123-4567','٠٥٠١٢٣٤٥٦٧'] loop
    begin
      perform public.create_booking('اختبار الجوال', f, '2026-09-05', '21:00',
        array[(select id from public.services where icon='evening')]);
      ok := ok + 1;
      delete from public.bookings where client_name = 'اختبار الجوال';
    exception when others then bad := bad || f || ' -> ' || SQLERRM || E'\n';
    end;
  end loop;
  raise notice 'accepted % of 7 formats', ok;
  if bad <> '' then raise notice 'REJECTED:%', E'\n' || bad; end if;
end $$;

\echo '### 7. Junk phone numbers must be refused'
do $$
declare f text;
begin
  foreach f in array array['0401234567','12345','05012345678','abcdefghij'] loop
    begin
      perform public.create_booking('رفض', f, '2026-09-05', '21:00',
        array[(select id from public.services where icon='evening')]);
      raise notice 'LEAK: % was accepted', f;
    exception when others then raise notice 'refused % (correct)', f;
    end;
  end loop;
end $$;

\echo '### 8. A stale page tries to book the already-taken 18:00'
do $$
begin
  perform public.create_booking('متأخرة','0559998888','2026-09-05','18:00',
    array[(select id from public.services where icon='bride')]);
  raise notice 'LEAK: double booking accepted';
exception when others then raise notice 'refused (correct): %', SQLERRM;
end $$;

\echo '### 9. Booking a time the artist never works'
do $$
begin
  perform public.create_booking('خارج الدوام','0559998888','2026-09-05','09:00',
    array[(select id from public.services where icon='bride')]);
  raise notice 'LEAK: out-of-hours accepted';
exception when others then raise notice 'refused (correct): %', SQLERRM;
end $$;
\pset border 2
\echo '### 10. As anon: try every way to reach the client list'
set role anon;
do $$
declare n int; leaked text := '';
begin
  begin select count(*) into n from public.bookings;
        leaked := leaked || format('bookings SELECT returned %s rows; ', n);
  exception when others then raise notice 'bookings SELECT blocked (correct)'; end;

  begin select count(*) into n from public.booking_items;
        leaked := leaked || format('booking_items SELECT returned %s rows; ', n);
  exception when others then raise notice 'booking_items SELECT blocked (correct)'; end;

  begin select count(*) into n from public.settings;
        leaked := leaked || format('settings SELECT returned %s rows; ', n);
  exception when others then raise notice 'settings SELECT blocked (correct)'; end;

  begin select count(*) into n from public.activity_log;
        leaked := leaked || format('activity_log SELECT returned %s rows; ', n);
  exception when others then raise notice 'activity_log SELECT blocked (correct)'; end;

  begin insert into public.bookings (client_name, client_phone, the_date, start_time)
        values ('تسلل','966501111111','2026-09-05','20:00');
        leaked := leaked || 'direct INSERT succeeded; ';
  exception when others then raise notice 'bookings INSERT blocked (correct)'; end;

  begin update public.bookings set status='confirmed';
        leaked := leaked || 'UPDATE succeeded; ';
  exception when others then raise notice 'bookings UPDATE blocked (correct)'; end;

  if leaked <> '' then raise notice '*** LEAK: %', leaked; else raise notice 'no leaks'; end if;
end $$;

\echo '### 11. But anon CAN read the price list and published hours (by design)'
select (select count(*) from public.services) as services,
       (select count(*) from public.availability_rules) as rules,
       (select business_name from public.public_settings) as name;
reset role;
\pset border 2
insert into public.availability_rules (weekday, start_time, end_time) values (6,'16:00','22:00') on conflict do nothing;
\echo '### 12. Group booking on a clear Saturday: bride + 2 evening = 150 min'
select ref, start_time, price from public.create_booking(
  'ريم القحطاني','0555554444','2026-09-12','16:00',
  array[(select id from public.services where icon='bride'),
        (select id from public.services where icon='evening'),
        (select id from public.services where icon='evening')],
  array['ريم','سارة','هند']);

\echo '### 13. Totals and duration derived from the people, never typed'
select b.duration_min, b.items_total, b.price,
       (select count(*) from public.booking_items i where i.booking_id=b.id) as people
from public.bookings b where b.client_name='ريم القحطاني';

\echo '### 14. Discount via price_override (items sum 2700 -> charge 2200)'
update public.bookings set price_override = 2200 where client_name='ريم القحطاني';
select items_total, price_override, price from public.bookings where client_name='ريم القحطاني';

\echo '### 15. Line items keep their own real prices — summary and detail never contradict'
select person_name, service_name, price from public.booking_items
where booking_id=(select id from public.bookings where client_name='ريم القحطاني') order by sort;

\echo '### 16. Deposit above the total is clamped'
update public.bookings set deposit = 9999 where client_name='ريم القحطاني';
select price, deposit from public.bookings where client_name='ريم القحطاني';

\echo '### 17. Remove a person -> totals re-derive'
delete from public.booking_items where person_name='هند';
update public.bookings set price_override = null where client_name='ريم القحطاني';
select duration_min, items_total, price, deposit from public.bookings where client_name='ريم القحطاني';
\pset border 2
delete from public.availability_rules;
insert into public.availability_rules (weekday,start_time,end_time) values (6,'16:00','22:00');
update public.settings set min_lead_hours=0;
update public.services set price=1500, duration_min=60 where icon='bride';
update public.services set price=600,  duration_min=45 where icon='evening';
select ref from public.create_booking('ريم','0555554444','2026-09-12','16:00',
  array[(select id from public.services where icon='bride'),
        (select id from public.services where icon='evening')], array['ريم','سارة']);

\echo '### 16a. Deposit typed above the total is now clamped, not rejected'
update public.bookings set deposit=9999 where client_name='ريم';
select price, deposit from public.bookings where client_name='ريم';

\echo '### 16b. A real partial deposit is kept exactly as entered'
update public.bookings set deposit=700 where client_name='ريم';
select price, deposit from public.bookings where client_name='ريم';

\echo '### 16c. Removing a person drops the total BELOW the deposit -> deposit follows'
delete from public.booking_items where person_name='ريم';
select duration_min, items_total, price, deposit from public.bookings where client_name='ريم';

\echo '### 16d. Negative deposit is floored at zero'
update public.bookings set deposit=-50 where client_name='ريم';
select deposit from public.bookings where client_name='ريم';
\pset border 2
\echo '### 18. The client tracking link returns only her own booking'
select ref, client_name, the_date, status, price, jsonb_array_length(items) as people
from public.get_booking_by_token((select public_token from public.bookings where client_name='ريم'));

\echo '### 19. A guessed/wrong token returns nothing at all'
select count(*) as rows_returned from public.get_booking_by_token('00000000-0000-0000-0000-000000000000');

\echo '### 20. Day off beats the weekly rule'
insert into public.date_overrides (the_date, kind, note) values ('2026-09-19','closed','إجازة');
select count(*) as slots_on_day_off from public.available_slots('2026-09-19', 60);

\echo '### 21. Special hours for one date beat the weekly rule'
insert into public.date_overrides (the_date, kind, start_time, end_time, note)
values ('2026-09-26','custom','09:00','12:00','دوام صباحي استثنائي');
select string_agg(slot::text,' ' order by slot) as morning_slots from public.available_slots('2026-09-26', 60);

\echo '### 22. Morning appointments work — the old system could not book these at all'
select count(*) as am_slots from public.available_slots('2026-09-26',60) where slot < '12:00';

\echo '### 23. Lead time: with 48h notice required, tomorrow is unbookable'
update public.settings set min_lead_hours=48;
select (select count(*) from public.available_slots(public.local_today()+1,60)) as tomorrow,
       (select count(*) from public.available_slots('2026-09-12',60))          as far_future;
update public.settings set min_lead_hours=0;

\echo '### 24. Beyond the booking horizon nothing is offered'
select count(*) as beyond_horizon from public.available_slots(public.local_today()+400, 60);

\echo '### 25. Week strip for the client page — counts only, no names'
select the_date, slot_count from public.days_with_availability('2026-09-12', 7, 60);
