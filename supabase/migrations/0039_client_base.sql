-- ٠٠٣٩ — قاعدة العميلات.
--
-- كلُّ من حجزت — من الرابط أو يدويًّا — عميلةٌ في قاعدة صاحبة العمل: اسمها
-- وجوّالها وموقعها، وكم حجزت وبكم، ومتى سُجّلت أوّل مرّة.
--
-- **ولا تُشتقّ من `bookings` وحدها.** الحذف الجماعيّ (`admin_purge_bookings`)
-- يمحو الحجوزات في نطاقٍ — أو كلّها — لينظّف التقويم؛ وقاعدةٌ مشتقّة منها
-- كانت ستُمحى معها، فتذهب العميلات بتنظيف تقويم. فسجلٌّ مستقلّ:
-- `client_history` — سطرٌ لكلّ حجزٍ مرّ، يكتبه مشغّلٌ على `bookings`.
--
-- - **الإضافة والتعديل** يُكتبان فيه، فكلُّ طريقٍ للحجز يصل وحده: رابط
--   العميلة، والحجز اليدويّ، والجماعيّ، والاستعادة.
-- - **وحذفُ حجزٍ بعينه يُحذف منه** — حجزٌ وُضع خطأً لا يُعدّ عميلة.
-- - **والحذف الجماعيّ لا يُحذف منه** — يرفع رايةَ `app.purging` داخل
--   معاملته (نمطُ `app.restoring` في §٧ج) فيُبقي المشغّلُ السطور.
-- - **وعطبُه لا يُسقط حجزًا.** السجلّ تابعٌ للحجز لا شرطٌ عليه: يُلتقط
--   خطؤه ويُكتب تحذيرًا في سجلّ القاعدة ويمضي الحجز. وقع أن ضاع حجزُ
--   عميلة بحارسٍ لم يمتنع من نفسه (§٧د) — وهذا أحرى ألّا يكون حارسًا.
--
-- والحساب في `admin_clients`: الحجوزات القائمة ما لم تُلغَ أو يُعتذر عنها،
-- والمبلغ `price` نفسه الذي يجمعه «إجمالي المعروض». والمفتاح رقمُ الجوال
-- المطبَّع (9665XXXXXXXX) — والاسم والموقع من أحدث حجز، فالأحدث أصدق.

-- ⟪core⟫ — ما بين العلامتين مستقلٌّ بنفسه: يُشغَّل كما هو على قاعدةٍ محلّيّة
-- في `supabase/tests/client_base_local.sql` فيُفحص الحذف المفرد والجماعيّ
-- على Postgres حقيقيّ بلا مساسٍ بالحيّ.
create table if not exists public.client_history (
  booking_id   uuid primary key,
  phone        text,
  name         text,
  loc_text     text,
  loc_map      text,
  loc_district text,
  the_date     date,
  booked_at    timestamptz not null default now(),
  price        numeric(12,2) not null default 0,
  status       text,
  source       text,
  updated_at   timestamptz not null default now()
);
create index if not exists client_history_phone_idx on public.client_history (phone);

comment on table public.client_history is
  'سجلّ قاعدة العميلات: سطرٌ لكلّ حجزٍ مرّ. يُكتب من bookings بمشغّل، ويبقى بعد الحذف الجماعيّ.';

-- لا سياسةَ قراءةٍ لأحد: يُقرأ بدالّةٍ مالكة وحدها (نمطُ `visits` في §٧ب).
alter table public.client_history enable row level security;
revoke all on public.client_history from anon, authenticated;

create or replace function public.tg_client_history()
returns trigger
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $fn$
begin
  begin
    if tg_op = 'DELETE' then
      if coalesce(current_setting('app.purging', true), '') <> '1' then
        delete from public.client_history where booking_id = old.id;
      end if;
      return old;
    end if;

    insert into public.client_history as h
      (booking_id, phone, name, loc_text, loc_map, loc_district,
       the_date, booked_at, price, status, source, updated_at)
    values
      (new.id, nullif(btrim(coalesce(new.client_phone, '')), ''),
       nullif(btrim(coalesce(new.client_name, '')), ''),
       nullif(btrim(coalesce(new.loc_text, '')), ''),
       nullif(btrim(coalesce(new.loc_map, '')), ''),
       nullif(btrim(coalesce(new.loc_district, '')), ''),
       new.the_date, coalesce(new.created_at, now()), coalesce(new.price, 0),
       new.status::text, new.source, now())
    on conflict (booking_id) do update set
      phone = excluded.phone, name = excluded.name,
      loc_text = excluded.loc_text, loc_map = excluded.loc_map,
      loc_district = excluded.loc_district, the_date = excluded.the_date,
      price = excluded.price, status = excluded.status, source = excluded.source,
      updated_at = now();
  exception when others then
    raise warning 'client_history: % (booking %)', sqlerrm, coalesce(new.id, old.id);
  end;
  return coalesce(new, old);
end $fn$;
revoke execute on function public.tg_client_history() from public, anon, authenticated;

create trigger bookings_client_history
  after insert or update or delete on public.bookings
  for each row execute function public.tg_client_history();

-- العميلات الموجودات: يُبذَر السجلّ من الحجوزات القائمة اليوم.
insert into public.client_history
  (booking_id, phone, name, loc_text, loc_map, loc_district,
   the_date, booked_at, price, status, source, updated_at)
select b.id, nullif(btrim(coalesce(b.client_phone, '')), ''),
       nullif(btrim(coalesce(b.client_name, '')), ''),
       nullif(btrim(coalesce(b.loc_text, '')), ''),
       nullif(btrim(coalesce(b.loc_map, '')), ''),
       nullif(btrim(coalesce(b.loc_district, '')), ''),
       b.the_date, coalesce(b.created_at, now()), coalesce(b.price, 0),
       b.status::text, b.source, now()
  from public.bookings b
on conflict (booking_id) do nothing;

-- قاعدة العميلات كما تُعرض وتُصدَّر: صفٌّ لكلّ عميلة.
create or replace function public.admin_clients()
returns table(phone text, name text, loc text, loc_map text,
              bookings integer, total numeric, first_at timestamptz, last_date date)
language sql
stable
security definer
set search_path to 'public', 'pg_temp'
as $fn$
  with h as (
    select c.*, coalesce(c.phone, 'name:' || coalesce(c.name, '')) as k,
           c.status not in ('cancelled', 'rejected') as live
      from public.client_history c
     where public.is_admin()
  ), who as (
    select distinct on (k) k, h.phone, h.name from h order by k, h.booked_at desc
  ), place as (
    select distinct on (k) k, coalesce(h.loc_text, h.loc_district) as loc, h.loc_map
      from h where coalesce(h.loc_text, h.loc_district, h.loc_map) is not null
     order by k, h.booked_at desc
  ), agg as (
    select k, (count(*) filter (where live))::int as bookings,
           coalesce(sum(h.price) filter (where live), 0) as total,
           min(h.booked_at) as first_at,
           max(h.the_date) filter (where live) as last_date
      from h group by k
  )
  select w.phone, w.name, p.loc, p.loc_map, a.bookings, a.total, a.first_at, a.last_date
    from agg a join who w using (k) left join place p using (k)
   order by a.first_at desc;
$fn$;
revoke execute on function public.admin_clients() from public, anon;
grant execute on function public.admin_clients() to authenticated, service_role;
-- ⟪/core⟫

-- الحذف الجماعيّ واللقطة والاستعادة: تُشتقّ من تعريفاتها القائمة.
do $do$
declare v_src text; v_new text;
begin
  select pg_get_functiondef(p.oid) into v_src from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'admin_purge_bookings';
  v_new := replace(v_src, E'    delete from public.bookings where id = any(v_ids);', E'    -- الحذف الجماعيّ تنظيفُ تقويمٍ لا محوُ عميلات: يرفع رايةً يقرؤها مشغّل\n    -- السجلّ فيُبقي سطورَ هذه الحجوزات — ثمّ يُنزلها في السطر التالي، فلا\n    -- تغطّي إلّا هذا الحذف ولو جاء بعده حذفٌ مفرد في المعاملة نفسها.\n    perform set_config(''app.purging'', ''1'', true);\n    delete from public.bookings where id = any(v_ids);\n    perform set_config(''app.purging'', '''', true);');
  if v_new = v_src then raise exception 'لم يُعثر على الحذف في admin_purge_bookings'; end if;
  execute v_new;

  select pg_get_functiondef(p.oid) into v_src from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'admin_snapshot';
  v_new := replace(v_src, E'    ''hood_group_prices'',    coalesce((select jsonb_agg(to_jsonb(x) order by x.group_id, x.service_id) from public.hood_group_prices x), ''[]''::jsonb),', E'    ''hood_group_prices'',    coalesce((select jsonb_agg(to_jsonb(x) order by x.group_id, x.service_id) from public.hood_group_prices x), ''[]''::jsonb),\n    ''client_history'',       coalesce((select jsonb_agg(to_jsonb(x) order by x.booked_at) from public.client_history x), ''[]''::jsonb),');
  if v_new = v_src then raise exception 'لم يُعثر على مفتاح المجموعات في اللقطة'; end if;
  v_src := v_new;
  v_new := replace(v_src, E'    ''hood_group_prices'', jsonb_array_length(v->''hood_group_prices''),', E'    ''hood_group_prices'', jsonb_array_length(v->''hood_group_prices''),\n    ''client_history'', jsonb_array_length(v->''client_history''),');
  if v_new = v_src then raise exception 'لم يُعثر على عدّاد المجموعات في اللقطة'; end if;
  execute v_new;

  select pg_get_functiondef(p.oid) into v_src from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'admin_restore_snapshot';
  v_new := replace(v_src, E'  n_hg int := 0; n_hgd int := 0; n_hgp int := 0;', E'  n_hg int := 0; n_hgd int := 0; n_hgp int := 0; n_ch int := 0;');
  if v_new = v_src then raise exception 'لم يُعثر على التصريح في الاستعادة'; end if;
  v_src := v_new;
  v_new := replace(v_src, E'  select count(*) into n_hgp from ins;', E'  select count(*) into n_hgp from ins;\n\n  -- سجلُّ العميلات بعد الحجوزات: ما عاد من حجزٍ كتبه المشغّل، وما بقي هنا\n  -- لحجزٍ حُذف جماعيًّا يعود من النسخة. والمفتاح رقمُ الحجز فلا يتكرّر.\n  with src as (select * from jsonb_populate_recordset(null::public.client_history,\n                                 coalesce(p_data->''client_history'', ''[]''::jsonb)))\n  , ins as (insert into public.client_history select * from src\n            on conflict (booking_id) do nothing returning 1)\n  select count(*) into n_ch from ins;');
  if v_new = v_src then raise exception 'لم يُعثر على كتلة الأسعار في الاستعادة'; end if;
  v_src := v_new;
  v_new := replace(v_src, E'    ''hood_group_districts'', n_hgd, ''hood_group_prices'', n_hgp,', E'    ''hood_group_districts'', n_hgd, ''hood_group_prices'', n_hgp, ''client_history'', n_ch,');
  if v_new = v_src then raise exception 'لم يُعثر على سطر الحصيلة في الاستعادة'; end if;
  execute v_new;
end $do$;

revoke all on function public.admin_restore_snapshot(jsonb, boolean) from public, anon;
grant execute on function public.admin_restore_snapshot(jsonb, boolean) to authenticated;
grant execute on function public.admin_snapshot() to authenticated, service_role;
