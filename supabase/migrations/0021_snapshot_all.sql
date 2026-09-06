-- النسخة الاحتياطية: كلُّ ما يُفقَد، لا ما تذكّرناه يوم كتبناها.
--
-- كانت اللقطة تحمل ستّة جداول: الإعدادات والخدمات وقواعد الأوقات
-- والاستثناءات والحجوزات وبنودها. وكلُّ ما أُضيف بعدها بقي خارجها:
-- الرسائل التي كتبتها صاحبة العمل وإعدادات إرسالها، وطابور ما أُرسل،
-- وعدّاد أرقام الحجوزات، وعدّ الزوّار، وسجلّ الأحداث. فنسخةٌ تُطمئن
-- وهي ناقصة أسوأ من لا نسخة: عليها يُبنى قرار الحذف.
--
-- والسببُ ليس سهوًا بل بنية: قائمةٌ مكتوبة باليد تتخلّف عن المخطّط كلّما
-- نما. ولذلك أُضيف فحصٌ يقارن مفاتيح اللقطة بجداول المخطّط، فجدولٌ جديد
-- يُسقط الفحص بدل أن يمرّ صامتًا — `supabase/tests/snapshot_coverage.sql`.
--
-- ── ما يبقى خارج اللقطة عن قصد ──────────────────────────────────────
-- `admins`  — جدولُ صلاحية لا بيانات. و`user_id` فيه يخصّ مشروعًا بعينه
--             فلا معنى لاستعادته في غيره، ونسخةٌ تُسرَّب فتُعيد منح
--             الوصول خطرٌ بلا مقابل.
-- `raw_text` من `receipt_scans` — النصّ الخام لإيصال العميلة البنكيّ.
--             وهو مشتقٌّ من الصورة (والصور تُنسخ مع اللقطة)، فحملُه في
--             ملفٍّ يُنزَّل توسيعٌ للانكشاف بلا فائدة استعادة. أمّا حكم
--             الفحص (الأرقام، ومطابقة الآيبان) فيبقى كاملًا.

/* ═══ اللقطة ═══════════════════════════════════════════════════════════ */

create or replace function public.admin_snapshot()
returns jsonb
language plpgsql stable security definer set search_path to 'public', 'pg_temp'
as $fn$
declare v jsonb;
begin
  if not public.is_admin() then
    raise exception 'not authorised' using errcode = '42501';
  end if;

  select jsonb_build_object(
    'version', 2,
    'taken_at', now(),
    'settings',           (select to_jsonb(s) from public.settings s where s.id = 1),
    'services',           coalesce((select jsonb_agg(to_jsonb(x) order by x.sort)       from public.services x), '[]'::jsonb),
    'availability_rules', coalesce((select jsonb_agg(to_jsonb(x))                       from public.availability_rules x), '[]'::jsonb),
    'date_overrides',     coalesce((select jsonb_agg(to_jsonb(x) order by x.the_date)   from public.date_overrides x), '[]'::jsonb),
    'bookings',           coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at) from public.bookings x), '[]'::jsonb),
    'booking_items',      coalesce((select jsonb_agg(to_jsonb(x))                       from public.booking_items x), '[]'::jsonb),
    -- ما كان ناقصًا:
    'message_templates',  coalesce((select jsonb_agg(to_jsonb(x) order by x.sort)       from public.message_templates x), '[]'::jsonb),
    'message_outbox',     coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at) from public.message_outbox x), '[]'::jsonb),
    'ref_counters',       coalesce((select jsonb_agg(to_jsonb(x))                       from public.ref_counters x), '[]'::jsonb),
    'visits',             coalesce((select jsonb_agg(to_jsonb(x) order by x.started_at) from public.visits x), '[]'::jsonb),
    'activity_log',       coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at) from public.activity_log x), '[]'::jsonb),
    -- بلا النصّ الخام: يبقى الحكمُ ويسقط ما لا يلزم حفظه.
    'receipt_scans',      coalesce((select jsonb_agg(to_jsonb(x) - 'raw_text' order by x.scanned_at)
                                      from public.receipt_scans x), '[]'::jsonb)
  ) into v;

  return v || jsonb_build_object('counts', jsonb_build_object(
    'bookings',          jsonb_array_length(v->'bookings'),
    'booking_items',     jsonb_array_length(v->'booking_items'),
    'services',          jsonb_array_length(v->'services'),
    'rules',             jsonb_array_length(v->'availability_rules'),
    'overrides',         jsonb_array_length(v->'date_overrides'),
    'message_templates', jsonb_array_length(v->'message_templates'),
    'message_outbox',    jsonb_array_length(v->'message_outbox'),
    'ref_counters',      jsonb_array_length(v->'ref_counters'),
    'visits',            jsonb_array_length(v->'visits'),
    'activity_log',      jsonb_array_length(v->'activity_log'),
    'receipt_scans',     jsonb_array_length(v->'receipt_scans'),
    'receipts',          (select count(*) from public.bookings where receipt_path is not null)
  ));
end $fn$;

revoke all on function public.admin_snapshot() from public, anon;
grant execute on function public.admin_snapshot() to authenticated;

/* ═══ الاستعادة ════════════════════════════════════════════════════════
   الوعد قائم كما هو: ما في القاعدة الآن لا يُستبدل ولا يُحذف — تُعاد
   الصفوف الغائبة وحدها (`on conflict do nothing`). واستثناؤه الوحيد
   عدّادُ الأرقام: يأخذ الأكبر، فلا يرجع إلى الوراء فيتكرّر رقمُ حجز. */

create or replace function public.admin_restore_snapshot(
  p_data jsonb, p_include_settings boolean default false)
returns jsonb
language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
declare
  n_svc int := 0; n_rule int := 0; n_ovr int := 0; n_bk int := 0; n_it int := 0;
  n_tpl int := 0; n_out int := 0; n_ref int := 0; n_vis int := 0;
  n_act int := 0; n_scan int := 0;
  v_ver text;
begin
  if not public.is_admin() then
    raise exception 'not authorised' using errcode = '42501';
  end if;

  v_ver := coalesce(p_data->>'version', '');
  if v_ver not in ('1', '2') then
    raise exception 'unknown backup format' using errcode = '22023';
  end if;

  -- الخدمات أوّلًا: البنود تشير إليها.
  with src as (select * from jsonb_populate_recordset(null::public.services,
                                 coalesce(p_data->'services', '[]'::jsonb)))
  , ins as (insert into public.services select * from src
            on conflict (id) do nothing returning 1)
  select count(*) into n_svc from ins;

  with src as (select * from jsonb_populate_recordset(null::public.availability_rules,
                                 coalesce(p_data->'availability_rules', '[]'::jsonb)))
  , ins as (insert into public.availability_rules select * from src
            on conflict (id) do nothing returning 1)
  select count(*) into n_rule from ins;

  with src as (select * from jsonb_populate_recordset(null::public.date_overrides,
                                 coalesce(p_data->'date_overrides', '[]'::jsonb)))
  , ins as (insert into public.date_overrides select * from src
            on conflict (id) do nothing returning 1)
  select count(*) into n_ovr from ins;

  with src as (select * from jsonb_populate_recordset(null::public.bookings,
                                 coalesce(p_data->'bookings', '[]'::jsonb)))
  , ins as (insert into public.bookings select * from src
            on conflict (id) do nothing returning 1)
  select count(*) into n_bk from ins;

  -- البنود تُدرج فقط لحجزٍ صار موجودًا، وإلّا سقطت على مفتاحٍ أجنبيّ.
  with src as (select * from jsonb_populate_recordset(null::public.booking_items,
                                 coalesce(p_data->'booking_items', '[]'::jsonb)))
  , ins as (insert into public.booking_items
            select s.* from src s
             where exists (select 1 from public.bookings b where b.id = s.booking_id)
            on conflict (id) do nothing returning 1)
  select count(*) into n_it from ins;

  -- القوالب قبل الطابور: الطابور يشير إليها.
  with src as (select * from jsonb_populate_recordset(null::public.message_templates,
                                 coalesce(p_data->'message_templates', '[]'::jsonb)))
  , ins as (insert into public.message_templates select * from src
            on conflict (id) do nothing returning 1)
  select count(*) into n_tpl from ins;

  with src as (select * from jsonb_populate_recordset(null::public.message_outbox,
                                 coalesce(p_data->'message_outbox', '[]'::jsonb)))
  , ins as (insert into public.message_outbox
            select s.* from src s
             where (s.booking_id is null
                    or exists (select 1 from public.bookings b where b.id = s.booking_id))
               and (s.template_id is null
                    or exists (select 1 from public.message_templates t where t.id = s.template_id))
            on conflict (id) do nothing returning 1)
  select count(*) into n_out from ins;

  with src as (select * from jsonb_populate_recordset(null::public.activity_log,
                                 coalesce(p_data->'activity_log', '[]'::jsonb)))
  , ins as (insert into public.activity_log
            select s.* from src s
             where s.booking_id is null
                or exists (select 1 from public.bookings b where b.id = s.booking_id)
            on conflict (id) do nothing returning 1)
  select count(*) into n_act from ins;

  with src as (select * from jsonb_populate_recordset(null::public.visits,
                                 coalesce(p_data->'visits', '[]'::jsonb)))
  , ins as (insert into public.visits select * from src
            on conflict (id) do nothing returning 1)
  select count(*) into n_vis from ins;

  with src as (select * from jsonb_populate_recordset(null::public.receipt_scans,
                                 coalesce(p_data->'receipt_scans', '[]'::jsonb)))
  , ins as (insert into public.receipt_scans select * from src
            on conflict (path) do nothing returning 1)
  select count(*) into n_scan from ins;

  /* العدّاد لا يرجع إلى الوراء: رقمُ حجزٍ يتكرّر خطأٌ لا يُصلَح بعدها. */
  with src as (select * from jsonb_populate_recordset(null::public.ref_counters,
                                 coalesce(p_data->'ref_counters', '[]'::jsonb)))
  , ins as (insert into public.ref_counters select * from src
            on conflict (period) do update
              set n = greatest(public.ref_counters.n, excluded.n) returning 1)
  select count(*) into n_ref from ins;

  /* الإعدادات: تُدمج بكلّ أعمدتها لا بقائمةٍ مكتوبة باليد. كانت القائمة
     تتخلّف عن المخطّط فتضيع اثنا عشر إعدادًا صامتةً عند الاستعادة —
     منها نسبةُ العربون ورقمُ واتساب. وما لا تحمله النسخة القديمة يبقى
     على قيمته الحالية. */
  if p_include_settings and p_data ? 'settings' then
    execute (
      select 'update public.settings s set '
             || string_agg(format('%I = m.%I', column_name, column_name), ', ')
             || ', updated_at = now()'
             || ' from jsonb_populate_record(null::public.settings, $1) m where s.id = 1'
        from information_schema.columns
       where table_schema = 'public' and table_name = 'settings'
         and column_name not in ('id', 'updated_at')
    ) using ((select to_jsonb(s) from public.settings s where s.id = 1)
             || ((p_data->'settings') - 'id' - 'updated_at'));
  end if;

  -- المجاميع يحسبها المشغّل عند الإدراج، لكن حجزًا عاد بلا بنودٍ جديدة
  -- (لأنّها موجودة أصلًا) لا يمرّ عليه المشغّل، فنُعيد الحساب صراحةً.
  perform public.recalc_booking(b.id) from public.bookings b
   where b.id in (select (x->>'id')::uuid
                    from jsonb_array_elements(coalesce(p_data->'bookings','[]'::jsonb)) x);

  return jsonb_build_object(
    'services', n_svc, 'rules', n_rule, 'overrides', n_ovr,
    'bookings', n_bk, 'booking_items', n_it,
    'message_templates', n_tpl, 'message_outbox', n_out,
    'ref_counters', n_ref, 'visits', n_vis,
    'activity_log', n_act, 'receipt_scans', n_scan,
    'settings_restored', (p_include_settings and p_data ? 'settings'));
end $fn$;

revoke all on function public.admin_restore_snapshot(jsonb, boolean) from public, anon;
grant execute on function public.admin_restore_snapshot(jsonb, boolean) to authenticated;
