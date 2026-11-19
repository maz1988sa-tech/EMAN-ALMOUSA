-- فحص ٠٠٤٢: الفترة المخصّصة لخدمة تسبق أقصى مدى الحجز (§٧ع في CLAUDE.md).
--
-- داخل معاملةٍ تُرجَع، على قاعدة الحيّ وجداوله، بلا أثر:
--   ١) reserved_open: مفعّلةٌ فيها اليوم وتشترك مع السلّة في خدمةٍ موجودة — وإلّا لا.
--   ٢) available_slots بعد المدى: تُفتح للعروس، وتبقى مقفلةً للسهرة ولمن لا يذكر خدماته وللموقوفة
--      وليوم الراحة داخل الفترة.
--   ٣) days_with_availability بعد المدى: أيامٌ مفتوحة للعروس لا «مخصّصة»، وللسهرة مقفلةٌ كما كانت
--      لا مخطّطة (اختيار صاحب المشروع: تراها «غير مفتوحة» بكلمة إيمان).
--   ٤) open_days_ahead: بلا خدماتٍ كما كانت، وبخدمات العروس تضمّ أيام فترتها بعد المدى وحدها.
--   ٥) create_booking: صفحةٌ تعرف الفترات (بتّ ١) تمرّ من سؤال الموعد في شهر العروس البعيد، وصفحةٌ لا
--      تعرفها تبقى كما كانت.
--   ٦) الصلاحيات والتوقيعات.
--
-- الخدمتان مؤقّتتان بلا عربون (تُدرجان ثمّ تُرجَعان): فلا يسبق فحصُ الإيصال سؤالَ الموعد في
-- create_booking، ولا تُمسّ خدمات إيمان ولا فتراتها. والحجز لا يُنشأ حتى داخل المعاملة: يُترك رابط
-- الخرائط فارغًا فيردّه المشغّل `bookings_require_map` عند الإدراج — وبلوغُ ذلك المشغّل هو الدليل أنّ
-- سؤال الموعد مرّ. والأيامُ تُختار حيث لا فترةَ قائمة، فلا يتعارض الفحص مع ما ضبطته إيمان.
--
-- قبل التطبيق يلفّه `tools/trial_reserved.py` حول نصّ الترحيل في معاملةٍ واحدة:
--   .venv/bin/python tools/trial_reserved.py supabase/migrations/0042_reserved_beyond_horizon.sql supabase/tests/reserved_horizon.sql
-- وبعده يُشغَّل وحده. الرسالة الأخيرة هي النتيجة: «ROLLBACK_OK reserved_horizon ok=N bad=0».

do $do$
declare
  v_adv int; v_edge date; v_tb uuid; v_te uuid; v_off int; v_all date[]; v_far date[]; v_far2 date[];
  v_edge3 date[]; v_d date; v_dc date; v_t time; v_i int; v_path text; v_txt text; v_n int; v_m int;
  v_a1 boolean; v_a2 boolean; v_a3 boolean;
  v_map  constant text := 'رابط الموقع من خرائط قوقل مطلوب لتثبيت الموعد';
  v_gone constant text := 'هذا الموعد لم يعد متاحًا، اختاري وقتًا آخر';
  v_msg  constant text := 'للعرائس بعد المدى';
  r_ok int; r_bad int; r_names text;
begin
  create temp table _r(ok boolean, name text) on commit drop;
  -- ⟪test⟫
  select coalesce(max_advance_days, 0) into v_adv from public.settings where id = 1;
  v_edge := public.local_today() + v_adv;

  insert into public.services (name, icon, price, duration_min, deposit_amount, active, bookable_by_client, sort)
  values ('فحص عروس ٠٠٤٢', 'bride', 100, 60, 0, true, true, 9990) returning id into v_tb;
  insert into public.services (name, icon, price, duration_min, deposit_amount, active, bookable_by_client, sort)
  values ('فحص سهرة ٠٠٤٢', 'evening', 100, 45, 0, true, true, 9991) returning id into v_te;

  -- عشرون يومًا بعد المدى لا تمسّها فترةٌ قائمة: أربعة عشر للفترة، وثلاثة لفترةٍ موقوفة، وآخرها لفترةٍ بلا خدمة
  for v_off in 0 .. 30 loop
    v_all := array(select v_edge + 10 + v_off * 20 + g from generate_series(0, 19) g);
    exit when not public.reserved_overlap(null, v_all);
    v_all := null;
  end loop;
  if v_all is null then raise exception 'ROLLBACK_SKIP لا أيامَ حرّة بعد المدى'; end if;
  v_far := v_all[1:14]; v_far2 := v_all[16:18];

  insert into public.reserved_periods (mode, dates, service_ids, message)
  values ('range', v_far, array[v_tb], v_msg);
  insert into public.reserved_periods (mode, dates, service_ids, message, active)
  values ('days', v_far2, array[v_tb], 'موقوفة', false);
  insert into public.reserved_periods (mode, dates, service_ids, message)
  values ('days', array[v_all[20]], array[gen_random_uuid()], 'بلا خدمة');

  -- ١) reserved_open
  insert into _r values (public.reserved_open(v_far[1], array[v_tb]), 'reserved_open: العروس في فترتها');
  insert into _r values (public.reserved_open(v_far[1], array[v_te, v_tb]), 'reserved_open: العروس ومعها سهرة');
  insert into _r values (not public.reserved_open(v_far[1], array[v_te]), 'reserved_open: السهرة وحدها لا');
  insert into _r values (not public.reserved_open(v_far[1], null), 'reserved_open: بلا خدماتٍ لا');
  insert into _r values (not public.reserved_open(v_far[1] - 1, array[v_tb]), 'reserved_open: خارج الفترة لا');
  insert into _r values (not public.reserved_open(v_far2[1], array[v_tb]), 'reserved_open: الموقوفة لا تفتح');
  insert into _r values (not public.reserved_open(v_all[20], (select service_ids from public.reserved_periods
                                                               where dates = array[v_all[20]])), 'reserved_open: فترةٌ بلا خدمةٍ موجودة لا تفتح');

  -- ٢) available_slots بعد المدى: أوّل يومٍ مفتوحٍ للعروس في فترتها ووقتُه
  for v_i in 1 .. array_length(v_far, 1) loop
    select s.slot into v_t from public.available_slots(v_far[v_i], 60, null, array[v_tb]) s limit 1;
    if v_t is not null then v_d := v_far[v_i]; exit; end if;
  end loop;
  insert into _r values (v_d is not null, 'العروس يُفتح لها يومٌ في فترتها بعد المدى [' || coalesce(v_d::text, 'لا يوم') || ']');
  if v_d is not null then
    insert into _r values (exists (select 1 from public.available_slots(v_d, 105, null, array[v_tb, v_te])), 'وعروسٌ معها سهرة كذلك');
    insert into _r values (not exists (select 1 from public.available_slots(v_d, 45, null, array[v_te])), 'السهرة وحدها لا يُفتح لها');
    insert into _r values (not exists (select 1 from public.available_slots(v_d, 60)), 'النداء القديم بلا خدماتٍ كما كان: مقفل');
  end if;
  insert into _r values (not exists (select 1 from public.available_slots(v_far2[1], 60, null, array[v_tb])), 'الموقوفة لا تفتح ما بعد المدى');
  select d into v_dc from unnest(v_far) d where not exists (select 1 from public.day_windows(d)) limit 1;
  if v_dc is not null then
    insert into _r values (not exists (select 1 from public.available_slots(v_dc, 60, null, array[v_tb])),
                           'يوم الراحة داخل الفترة يبقى مقفلًا للعروس [' || v_dc || ']');
  end if;

  -- ٣) days_with_availability بعد المدى
  select count(*) filter (where slot_count > 0), count(*) filter (where reserved)
    into v_n, v_m from public.days_with_availability(v_far[1], 14, 60, array[v_tb]);
  insert into _r values (v_n >= 1 and v_m = 0, 'أيام العروس بعد المدى مفتوحةٌ لا «مخصّصة» [' || v_n || '/' || v_m || ']');
  select count(*) filter (where slot_count > 0), count(*) filter (where reserved)
    into v_n, v_m from public.days_with_availability(v_far[1], 14, 45, array[v_te]);
  insert into _r values (v_n = 0 and v_m = 0, 'وللسهرة مقفلةٌ كما كانت، لا مخطّطة [' || v_n || '/' || v_m || ']');
  select count(*) filter (where slot_count > 0) into v_n from public.days_with_availability(v_far[1], 14, 60);
  insert into _r values (v_n = 0, 'والنداء القديم بثلاثة وسائط كما كان');

  -- ٤) open_days_ahead
  insert into _r values (not exists (select 1 from public.open_days_ahead() o where o.the_date = any(v_far)),
                         'open_days_ahead بلا خدماتٍ كما كانت: لا أيام فترات');
  insert into _r values ((select count(*) from public.open_days_ahead(array[v_tb]) o where o.the_date = any(v_far)) = 14,
                         'وبخدمات العروس تضمّ أيام فترتها كلَّها');
  insert into _r values (not exists (select 1 from public.open_days_ahead(array[v_te]) o where o.the_date = any(v_far)),
                         'وبخدمات السهرة لا تضمّها');
  insert into _r values (not exists (select 1 from public.open_days_ahead(array[v_tb]) o where o.the_date = any(v_far2)),
                         'ولا أيام الموقوفة');
  insert into _r values ((select count(*) from public.open_days_ahead()) = (select count(*) from public.open_days_ahead(null)),
                         'التوقيع القديم والجديد بلا خدماتٍ سواء');
  v_edge3 := array[v_edge - 1, v_edge, v_edge + 1];
  if not public.reserved_overlap(null, v_edge3) then
    insert into public.reserved_periods (mode, dates, service_ids, message) values ('range', v_edge3, array[v_tb], 'عند الحدّ');
    insert into _r values ((select array_agg(o.the_date order by o.the_date) from public.open_days_ahead(array[v_tb]) o
                             where o.the_date = any(v_edge3)) = array[v_edge + 1],
                           'فترةٌ تعبر الحدّ: يُذكر ما بعده وحده');
  end if;

  -- ٥) create_booking: سؤال الموعد بخدمات السلّة لمن يعرف الفترات وحده
  v_path := 'pending/' || gen_random_uuid()::text || '.jpg';
  begin
    insert into storage.objects (bucket_id, name) values ('receipts', v_path);
    v_a1 := true;
  exception when others then v_a1 := false; v_txt := sqlerrm; end;
  if v_a1 and v_d is not null and (select accepting_bookings from public.settings where id = 1) then
    begin
      perform 1 from public.create_booking('اختبار', '0551234567', v_d, v_t, array[v_tb], null, null, null, null, v_path, null, null, 1, 1);
      v_txt := 'أُنشئ';
    exception when others then v_txt := sqlerrm; end;
    insert into _r values (v_txt = v_map, 'صفحةٌ تعرف الفترات: العروس تمرّ من سؤال الموعد في شهرها البعيد [' || v_txt || ']');
    begin
      perform 1 from public.create_booking('اختبار', '0551234567', v_d, v_t, array[v_tb], null, null, null, null, v_path, null, null, 1, 0);
      v_txt := 'أُنشئ';
    exception when others then v_txt := sqlerrm; end;
    insert into _r values (v_txt = v_gone, 'وصفحةٌ لا تعرفها كما كانت: الموعد بعد المدى غير متاح [' || v_txt || ']');
    begin
      perform 1 from public.create_booking('اختبار', '0551234567', v_d, v_t, array[v_te], null, null, null, null, v_path, null, null, 1, 1);
      v_txt := 'أُنشئ';
    exception when others then v_txt := sqlerrm; end;
    insert into _r values (v_txt = v_msg, 'والسهرة وحدها تُردّ برسالة الفترة [' || v_txt || ']');
  else
    insert into _r values (true, 'تخطّي create_booking [' || coalesce(v_txt, case when v_d is null then 'لا يوم' else 'الحجز مغلق' end) || ']');
  end if;

  -- ٦) الصلاحيات والتوقيعات
  insert into _r values ((select count(*) from pg_proc where pronamespace = 'public'::regnamespace and proname = 'open_days_ahead') = 1, 'open_days_ahead بتوقيعٍ واحد');
  insert into _r values ((select count(*) from pg_proc where pronamespace = 'public'::regnamespace and proname = 'available_slots') = 1, 'available_slots بتوقيعٍ واحد');
  insert into _r values ((select count(*) from pg_proc where pronamespace = 'public'::regnamespace and proname = 'create_booking') = 1, 'create_booking بتوقيعٍ واحد');
  perform set_config('role', 'anon', true);
  begin perform 1 from public.open_days_ahead(); v_a1 := true; exception when others then v_a1 := false; end;
  begin perform 1 from public.open_days_ahead(array[v_tb]); v_a2 := true; exception when others then v_a2 := false; end;
  begin perform public.reserved_open(v_far[1], array[v_tb]); v_a3 := false; exception when insufficient_privilege then v_a3 := true; end;
  perform set_config('role', 'postgres', true);
  insert into _r values (v_a1, 'المتصفّح ينادي open_days_ahead بلا وسائط (الصفحة القديمة)');
  insert into _r values (v_a2, 'وبخدمات السلّة (الصفحة الجديدة)');
  insert into _r values (v_a3, 'المتصفّح لا ينادي reserved_open');
  insert into _r values (not exists (select 1 from pg_proc p, aclexplode(p.proacl) a
                                      where p.pronamespace = 'public'::regnamespace and p.proname = 'open_days_ahead'
                                        and a.grantee = 0), 'open_days_ahead لا تُنفَّذ من «الجميع»');
  -- ⟪/test⟫
  select count(*) filter (where ok), count(*) filter (where not ok),
         coalesce(string_agg(name, ' | ') filter (where not ok), '')
    into r_ok, r_bad, r_names from _r;
  raise exception 'ROLLBACK_OK reserved_horizon ok=% bad=% %', r_ok, r_bad, r_names;
end $do$;
