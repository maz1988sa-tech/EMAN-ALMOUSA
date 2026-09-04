-- فحص محرّك الرسائل التلقائية على القاعدة الحيّة، بلا أثر.
--
-- كل ما فيه داخل do-block يرفع استثناءً في آخره، فتُرجَع المعاملة كاملة:
-- الحجوزات المصنوعة، والقوالب المفعّلة، والطابور. يُشغَّل كما هو ويُقرأ
-- الناتج: كل سطرٍ فيه "ok": true.
--
--   psql "$DB_URL" -f supabase/tests/auto_messages.sql
--
-- أو من لوحة Supabase ← SQL Editor. الرسالة الأخيرة هي النتيجة.

do $do$
declare
  b1 uuid; b2 uuid; b3 uuid; b4 uuid;
  t_conf uuid; t_rem uuid; t_thx uuid;
  n int; v text; ok boolean; res jsonb := '[]'::jsonb;
begin
  update public.settings set wa_quiet_from = 22, wa_quiet_to = 9 where id = 1;

  select id into t_conf from public.message_templates where title = 'تأكيد الحجز' limit 1;
  select id into t_rem  from public.message_templates where title = 'تذكير بالموعد' limit 1;
  select id into t_thx  from public.message_templates where title like 'شكر بعد الخدم%' limit 1;

  update public.message_templates set auto_enabled = true, auto_trigger = 'on_confirmed',
         auto_offset_min = 0, auto_at_hour = null where id = t_conf;
  update public.message_templates set auto_enabled = true, auto_trigger = 'before_appt',
         auto_offset_min = 1440, auto_at_hour = 18 where id = t_rem;
  update public.message_templates set auto_enabled = true, auto_trigger = 'after_done',
         auto_offset_min = 1440, auto_at_hour = 11, active = true where id = t_thx;

  insert into public.bookings (ref, client_name, client_phone, the_date, start_time,
         duration_min, status, items_total, price, deposit, source)
  values ('T-1','اختبار أولى','966500000001', current_date + 10, '19:00', 60, 'confirmed',
          1000,1000,300,'admin') returning id into b1;

  select count(*) into n from public.message_outbox where booking_id = b1;
  res := res || jsonb_build_array(jsonb_build_object('n','حجزٌ مؤكَّد يجدول رسالتين','ok', n=2,'got',n));

  select to_char(due_at at time zone 'Asia/Riyadh','YYYY-MM-DD HH24:MI') into v
    from public.message_outbox where booking_id=b1 and template_id=t_rem;
  res := res || jsonb_build_array(jsonb_build_object('n','التذكير قبل الموعد بيومٍ عند ٦ م',
    'ok', v = to_char(current_date + 9,'YYYY-MM-DD')||' 18:00','got',v));

  select due_at <= now() + interval '5 seconds' into ok
    from public.message_outbox where booking_id=b1 and template_id=t_conf;
  res := res || jsonb_build_array(jsonb_build_object('n','التأكيد مستحقٌّ فورًا','ok',ok,'got',''));

  perform public.schedule_auto_messages(b1);
  perform public.schedule_auto_messages(b1);
  select count(*) into n from public.message_outbox where booking_id=b1;
  res := res || jsonb_build_array(jsonb_build_object('n','إعادة الجدولة لا تكرّر','ok', n=2,'got',n));

  update public.message_templates set auto_at_hour = 3 where id = t_rem;
  delete from public.message_outbox where booking_id = b1;
  perform public.schedule_auto_messages(b1);
  select to_char(due_at at time zone 'Asia/Riyadh','HH24:MI') into v
    from public.message_outbox where booking_id=b1 and template_id=t_rem;
  res := res || jsonb_build_array(jsonb_build_object('n','الثالثة فجرًا تُؤجَّل إلى ٩ ص','ok', v='09:00','got',v));
  update public.message_templates set auto_at_hour = 18 where id = t_rem;

  insert into public.bookings (ref, client_name, client_phone, the_date, start_time,
         duration_min, status, items_total, price, deposit, source)
  values ('T-2','اختبار ثانية','966500000002', current_date - 3, '19:00', 60, 'confirmed',
          1000,1000,300,'admin') returning id into b2;
  select count(*) into n from public.message_outbox where booking_id=b2 and template_id=t_rem;
  res := res || jsonb_build_array(jsonb_build_object('n','موعدٌ فات لا يُجدول له تذكير','ok', n=0,'got',n));

  update public.bookings set status='cancelled' where id=b1;
  select count(*) into n from public.message_outbox where booking_id=b1 and status='cancelled';
  res := res || jsonb_build_array(jsonb_build_object('n','الإلغاء يسحب المجدول','ok', n>=1,'got',n));
  select count(*) into n from public.message_outbox where booking_id=b1 and status='queued';
  res := res || jsonb_build_array(jsonb_build_object('n','ولا يبقى شيءٌ في الانتظار','ok', n=0,'got',n));

  insert into public.bookings (ref, client_name, client_phone, the_date, start_time,
         duration_min, status, items_total, price, deposit, source, completed_at)
  values ('T-3','اختبار ثالثة','966500000003', current_date - 1, '15:00', 60, 'done',
          800,800,200,'admin', now()) returning id into b3;
  select to_char(due_at at time zone 'Asia/Riyadh','YYYY-MM-DD HH24:MI') into v
    from public.message_outbox where booking_id=b3 and template_id=t_thx;
  res := res || jsonb_build_array(jsonb_build_object('n','الشكر بعد الاكتمال بيومٍ عند ١١ ص',
    'ok', v = to_char((now() at time zone 'Asia/Riyadh')::date + 1,'YYYY-MM-DD')||' 11:00','got',v));

  insert into public.bookings (ref, client_name, client_phone, the_date, start_time,
         duration_min, status, items_total, price, deposit, source)
  values ('T-4','اختبار رابعة','966500000004', current_date + 5, '17:00', 60, 'pending',
          500,500,100,'admin') returning id into b4;
  select count(*) into n from public.message_outbox where booking_id=b4;
  res := res || jsonb_build_array(jsonb_build_object('n','الطلب المعلّق لا يُرسل له تأكيد','ok', n=0,'got',n));

  perform public.dispatch_due_messages(50);
  select count(*) into n from public.message_outbox where status='sent';
  res := res || jsonb_build_array(jsonb_build_object('n','وضع المعاينة لا يُرسل شيئًا','ok', n=0,'got',n));

  insert into public.booking_items (booking_id, service_name, price, duration_min, sort)
  values (b3,'ميك اب عروس',3000,60,1),(b3,'تسريحة',300,30,2);
  update public.bookings set the_date = date '2026-10-03', start_time='13:30',
         price=3300, deposit=300, client_name='أماني العنزي' where id=b3;
  select public.render_template('{الاسم} · {التاريخ} · {الوقت} · {الخدمة} · {الإجمالي} · {المتبقي} · {مجهول}', b3) into v;
  res := res || jsonb_build_array(jsonb_build_object('n','الصياغة كما في اللوحة حرفًا بحرف',
    'ok', v = 'أماني العنزي · السبت 3 أكتوبر 2026 · 1:30 م · ميك اب عروس + تسريحة · 3,300 ر.س · 3,000 ر.س · {مجهول}',
    'got', v));

  raise exception 'RESULTS %', res::text;
end $do$;
