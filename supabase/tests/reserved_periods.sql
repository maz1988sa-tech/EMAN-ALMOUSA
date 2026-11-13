-- فحص الفترات المخصّصة لخدمة (الترحيل ٠٠٤١، §٧ع في CLAUDE.md).
--
-- يجرّب الحكم والتعارض والتطبيع والقيود والصلاحيات واللقطة والاستعادة وحارسَ create_booking
-- كلَّها داخل معاملةٍ تُرجَع، على خدمات الحيّ الحقيقية وجدوله — فلا يبقى أثرٌ:
--
--   psql "$DB_URL" -f supabase/tests/reserved_periods.sql
--
-- أو من لوحة Supabase ← SQL Editor. الرسالة الأخيرة هي النتيجة (استثناءٌ يُرجع المعاملة):
-- «ROLLBACK_OK reserved_periods ok=N bad=0». وأيُّ bad يُسمّى بنصّه.
--
-- ما يُجرَّب هنا إدراجٌ وقراءة فقط: التعديل والحذف يُحبَسان على الحيّ بلا موافقة (§٣)، فمنطق
-- التعديل يُفحص بـ`reserved_overlap(id, dates)` وهي ما يستدعيه مشغّل التعديل نفسُه، والحذف
-- لا منطقَ فيه.
--
-- ويُشغَّل قبل تطبيق الترحيل كذلك: يلفّه `tools/trial_reserved.py` حول نصّ الترحيل في معاملةٍ
-- واحدة (علامتا ⟪test⟫ تحدّان ما يُنقل).

do $do$
declare
  v_ids uuid[]; v_b uuid; v_e uuid; v_h uuid := gen_random_uuid();
  v_d0 date; v_dc date; v_i int; v_p1 uuid;
  v_msgp constant text := 'رسالة الفترة';
  v_dur int; v_slot time; v_path text; v_uid uuid; v_row record;
  v_n1 int; v_n2 int; v_cnt int; v_snap jsonb; v_rest jsonb; v_txt text;
  v_a1 boolean; v_a2 boolean; v_a3 boolean; v_a4 boolean; v_a5 boolean;
  r_ok int; r_bad int; r_names text;
begin
  create temp table _r(ok boolean, name text) on commit drop;
  -- ⟪test⟫
  select array_agg(id order by sort) into v_ids
    from (select id, sort from public.services where active order by sort limit 2) s;
  if coalesce(array_length(v_ids, 1), 0) < 2 then
    raise exception 'ROLLBACK_SKIP أحتاج خدمتين فعّالتين على الأقل';
  end if;
  v_b := v_ids[1]; v_e := v_ids[2];

  -- أوّل يومٍ مفتوح (بعد غدٍ فصاعدًا ليتجاوز مهلة الحجز)
  for v_i in 3 .. 90 loop
    if exists (select 1 from public.available_slots(public.local_today() + v_i, 60)) then
      v_d0 := public.local_today() + v_i; exit;
    end if;
  end loop;
  if v_d0 is null then raise exception 'ROLLBACK_SKIP لا يوم مفتوح خلال ٩٠ يومًا'; end if;

  -- التوقيعات: واحدٌ لكلّ دالّة، وإلّا صار النداء «غير وحيد» فسقط
  insert into _r values ((select count(*) from pg_proc where pronamespace = 'public'::regnamespace and proname = 'create_booking') = 1, 'create_booking بتوقيعٍ واحد');
  insert into _r values ((select count(*) from pg_proc where pronamespace = 'public'::regnamespace and proname = 'available_slots') = 1, 'available_slots بتوقيعٍ واحد');
  insert into _r values ((select count(*) from pg_proc where pronamespace = 'public'::regnamespace and proname = 'days_with_availability') = 1, 'days_with_availability بتوقيعٍ واحد');

  -- فترةٌ لسبعة أيام مخصّصة للعروس
  insert into public.reserved_periods (mode, dates, service_ids, message)
  values ('range', (select array_agg(v_d0 + g) from generate_series(0, 6) g), array[v_b], v_msgp)
  returning id into v_p1;

  -- ١) الحكم: خدمةٌ واحدة من المخصّصة تفتح الباب لكلّ ما معها
  insert into _r values (public.reserved_block(v_d0, array[v_b]) is null, 'العروس تدخل');
  insert into _r values (public.reserved_block(v_d0, array[v_e]) = v_msgp, 'السهرة تُردّ برسالة الفترة');
  insert into _r values (public.reserved_block(v_d0, array[v_b, v_e]) is null, 'عروس مع سهرة تدخل');
  insert into _r values (public.reserved_block(v_d0, array[v_e, v_h]) = v_msgp, 'سهرة مع غير مخصّصة تُردّ');
  insert into _r values (public.reserved_block(v_d0, array[v_b, v_h]) is null, 'عروس مع غير مخصّصة تدخل');
  insert into _r values (public.reserved_block(v_d0 + 30, array[v_e]) is null, 'خارج الفترة لا حكم');

  -- ٢) الموقوفة لا تحجب، وفترةٌ لم تبقَ فيها خدمةٌ موجودة لا تحجب
  insert into public.reserved_periods (mode, dates, service_ids, message, active)
  values ('days', array[v_d0 + 40], array[v_b], 'موقوفة', false);
  insert into _r values (public.reserved_block(v_d0 + 40, array[v_e]) is null, 'الموقوفة لا تحجب');
  insert into public.reserved_periods (mode, dates, service_ids, message)
  values ('days', array[v_d0 + 50], array[gen_random_uuid()], 'بلا خدمة');
  insert into _r values (public.reserved_block(v_d0 + 50, array[v_e]) is null, 'فترة بلا خدمةٍ موجودة لا تحجب');

  -- ٣) التعارض: حكمٌ واحد لكلّ يوم، والفترة لا تتعارض مع نفسها (طريق التعديل)
  insert into _r values (not public.reserved_overlap(v_p1, array[v_d0]), 'الفترة لا تتعارض مع نفسها');
  insert into _r values (public.reserved_overlap(null, array[v_d0]), 'يومٌ مأخوذ يُكشف');
  insert into _r values (not public.reserved_overlap(gen_random_uuid(), array[v_d0 + 100]), 'يومٌ حرّ لا يُكشف');
  begin
    insert into public.reserved_periods (dates, service_ids, message)
    values (array[v_d0 + 3], array[v_e], 'تعارض');
    insert into _r values (false, 'التعارض لم يُردّ');
  exception when others then
    v_txt := sqlstate || ' ' || sqlerrm;
    insert into _r values (sqlstate = 'P0001' and sqlerrm like 'أيامٌ من هذه%', 'التعارض يُردّ بالمشغّل [' || v_txt || ']');
  end;

  -- ٤) التطبيع والقيود
  insert into public.reserved_periods (mode, dates, service_ids, message)
  values ('days', array[v_d0 + 60, v_d0 + 60, v_d0 + 59], array[v_b, v_b], '  مرحبا  ')
  returning dates, service_ids, message into v_row;
  insert into _r values (v_row.dates = array[v_d0 + 59, v_d0 + 60], 'التواريخ مرتّبة بلا تكرار');
  insert into _r values (array_length(v_row.service_ids, 1) = 1, 'الخدمات بلا تكرار');
  insert into _r values (v_row.message = 'مرحبا', 'الرسالة مقصوصة');
  begin
    insert into public.reserved_periods (dates, service_ids, message) values ('{}', array[v_b], 'م');
    insert into _r values (false, 'بلا أيام لم يُردّ');
  exception when check_violation then insert into _r values (true, 'بلا أيام يُردّ'); end;
  begin
    insert into public.reserved_periods (dates, service_ids, message) values (array[v_d0 + 90], '{}', 'م');
    insert into _r values (false, 'بلا خدمة لم يُردّ');
  exception when check_violation then insert into _r values (true, 'بلا خدمة يُردّ'); end;
  begin
    insert into public.reserved_periods (dates, service_ids, message) values (array[v_d0 + 90], array[v_b], '   ');
    insert into _r values (false, 'بلا رسالة لم يُردّ');
  exception when check_violation then insert into _r values (true, 'بلا رسالة يُردّ'); end;

  -- ٥) available_slots: اليوم لا يُفتح لسلّةٍ لا تناسبه، وبلا خدماتٍ لا حكم
  select count(*) into v_n1 from public.available_slots(v_d0, 60);
  insert into _r values (v_n1 > 0, 'اليوم المفتوح له أوقات');
  insert into _r values ((select count(*) from public.available_slots(v_d0, 60, null, array[v_e])) = 0, 'السهرة لا أوقات لها في اليوم المخصّص');
  insert into _r values ((select count(*) from public.available_slots(v_d0, 60, null, array[v_b])) = v_n1, 'العروس أوقاتُها كاملة');
  insert into _r values ((select count(*) from public.available_slots(v_d0, 60, null, null)) = v_n1, 'بلا خدماتٍ لا حكم');
  insert into _r values ((select count(*) from public.available_slots(v_d0 + 30, 60, null, array[v_e])) = (select count(*) from public.available_slots(v_d0 + 30, 60)), 'خارج الفترة السهرة كما هي');

  -- ٦) days_with_availability: «مخصّص» ورسالته، والمقفل يبقى مقفلًا، والنداء القديم يعمل
  select * into v_row from public.days_with_availability(v_d0, 1, 60, array[v_e]);
  insert into _r values (v_row.slot_count = 0 and v_row.reserved and v_row.reserved_msg = v_msgp, 'اليوم المخصّص يُعلَّم ورسالته');
  select * into v_row from public.days_with_availability(v_d0, 1, 60, array[v_b]);
  insert into _r values (v_row.slot_count = v_n1 and not v_row.reserved and v_row.reserved_msg is null, 'العروس يومها عاديّ');
  select * into v_row from public.days_with_availability(v_d0, 1, 60);
  insert into _r values (v_row.slot_count = v_n1 and not v_row.reserved, 'النداء القديم بثلاثة وسائط كما كان');
  select x.dd into v_dc from (select v_d0 + g as dd from generate_series(1, 6) g) x
   where not exists (select 1 from public.available_slots(x.dd, 60)) limit 1;
  if v_dc is not null then
    select * into v_row from public.days_with_availability(v_dc, 1, 60, array[v_e]);
    insert into _r values (v_row.slot_count = 0 and not v_row.reserved and v_row.reserved_msg is null, 'المقفل في الأساس يبقى مقفلًا لا مخصّصًا');
  end if;

  -- ٧) الصلاحيات: المتصفّح (anon) يسأل ولا يقرأ الجدول ولا ينادي المساعدة
  perform set_config('role', 'anon', true);
  begin perform 1 from public.days_with_availability(v_d0, 1, 60, array[v_e]); v_a1 := true; exception when others then v_a1 := false; end;
  begin perform 1 from public.available_slots(v_d0, 60, null, array[v_e]); v_a2 := true; exception when others then v_a2 := false; end;
  begin perform 1 from public.reserved_periods; v_a3 := false; exception when insufficient_privilege then v_a3 := true; end;
  begin perform public.reserved_block(v_d0, array[v_e]); v_a4 := false; exception when insufficient_privilege then v_a4 := true; end;
  begin perform public.reserved_overlap(null, array[v_d0]); v_a5 := false; exception when insufficient_privilege then v_a5 := true; end;
  perform set_config('role', 'postgres', true);
  insert into _r values (v_a1, 'المتصفّح ينادي days_with_availability');
  insert into _r values (v_a2, 'المتصفّح ينادي available_slots');
  insert into _r values (v_a3, 'المتصفّح لا يقرأ الجدول');
  insert into _r values (v_a4, 'المتصفّح لا ينادي reserved_block');
  insert into _r values (v_a5, 'المتصفّح لا ينادي reserved_overlap');
  insert into _r values (has_function_privilege('anon', 'public.create_booking(text,text,date,time without time zone,uuid[],text[],text,text,text,text,numeric,numeric,integer,integer)', 'execute'), 'المتصفّح ينادي create_booking');
  insert into _r values (not exists (select 1 from pg_proc p, aclexplode(p.proacl) a where p.pronamespace = 'public'::regnamespace
                                      and p.proname in ('available_slots', 'days_with_availability') and a.grantee = 0), 'الدالّتان لا تُنفَّذان من «الجميع»');

  -- ٨) المديرة تقرأ وتكتب، وغيرها لا يرى ولا يكتب
  select user_id into v_uid from public.admins limit 1;
  if v_uid is null then raise exception 'ROLLBACK_SKIP لا مديرَ في الجدول'; end if;
  perform set_config('role', 'authenticated', true);
  perform set_config('request.jwt.claims', json_build_object('sub', v_uid)::text, true);
  select count(*) into v_n1 from public.reserved_periods;
  begin
    insert into public.reserved_periods (dates, service_ids, message) values (array[v_d0 + 70], array[v_b], 'من المديرة');
    v_a1 := true;
  exception when others then v_a1 := false; end;
  perform set_config('request.jwt.claims', json_build_object('sub', gen_random_uuid())::text, true);
  select count(*) into v_n2 from public.reserved_periods;
  begin
    insert into public.reserved_periods (dates, service_ids, message) values (array[v_d0 + 71], array[v_b], 'من غير المديرة');
    v_a2 := false;
  exception when others then v_a2 := true; end;
  perform set_config('role', 'postgres', true);
  insert into _r values (v_n1 >= 4, 'المديرة ترى الفترات');
  insert into _r values (v_a1, 'المديرة تضيف فترة');
  insert into _r values (v_n2 = 0, 'غير المديرة لا ترى شيئًا');
  insert into _r values (v_a2, 'غير المديرة لا تضيف');

  -- ٩) حارس create_booking: يردّ برسالة الفترة لمن تعرفها فقط (p_features بتّ ١)
  v_path := 'pending/' || gen_random_uuid()::text || '.jpg';
  begin
    insert into storage.objects (bucket_id, name) values ('receipts', v_path);
    v_a1 := true;
  exception when others then v_a1 := false; v_txt := sqlerrm; end;
  if v_a1 then
    select duration_min into v_dur from public.services where id = v_e;
    select slot into v_slot from public.available_slots(v_d0, v_dur) limit 1;
    begin
      perform 1 from public.create_booking('اختبار', '0551234567', v_d0, v_slot, array[v_e], null, null, null, null, v_path, null, null, 1, 1);
      v_txt := 'لم تُردّ';
    exception when others then v_txt := sqlerrm; end;
    insert into _r values (v_txt = v_msgp, 'السهرة تُردّ برسالة الفترة لمن يعرفها [' || v_txt || ']');
    begin
      perform 1 from public.create_booking('اختبار', '0551234567', v_d0, v_slot, array[v_e], null, null, null, null, v_path, null, null, 1, 0);
      v_txt := 'مرّت';
    exception when others then v_txt := sqlerrm; end;
    insert into _r values (v_txt is distinct from v_msgp, 'صفحةٌ لا تعرف الفترات لا تُحكَم بها [' || v_txt || ']');
    begin
      perform 1 from public.create_booking('اختبار', '0551234567', v_d0, v_slot, array[v_b], null, null, null, null, v_path, null, null, 1, 1);
      v_txt := 'مرّت';
    exception when others then v_txt := sqlerrm; end;
    insert into _r values (v_txt is distinct from v_msgp, 'العروس لا تُردّ بالفترة [' || v_txt || ']');
    begin
      perform 1 from public.create_booking('اختبار', '0551234567', v_d0, v_slot, array[v_b, v_e], null, null, null, null, v_path, null, null, 1, 1);
      v_txt := 'مرّت';
    exception when others then v_txt := sqlerrm; end;
    insert into _r values (v_txt is distinct from v_msgp, 'عروس مع سهرة لا تُردّ بالفترة [' || v_txt || ']');
  else
    insert into _r values (true, 'تخطّي: تعذّر إدراج ملف إيصال في storage [' || coalesce(v_txt, '') || ']');
  end if;

  -- ١٠) اللقطة والاستعادة
  perform set_config('role', 'authenticated', true);
  perform set_config('request.jwt.claims', json_build_object('sub', v_uid)::text, true);
  v_snap := public.admin_snapshot();
  perform set_config('role', 'postgres', true);
  select count(*) into v_cnt from public.reserved_periods;
  insert into _r values (v_snap ? 'reserved_periods', 'اللقطة تحمل الفترات');
  insert into _r values ((v_snap->'counts') ? 'reserved_periods', 'اللقطة تعدّ الفترات');
  insert into _r values (jsonb_array_length(v_snap->'reserved_periods') = v_cnt, 'عدد الفترات في اللقطة هو عددها في الجدول');
  perform set_config('role', 'authenticated', true);
  perform set_config('request.jwt.claims', json_build_object('sub', v_uid)::text, true);
  v_rest := public.admin_restore_snapshot(jsonb_build_object('version', 2, 'reserved_periods', jsonb_build_array(
      (select to_jsonb(p) from public.reserved_periods p where p.id = v_p1),
      jsonb_build_object('id', gen_random_uuid(), 'mode', 'days', 'dates', jsonb_build_array((v_d0 + 200)::text),
                         'service_ids', jsonb_build_array(v_b::text), 'message', 'من النسخة', 'active', true, 'created_at', now()),
      jsonb_build_object('id', gen_random_uuid(), 'mode', 'days', 'dates', jsonb_build_array((v_d0 + 1)::text),
                         'service_ids', jsonb_build_array(v_e::text), 'message', 'تتعارض', 'active', true, 'created_at', now()))), false);
  perform set_config('role', 'postgres', true);
  perform set_config('app.restoring', '', true);
  insert into _r values ((v_rest->>'reserved_periods')::int = 1, 'الاستعادة تُعيد الغائب وتتخطّى القائم والمتعارض [' || coalesce(v_rest->>'reserved_periods', '?') || ']');
  insert into _r values ((select count(*) from public.reserved_periods) = v_cnt + 1, 'والجدول زاد واحدةً فقط');
  -- ⟪/test⟫
  select count(*) filter (where ok), count(*) filter (where not ok),
         coalesce(string_agg(name, ' | ') filter (where not ok), '')
    into r_ok, r_bad, r_names from _r;
  raise exception 'ROLLBACK_OK reserved_periods ok=% bad=% %', r_ok, r_bad, r_names;
end $do$;
