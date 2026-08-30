-- رقم الطلب يقول متى كان: EA-20260900
--
-- كان الرقم خمسة أحرفٍ عشوائية (IA-7K3QP): فريدٌ نعم، لكنّه لا يقول شيئًا.
-- لا ترتيب فيه ولا تاريخ، ولا تعرف زوجتك من رقمين أيّهما أسبق.
--
-- الصيغة الجديدة تُقرأ من يسارها إلى يمينها:
--   EA        اختصار Eman Almousa
--   2026      السنة
--   09        الشهر
--   00        ترتيب الطلب في ذلك الشهر — أوّلُه صفر
--
-- والترتيب على وقت تسجيل الطلب لا على موعده: «الطلب الخامس» يعني خامس
-- ما وصلها في ذلك الشهر. ولو بُني على موعد الحفلة لقرأت في طلبٍ سجّلته
-- اليوم لحفلةٍ في ديسمبر أنّه من ديسمبر — وهو ليس كذلك.

-- عدّادٌ لكلِّ شهر. الزيادة والقراءة في جملةٍ واحدة، فطلبان يصلان في اللحظة
-- نفسها لا يأخذان الرقم نفسه.
create table if not exists public.ref_counters (
  period text primary key,          -- 'YYYYMM' بتوقيت المشروع
  n      integer not null default 0
);

alter table public.ref_counters enable row level security;
-- بلا سياسات: لا يمسّه إلّا ما يعمل بصلاحية المالك.

create or replace function public.gen_booking_ref()
returns text
language plpgsql volatile
security definer
set search_path = public, pg_temp
as $$
declare
  v_period text := to_char(public.local_now(), 'YYYYMM');
  v_n      integer;
begin
  insert into public.ref_counters (period, n) values (v_period, 0)
  on conflict (period) do update set n = public.ref_counters.n + 1
  returning n into v_n;

  -- خانتان تكفيان تسعةً وتسعين طلبًا في الشهر. وإن زادت اتّسع الرقم:
  -- lpad يقصّ ما طال عن طوله، فالمئة تصير «10» وتصطدم بالحادي عشر.
  return 'EA-' || v_period
       || case when v_n < 100 then lpad(v_n::text, 2, '0') else v_n::text end;
end;
$$;

revoke execute on function public.gen_booking_ref() from public, anon, authenticated;

-- ── ترقيم ما مضى ──────────────────────────────────────────────────────
-- كلُّ ما في الجدول يُعاد ترقيمه بالصيغة نفسها: أوّلُ كلِّ شهر صفر، فما
-- يُقرأ اليوم يُقرأ كما سيُقرأ غدًا. والأرقام القديمة لا تعود.
do $$
declare
  v_tz text := (select timezone from public.settings where id = 1);
begin
  with ordered as (
    select id,
           to_char(created_at at time zone v_tz, 'YYYYMM') as period,
           row_number() over (
             partition by to_char(created_at at time zone v_tz, 'YYYYMM')
             order by created_at, id
           ) - 1 as seq
      from public.bookings
  )
  update public.bookings b
     set ref = 'EA-' || o.period || lpad(o.seq::text, 2, '0')
    from ordered o
   where b.id = o.id;

  -- العدّادات تبدأ من حيث انتهى الترقيم، فلا يتكرّر رقمٌ مع أوّل طلبٍ جديد.
  insert into public.ref_counters (period, n)
  select to_char(created_at at time zone v_tz, 'YYYYMM'), count(*) - 1
    from public.bookings
   group by 1
  on conflict (period) do update set n = greatest(public.ref_counters.n, excluded.n);
end $$;
