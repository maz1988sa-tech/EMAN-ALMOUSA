-- هل تحمل النسخة الاحتياطية كلَّ جدول؟
--
-- السؤال ليس «هل كتبنا الجداول الصحيحة يومها» بل «هل بقيت صحيحة بعد أن
-- نما المخطّط». قائمةٌ مكتوبة باليد تتخلّف صامتةً: أُضيفت الرسائل ثمّ
-- الطابور ثمّ الزوّار، وبقيت اللقطة على ستّة جداول — ونسخةٌ تُطمئن وهي
-- ناقصة أسوأ من لا نسخة.
--
-- فهذا الفحص يقارن مفاتيح اللقطة بجداول المخطّط نفسه. جدولٌ جديد لا
-- يدخل اللقطة ولا يُذكر في قائمة الاستثناء أدناه يُسقط الفحص.
--
--   psql "$DB_URL" -f supabase/tests/snapshot_coverage.sql
--
-- أو من لوحة Supabase ← SQL Editor. الرسالة الأخيرة هي النتيجة، وهي
-- استثناءٌ يُرجع المعاملة فلا يبقى أثر.

do $do$
declare
  uid uuid;
  snap jsonb;
  t text;
  uncovered text[] := '{}';
  stale text[] := '{}';
  leaked text[] := '{}';

  /* ما يبقى خارج اللقطة عن قصد — ومعه سببه في 0021_snapshot_all.sql:
     `admins` جدولُ صلاحية لا بيانات، ونسخةٌ تُسرَّب فتُعيد منح الوصول. */
  excluded text[] := array['admins'];
begin
  select user_id into uid from public.admins limit 1;
  if uid is null then
    raise exception 'ROLLBACK_OK لا مديرَ في الجدول، فلا يمكن أخذ اللقطة';
  end if;

  perform set_config('role', 'authenticated', true);
  perform set_config('request.jwt.claims', json_build_object('sub', uid)::text, true);
  snap := public.admin_snapshot();
  perform set_config('role', 'postgres', true);

  -- ١) كلُّ جدولٍ في المخطّط: إمّا في اللقطة وإمّا في الاستثناء.
  for t in
    select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public' and c.relkind = 'r'
     order by 1
  loop
    if not (snap ? t) and not (t = any(excluded)) then
      uncovered := uncovered || t;
    end if;
  end loop;

  -- ٢) ولا مفتاحَ في اللقطة لجدولٍ لم يعد موجودًا.
  for t in select k from jsonb_object_keys(snap) k loop
    if t not in ('version', 'taken_at', 'counts', 'settings')
       and not exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
                        where n.nspname = 'public' and c.relkind = 'r' and c.relname = t)
    then stale := stale || t;
    end if;
  end loop;

  -- ٣) ولا يخرج ما قُرِّر ألّا يخرج.
  if snap::text like '%raw_text%' then leaked := leaked || 'raw_text'; end if;
  if snap ? 'admins'             then leaked := leaked || 'admins';   end if;

  -- ٤) ولكلّ جدولٍ في اللقطة عدّادٌ يُعرَض، وإلّا حُفظ ولم يُذكر.
  for t in select k from jsonb_object_keys(snap) k loop
    if t not in ('version', 'taken_at', 'counts', 'settings',
                 'availability_rules', 'date_overrides')
       and not (snap->'counts' ? t)
    then stale := stale || ('بلا عدّاد:' || t);
    end if;
  end loop;

  raise exception 'ROLLBACK_OK % — خارج اللقطة=[%] مفاتيح غريبة=[%] تسرّب=[%]',
    case when uncovered = '{}' and stale = '{}' and leaked = '{}'
         then 'اللقطة تغطّي المخطّط' else '✗ نقص' end,
    array_to_string(uncovered, ','), array_to_string(stale, ','),
    array_to_string(leaked, ',');
end $do$;
