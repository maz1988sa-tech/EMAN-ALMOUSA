-- الزوّار: عدٌّ بلا تعرّف.
--
-- تريد إيمان أن تعرف كم زارها، وكم بقي، وكم حجز. وهذا يُعرَف بالعدّ لا
-- بالتتبّع: لا اسم، ولا عنوان شبكة، ولا بصمة متصفّح، ولا صفحةٌ خارج
-- موقعها. معرّفٌ عشوائيّ يصنعه المتصفّح ويحفظه عنده، إن مسحه صار زائرًا
-- جديدًا — وهذا مقبول، فالمطلوب مقياسٌ لا هويّة.
--
-- ولا يُقرأ من هذا الجدول سطرٌ واحد في اللوحة: تُقرأ الحصائل مجموعةً.
-- فما لا يُعرض لا يُساء استعماله.
--
-- والمختبر لا يُحسب: تجاربُنا ليست زيارات.

create table if not exists public.visits (
  id           uuid primary key default gen_random_uuid(),
  vid          text        not null,
  started_at   timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  max_step     smallint    not null default 0,
  booked       boolean     not null default false,
  is_new       boolean     not null default false,
  ref_host     text,
  device       text,
  day          date        not null default ((now() at time zone 'Asia/Riyadh')::date)
);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'visits_device_ck') then
    alter table public.visits add constraint visits_device_ck
      check (device is null or device in ('mobile', 'desktop'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'visits_step_ck') then
    alter table public.visits add constraint visits_step_ck
      check (max_step between 0 and 9);
  end if;
end $$;

create index if not exists visits_day_idx on public.visits (day);
create index if not exists visits_vid_day_idx on public.visits (vid, day);

alter table public.visits enable row level security;
-- لا سياسةَ قراءةٍ لأحد: الحصائل تُقرأ بدالّةٍ مالكة، والسطر لا يُعرض.

/* ═══ التسجيل ══════════════════════════════════════════════════════════
   ثلاث نداءات من الصفحة: بدءُ زيارة، ونبضةٌ كلَّ حين تقول «ما زلتُ هنا
   وبلغتُ هذه الشاشة»، وعلامةٌ عند إتمام الحجز. ولا شيء منها يُصدَّق في
   حسابٍ ماليّ — إنّما عدٌّ. */

create or replace function public.track_visit(
  p_vid text, p_new boolean default false,
  p_ref text default null, p_device text default null)
returns uuid
language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
declare v_id uuid; v_vid text; v_today date;
begin
  v_vid := substr(regexp_replace(coalesce(p_vid, ''), '[^a-zA-Z0-9-]', '', 'g'), 1, 64);
  if length(v_vid) < 8 then return null; end if;
  v_today := (now() at time zone 'Asia/Riyadh')::date;

  -- سقفٌ للمتصفّح الواحد في اليوم: يمنع نفخ العدّ بإعادة تحميلٍ متكرّرة،
  -- ولا يضرّ زائرةً تفتح الصفحة مرّاتٍ معدودة.
  if (select count(*) from public.visits
       where vid = v_vid and day = v_today) >= 40 then
    return null;
  end if;

  insert into public.visits (vid, is_new, ref_host, device, day)
  values (v_vid, coalesce(p_new, false),
          nullif(substr(regexp_replace(coalesce(p_ref, ''), '[^a-zA-Z0-9.:-]', '', 'g'), 1, 80), ''),
          case when p_device in ('mobile', 'desktop') then p_device end,
          v_today)
  returning id into v_id;
  return v_id;
end $fn$;
revoke all on function public.track_visit(text, boolean, text, text) from public;
grant execute on function public.track_visit(text, boolean, text, text) to anon, authenticated;

create or replace function public.track_ping(p_id uuid, p_step integer default 0)
returns void
language sql security definer set search_path to 'public', 'pg_temp'
as $$
  update public.visits
     set last_seen_at = now(),
         max_step = greatest(max_step, least(greatest(coalesce(p_step, 0), 0), 9))
   where id = p_id
     -- زيارةٌ مضى عليها أكثر من ستّ ساعات لا تُمدَّد: لسانُ تبويبٍ نُسي
     -- مفتوحًا ليس بقاءً.
     and started_at > now() - interval '6 hours';
$$;
revoke all on function public.track_ping(uuid, integer) from public;
grant execute on function public.track_ping(uuid, integer) to anon, authenticated;

create or replace function public.track_booked(p_id uuid)
returns void
language sql security definer set search_path to 'public', 'pg_temp'
as $$
  update public.visits set booked = true, last_seen_at = now()
   where id = p_id and started_at > now() - interval '6 hours';
$$;
revoke all on function public.track_booked(uuid) from public;
grant execute on function public.track_booked(uuid) to anon, authenticated;

/* ═══ الحصائل ══════════════════════════════════════════════════════════
   «زائر» هو متصفّحٌ مختلف لا فتحةُ صفحة. والبقاء يُحسب من الجلسات التي
   بقيت فعلًا — والزيارة التي لم تُنبض ولو مرّة لا زمنَ لها فلا تُحسب في
   المتوسّط، وإلّا جرّته إلى الصفر. */

drop function if exists public.admin_visits(date, date);
create function public.admin_visits(p_from date, p_to date)
returns TABLE (
  visitors      bigint,
  sessions      bigint,
  new_visitors  bigint,
  bounced       bigint,
  reached_form  bigint,
  booked        bigint,
  avg_seconds   integer,
  med_seconds   integer
)
language sql stable security definer set search_path to 'public', 'pg_temp'
as $$
  with v as (
    select *, extract(epoch from (last_seen_at - started_at))::int as secs
      from public.visits
     where public.is_admin() and day between p_from and p_to
  )
  select
    (select count(distinct vid) from v),
    (select count(*) from v),
    (select count(distinct vid) from v where is_new),
    -- «دخل وخرج»: لم يتجاوز الشاشة الأولى قطّ.
    (select count(*) from v where max_step = 0),
    (select count(*) from v where max_step >= 3),
    (select count(*) from v where booked),
    (select coalesce(round(avg(secs))::int, 0) from v where secs > 0),
    (select coalesce(percentile_disc(0.5) within group (order by secs), 0)::int
       from v where secs > 0);
$$;
revoke all on function public.admin_visits(date, date) from public, anon;
grant execute on function public.admin_visits(date, date) to authenticated;

/** الشهور: صفٌّ لكلّ شهرٍ فيه زيارة، من الأحدث. */
drop function if exists public.admin_visits_monthly(integer);
create function public.admin_visits_monthly(p_months integer default 12)
returns TABLE (
  ym text, visitors bigint, sessions bigint, booked bigint, avg_seconds integer
)
language sql stable security definer set search_path to 'public', 'pg_temp'
as $$
  select to_char(date_trunc('month', day), 'YYYY-MM'),
         count(distinct vid), count(*), count(*) filter (where booked),
         coalesce(round(avg(extract(epoch from (last_seen_at - started_at))
                            ) filter (where last_seen_at > started_at))::int, 0)
    from public.visits
   where public.is_admin()
     and day >= (date_trunc('month', (now() at time zone 'Asia/Riyadh')::date)
                 - make_interval(months => greatest(coalesce(p_months, 12), 1) - 1))::date
   group by 1
   order by 1 desc;
$$;
revoke all on function public.admin_visits_monthly(integer) from public, anon;
grant execute on function public.admin_visits_monthly(integer) to authenticated;

/* ما مضى عليه سنةٌ يُمسح: العدّ يفيد قريبًا، وحفظُه أبدًا بلا سببٍ
   احتفاظٌ لا يُبرَّر. */
create or replace function public.purge_old_visits()
returns integer
language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
declare n integer;
begin
  delete from public.visits where day < current_date - 400;
  get diagnostics n = row_count;
  return n;
end $fn$;
revoke all on function public.purge_old_visits() from public, anon, authenticated;

do $$
begin perform cron.unschedule('purge-old-visits'); exception when others then null; end $$;
select cron.schedule('purge-old-visits', '17 3 * * 0', $$select public.purge_old_visits();$$);
