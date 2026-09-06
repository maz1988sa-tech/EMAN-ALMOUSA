-- الاستعادة تُعيد ما كان، ولا تُخضعه لقواعد الاستقبال.
--
-- ظهر هذا في دورةٍ كاملة على القاعدة الحيّة (داخل معاملة أُرجعت): استعادةُ
-- لقطةٍ سقطت كلُّها برسالة «رابط الموقع من خرائط قوقل مطلوب». والسبب أنّ
-- صفوف الحجوزات تمرّ على مشغّلات الإدخال نفسها التي تحكم العميلة وهي
-- تحجز. فحجزٌ قديم سابقٌ لسنّ القاعدة — أو حجزٌ أدخلته صاحبة العمل بلا
-- رابط — يُسقط الاستعادة بأكملها. أي أنّ النسخة كانت تُؤخذ ولا تُستعاد.
--
-- وأخطرُ منه صامتًا: مشغّلُ الرسائل التلقائية يجدول رسائل لكلّ حجزٍ
-- يُدرَج. فاستعادةُ نسخةٍ بعد ربط واتساب كانت سترسل تأكيداتٍ وتذكيراتٍ
-- إلى عميلاتٍ انتهت مواعيدهنّ من شهور.
--
-- العلاج: رايةٌ تعيش داخل المعاملة وحدها (`set_config(..., true)`)،
-- ترفعها الاستعادة وتخفضها نهايةُ المعاملة مهما كان مآلها. ولا تُعطَّل
-- بها مشغّلاتُ السلامة: إسنادُ الرقم عند غيابه، ومزامنةُ البنود، وإعادةُ
-- حساب المجاميع — كلُّها تعمل كما هي.

/* راية الاستعادة: مقروءة في سطرٍ واحد، ولا تُورَّث خارج المعاملة. */
create or replace function public.restoring()
returns boolean
language sql stable
as $$ select coalesce(current_setting('app.restoring', true), '') = '1' $$;

/* رابط الخرائط شرطُ حجزٍ جديد، لا شرطُ صفٍّ يعود إلى مكانه. */
create or replace function public.bookings_require_map()
returns trigger
language plpgsql
as $fn$
declare v_need boolean;
begin
  if public.restoring() then return new; end if;
  if new.source = 'client' then
    select require_loc_map into v_need from public.settings where id = 1;
    if coalesce(v_need, false)
       and nullif(btrim(coalesce(new.loc_map, '')), '') is null then
      raise exception 'رابط الموقع من خرائط قوقل مطلوب لتثبيت الموعد'
        using errcode = 'P0001';
    end if;
  end if;
  return new;
end $fn$;

/* حجزٌ يعود من نسخةٍ ليس حجزًا جديدًا، فلا يُجدوَل له تأكيدٌ ولا تذكير. */
create or replace function public.tg_schedule_auto_messages()
returns trigger
language plpgsql
as $fn$
begin
  if public.restoring() then return null; end if;
  perform public.schedule_auto_messages(new.id);
  return null;
exception when others then
  raise warning 'schedule_auto_messages failed for %: %', new.id, sqlerrm;
  return null;
end $fn$;

/* ترفعها الاستعادة أوّل ما تتحقّق من الصلاحية. */
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

  -- داخل المعاملة وحدها: تسقط مع نهايتها نجحت أو سقطت.
  perform set_config('app.restoring', '1', true);

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

  with src as (select * from jsonb_populate_recordset(null::public.booking_items,
                                 coalesce(p_data->'booking_items', '[]'::jsonb)))
  , ins as (insert into public.booking_items
            select s.* from src s
             where exists (select 1 from public.bookings b where b.id = s.booking_id)
            on conflict (id) do nothing returning 1)
  select count(*) into n_it from ins;

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

  with src as (select * from jsonb_populate_recordset(null::public.ref_counters,
                                 coalesce(p_data->'ref_counters', '[]'::jsonb)))
  , ins as (insert into public.ref_counters select * from src
            on conflict (period) do update
              set n = greatest(public.ref_counters.n, excluded.n) returning 1)
  select count(*) into n_ref from ins;

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
