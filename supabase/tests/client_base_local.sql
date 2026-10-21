-- قاعدة العميلات على Postgres محلّيّ — لا على الحيّ.
--
-- الحيّ لا يقبل تجربةَ حذفٍ من أداة الإدارة، والحذفُ هو أدقُّ ما في هذه
-- الميزة: حذفُ حجزٍ بعينه يُخرج العميلة، والحذفُ الجماعيّ لا يُخرجها. فيُفحص
-- هنا على قاعدةٍ فارغة: مخطّطٌ مصغّر لـ`bookings` بالأعمدة التي يقرؤها
-- المشغّل، ثمّ «النواة» من الترحيل ٠٠٣٩ كما هي حرفًا بحرف، ثمّ الحالات.
--
--   bash supabase/tests/run_local.sh client_base_local.sql
--
-- الرسالة الأخيرة هي النتيجة: `ROLLBACK_OK ok=N bad=0`.

-- ── مخطّطٌ مصغّر ──────────────────────────────────────────────────────
create type public.booking_status as enum
  ('pending','confirmed','done','cancelled','rejected','no_show');
create table public.bookings (
  id uuid primary key default gen_random_uuid(),
  client_name text, client_phone text, the_date date, status public.booking_status,
  price numeric(10,2) default 0, loc_text text, loc_map text, loc_district text,
  source text default 'client', created_at timestamptz default now()
);
create table public.admins (user_id uuid primary key);
create or replace function public.is_admin() returns boolean language sql stable as $$
  select coalesce(current_setting('test.admin', true), '') = '1';
$$;
-- نسخةٌ من الحذف الجماعيّ بالسطرين اللذين يعنيان هنا: الراية ثمّ الحذف.
create or replace function public.admin_purge_bookings(p_from date, p_to date, p_dry boolean)
returns void language plpgsql as $$
begin
  if not p_dry then
    perform set_config('app.purging', '1', true);
    delete from public.bookings where the_date between p_from and p_to;
    perform set_config('app.purging', '', true);
  end if;
end $$;
create role anon; create role authenticated; create role service_role;

-- ── النواة من ٠٠٣٩ ─────────────────────────────────────────────────────
\i :core

-- ── الحالات ────────────────────────────────────────────────────────────
do $t$
declare n int; r text := ''; okc int := 0; badc int := 0; c record;
        a uuid; b uuid; x uuid;
begin
  -- ١) الإضافة: من الرابط ويدويًّا سواء
  insert into public.bookings (client_name, client_phone, the_date, status, price, loc_text, source, created_at)
  values ('نورة', '966500000001', '2026-01-10', 'done', 2000, 'حي الشفا', 'client', '2026-01-01')
  returning id into a;
  insert into public.bookings (client_name, client_phone, the_date, status, price, source, created_at)
  values ('نورة العتيبي', '966500000001', '2026-03-05', 'confirmed', 800, 'admin', '2026-02-20')
  returning id into b;
  select count(*) into n from public.client_history where phone = '966500000001';
  if n = 2 then okc:=okc+1; else badc:=badc+1; r:=r||' [1 '||n||']'; end if;

  -- ٢) القاعدة: صفٌّ واحد، الاسمُ الأحدث، والموقعُ آخرُ ما عُرف
  perform set_config('test.admin', '1', true);
  select * into c from public.admin_clients() where phone = '966500000001';
  if c.name = 'نورة العتيبي' and c.loc = 'حي الشفا' and c.bookings = 2 and c.total = 2800
     and c.first_at = '2026-01-01'::timestamptz and c.last_date = '2026-03-05'
  then okc:=okc+1; else badc:=badc+1; r:=r||' [2 '||row_to_json(c)::text||']'; end if;

  -- ٣) التعديل يصل، والملغى لا يُعدّ ولا يُجمع — والعميلة تبقى
  update public.bookings set status = 'cancelled' where id = b;
  select * into c from public.admin_clients() where phone = '966500000001';
  if c.bookings = 1 and c.total = 2000 and c.last_date = '2026-01-10'
  then okc:=okc+1; else badc:=badc+1; r:=r||' [3 '||row_to_json(c)::text||']'; end if;

  -- ٤) حذفُ حجزٍ بعينه يُخرجه من السجلّ
  delete from public.bookings where id = b;
  select count(*) into n from public.client_history where booking_id = b;
  if n = 0 then okc:=okc+1; else badc:=badc+1; r:=r||' [4]'; end if;

  -- ٥) والحذفُ الجماعيّ لا يُخرج العميلة ولا ينقص حسابها
  perform public.admin_purge_bookings('2026-01-01', '2026-01-31', false);
  select count(*) into n from public.bookings where id = a;
  select * into c from public.admin_clients() where phone = '966500000001';
  if n = 0 and c.bookings = 1 and c.total = 2000
  then okc:=okc+1; else badc:=badc+1; r:=r||' [5 حجز='||n||' '||coalesce(row_to_json(c)::text,'∅')||']'; end if;

  -- ٦) والراية تغطّي حذفها وحده: حذفٌ مفرد بعده في المعاملة نفسها يُخرج سطره
  insert into public.bookings (client_name, client_phone, the_date, status, price, created_at)
  values ('ريم', '966500000002', '2026-05-01', 'pending', 500, '2026-04-01') returning id into x;
  insert into public.bookings (client_name, client_phone, the_date, status, price, created_at)
  values ('خطأ', '966500000009', '2026-05-02', 'pending', 1, '2026-04-02') returning id into b;
  delete from public.bookings where id = b;
  select count(*) into n from public.client_history where booking_id = b;
  if n = 0 and coalesce(current_setting('app.purging', true), '') = '' then okc:=okc+1;
  else badc:=badc+1; r:=r||' [6 بقي='||n||']'; end if;

  -- ٧) عطبُ السجلّ لا يُسقط حجزًا
  alter table public.client_history rename to client_history_off;
  insert into public.bookings (client_name, client_phone, the_date, status, price)
  values ('هند', '966500000003', '2026-06-01', 'pending', 300);
  select count(*) into n from public.bookings where client_phone = '966500000003';
  alter table public.client_history_off rename to client_history;
  if n = 1 then okc:=okc+1; else badc:=badc+1; r:=r||' [7]'; end if;

  -- ٨) غيرُ المديرة لا ترى شيئًا
  perform set_config('test.admin', '', true);
  select count(*) into n from public.admin_clients();
  if n = 0 then okc:=okc+1; else badc:=badc+1; r:=r||' [8 '||n||']'; end if;

  -- ٩) والترتيب: الأحدث تسجيلًا أوّلًا
  perform set_config('test.admin', '1', true);
  select phone into c from public.admin_clients() limit 1;
  if c.phone = '966500000002' then okc:=okc+1; else badc:=badc+1; r:=r||' [9 '||c.phone||']'; end if;

  raise exception 'ROLLBACK_OK ok=% bad=% %', okc, badc, r;
end $t$;
