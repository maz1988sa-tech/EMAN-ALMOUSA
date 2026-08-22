-- نسخة احتياطية سحابية، واستعادةٌ لا تحذف شيئًا.
--
-- الاستعادة تُرجع المفقود فقط: كل صفٍّ ما زال موجودًا يُترك كما هو. فلو
-- استعادت نسخةً قديمة بالخطأ لم تُمحَ حجوزات اليوم — وأسوأ ما قد تفعله
-- ميزةُ إنقاذ أن تصير هي الكارثة.
--
-- والصور تُنسخ إلى دلوٍ منفصل لا إلى دلو الإيصالات: كانس الملفّات اليتيمة
-- يمسح كل ما لا يشير إليه حجزٌ قائم، فنسخةٌ هناك كانت ستُمحى وحدها.

insert into storage.buckets (id, name, public, file_size_limit)
values ('backups', 'backups', false, 52428800)
on conflict (id) do nothing;

drop policy if exists "backups admin read"   on storage.objects;
drop policy if exists "backups admin write"  on storage.objects;
drop policy if exists "backups admin delete" on storage.objects;

create policy "backups admin read" on storage.objects
  for select to authenticated
  using (bucket_id = 'backups' and public.is_admin());

create policy "backups admin write" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'backups' and public.is_admin());

create policy "backups admin delete" on storage.objects
  for delete to authenticated
  using (bucket_id = 'backups' and public.is_admin());

-- ── اللقطة: كل ما يمكن أن يُفقد، في كائنٍ واحد ──────────────────────────
create or replace function public.admin_snapshot()
returns jsonb
language plpgsql
stable
security definer
set search_path to 'public', 'pg_temp'
as $$
declare v jsonb;
begin
  if not public.is_admin() then
    raise exception 'not authorised' using errcode = '42501';
  end if;

  select jsonb_build_object(
    'version', 1,
    'taken_at', now(),
    'settings',           (select to_jsonb(s) from public.settings s where s.id = 1),
    'services',           coalesce((select jsonb_agg(to_jsonb(x) order by x.sort)       from public.services x), '[]'::jsonb),
    'availability_rules', coalesce((select jsonb_agg(to_jsonb(x))                       from public.availability_rules x), '[]'::jsonb),
    'date_overrides',     coalesce((select jsonb_agg(to_jsonb(x) order by x.the_date)   from public.date_overrides x), '[]'::jsonb),
    'bookings',           coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at) from public.bookings x), '[]'::jsonb),
    'booking_items',      coalesce((select jsonb_agg(to_jsonb(x))                       from public.booking_items x), '[]'::jsonb)
  ) into v;

  return v || jsonb_build_object('counts', jsonb_build_object(
    'bookings',      jsonb_array_length(v->'bookings'),
    'booking_items', jsonb_array_length(v->'booking_items'),
    'services',      jsonb_array_length(v->'services'),
    'rules',         jsonb_array_length(v->'availability_rules'),
    'overrides',     jsonb_array_length(v->'date_overrides'),
    'receipts',      (select count(*) from public.bookings where receipt_path is not null)
  ));
end;
$$;

-- ── الاستعادة: تُدرج المفقود ولا تمسّ الموجود ───────────────────────────
create or replace function public.admin_restore_snapshot(
  p_data jsonb,
  p_include_settings boolean default false
)
returns jsonb
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $$
declare
  n_svc int := 0; n_rule int := 0; n_ovr int := 0; n_bk int := 0; n_it int := 0;
begin
  if not public.is_admin() then
    raise exception 'not authorised' using errcode = '42501';
  end if;

  if coalesce(p_data->>'version', '') <> '1' then
    raise exception 'unknown backup format' using errcode = '22023';
  end if;

  -- الخدمات أوّلًا: البنود تشير إليها.
  with src as (select * from jsonb_populate_recordset(null::public.services,
                                 coalesce(p_data->'services', '[]'::jsonb)))
  , ins as (
    insert into public.services select * from src
    on conflict (id) do nothing returning 1)
  select count(*) into n_svc from ins;

  with src as (select * from jsonb_populate_recordset(null::public.availability_rules,
                                 coalesce(p_data->'availability_rules', '[]'::jsonb)))
  , ins as (
    insert into public.availability_rules select * from src
    on conflict (id) do nothing returning 1)
  select count(*) into n_rule from ins;

  with src as (select * from jsonb_populate_recordset(null::public.date_overrides,
                                 coalesce(p_data->'date_overrides', '[]'::jsonb)))
  , ins as (
    insert into public.date_overrides select * from src
    on conflict (id) do nothing returning 1)
  select count(*) into n_ovr from ins;

  with src as (select * from jsonb_populate_recordset(null::public.bookings,
                                 coalesce(p_data->'bookings', '[]'::jsonb)))
  , ins as (
    insert into public.bookings select * from src
    on conflict (id) do nothing returning 1)
  select count(*) into n_bk from ins;

  -- البنود تُدرج فقط لحجزٍ صار موجودًا، وإلّا سقطت على مفتاحٍ أجنبيّ.
  with src as (select * from jsonb_populate_recordset(null::public.booking_items,
                                 coalesce(p_data->'booking_items', '[]'::jsonb)))
  , ins as (
    insert into public.booking_items
    select s.* from src s
     where exists (select 1 from public.bookings b where b.id = s.booking_id)
    on conflict (id) do nothing returning 1)
  select count(*) into n_it from ins;

  if p_include_settings and p_data ? 'settings' then
    update public.settings s set
      business_name = coalesce(d.business_name, s.business_name),
      tagline = d.tagline, timezone = coalesce(d.timezone, s.timezone),
      slot_step_min = coalesce(d.slot_step_min, s.slot_step_min),
      min_lead_hours = coalesce(d.min_lead_hours, s.min_lead_hours),
      max_advance_days = coalesce(d.max_advance_days, s.max_advance_days),
      whatsapp_phone = d.whatsapp_phone,
      accepting_bookings = coalesce(d.accepting_bookings, s.accepting_bookings),
      closed_message = d.closed_message,
      bank_name = d.bank_name, iban = d.iban, beneficiary_name = d.beneficiary_name,
      instagram_url = d.instagram_url, tiktok_url = d.tiktok_url,
      group_discount_amount = coalesce(d.group_discount_amount, s.group_discount_amount),
      receipt_ocr_required = coalesce(d.receipt_ocr_required, s.receipt_ocr_required),
      updated_at = now()
    from jsonb_populate_record(null::public.settings, p_data->'settings') d
    where s.id = 1;
  end if;

  -- المجاميع يحسبها المشغّل عند الإدراج، لكن حجزًا عاد بلا بنودٍ جديدة
  -- (لأنّها موجودة أصلًا) لا يمرّ عليه المشغّل، فنُعيد الحساب صراحةً.
  perform public.recalc_booking(b.id) from public.bookings b
   where b.id in (select (x->>'id')::uuid
                    from jsonb_array_elements(coalesce(p_data->'bookings','[]'::jsonb)) x);

  return jsonb_build_object(
    'services', n_svc, 'rules', n_rule, 'overrides', n_ovr,
    'bookings', n_bk, 'booking_items', n_it,
    'settings_restored', (p_include_settings and p_data ? 'settings'));
end;
$$;

revoke all on function public.admin_snapshot()                          from public;
revoke all on function public.admin_restore_snapshot(jsonb, boolean)    from public;
grant execute on function public.admin_snapshot()                       to authenticated;
grant execute on function public.admin_restore_snapshot(jsonb, boolean) to authenticated;
