-- رقم الطلب: يُقرأ، ويتسلسل، ولا يتصادم — يُفحص على القاعدة نفسها ثمّ يُلغى.
do $$
declare
  p    text := to_char(public.local_now(), 'YYYYMM');
  ok   int := 0; bad int := 0;
  msg  text := '';
  procedure_note text;
  r1 text; r2 text; r3 text; r99 text; r100 text; r101 text;
  v_rows int; v_dup int; v_shape int; v_gap int;
begin
  -- ١ الصيغة: EA + سنة + شهر + رقم
  r1 := public.gen_booking_ref();
  if r1 ~ ('^EA-' || p || '[0-9]{2,}$') then ok := ok+1;
  else bad := bad+1; msg := msg || ' ✗صيغة:' || r1; end if;

  -- ٢ يتسلسل واحدًا واحدًا
  r2 := public.gen_booking_ref(); r3 := public.gen_booking_ref();
  if right(r2,2)::int = right(r1,2)::int + 1
     and right(r3,2)::int = right(r2,2)::int + 1 then ok := ok+1;
  else bad := bad+1; msg := msg || ' ✗تسلسل:' || r1 ||','|| r2 ||','|| r3; end if;

  -- ٣ لا يصطدم بما في الجدول
  if not exists (select 1 from public.bookings where ref in (r1,r2,r3)) then ok := ok+1;
  else bad := bad+1; msg := msg || ' ✗تصادم'; end if;

  -- ٤ ما بعد التسعة والتسعين يتّسع ولا يقصّ
  update public.ref_counters set n = 98 where period = p;
  r99 := public.gen_booking_ref(); r100 := public.gen_booking_ref(); r101 := public.gen_booking_ref();
  if r99 = 'EA-'||p||'99' and r100 = 'EA-'||p||'100' and r101 = 'EA-'||p||'101' then ok := ok+1;
  else bad := bad+1; msg := msg || ' ✗فوق99:' || r99 ||','|| r100 ||','|| r101; end if;

  -- ٥ شهرٌ جديد يبدأ من صفر
  delete from public.ref_counters where period = '209901';
  insert into public.ref_counters(period, n) values ('209901', 0);
  if (select n from public.ref_counters where period='209901') = 0 then ok := ok+1;
  else bad := bad+1; msg := msg || ' ✗شهر جديد'; end if;

  -- ٦ كلُّ ما في الجدول بالصيغة الجديدة، بلا تكرار ولا فجوة
  select count(*) into v_rows  from public.bookings;
  select count(*) into v_shape from public.bookings where ref !~ '^EA-[0-9]{8,}$';
  select count(*) into v_dup   from (select ref from public.bookings group by ref having count(*)>1) x;
  select count(*) into v_gap from (
    select substr(ref,4,6) as per,
           count(*) as n,
           max(substr(ref,10)::int) as mx
      from public.bookings group by 1
     having count(*) - 1 <> max(substr(ref,10)::int)) y;
  if v_shape = 0 then ok := ok+1; else bad := bad+1; msg := msg || ' ✗صيغة قديمة:'||v_shape; end if;
  if v_dup   = 0 then ok := ok+1; else bad := bad+1; msg := msg || ' ✗مكرّر:'||v_dup; end if;
  if v_gap   = 0 then ok := ok+1; else bad := bad+1; msg := msg || ' ✗فجوة في شهر'; end if;

  -- ٧ أوّل كلِّ شهر صفر
  if not exists (select 1 from public.bookings group by substr(ref,4,6)
                  having min(substr(ref,10)::int) <> 0) then ok := ok+1;
  else bad := bad+1; msg := msg || ' ✗أوّل الشهر ليس صفرًا'; end if;

  raise exception 'ROLLBACK_OK نجح=% سقط=% · صفوف=%%s', ok, bad, v_rows, msg;
end $$;
