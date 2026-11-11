-- ٠٠٤٠ ترحيب العميلة العائدة (§٧ن في CLAUDE.md).
--
-- حين تكتب العميلة رقم جوّالها في «بياناتك» تسأل الصفحة: هل لهذا الرقم موعدٌ مكتمل؟
-- فإن كان، ظهر تحت الخانة «أهلًا بعودتك سارة، نوّرتينا من جديد». طلبه صاحب المشروع لتحسّ
-- العميلة أنّها معروفةٌ لا زائرةٌ أولى، واعتمد شكله وصياغته (١١ نوفمبر ٢٠٢٦).
--
-- **الجواب نعم أو لا وحسب: لا اسم ولا تاريخ ولا عدد.** الاسم في الرسالة ممّا كتبته العميلة
-- في الخانة الأولى؛ ولو ردّته القاعدة لعرف كلُّ من يكتب رقمًا اسمَ صاحبته. ويبقى أنّ من
-- يكتب رقم عميلةٍ يعرف أنّ لها موعدًا مكتملًا سابقًا — عُرض على صاحب المشروع فقبله.
--
-- **والسؤال محدودٌ للجميع معًا:** ١٠ في الدقيقة و٦٠ في الساعة، وما زاد يُجاب «لا» بصمت
-- ولا يرجع سببٌ إلى المتصفّح. فلا تُجرَّب قائمةُ أرقامٍ في جلسة: أقصى ما يُسأل ١٤٤٠ في اليوم.
-- والعدّاد بلا هويّة (§٧ب): لا رقم ولا عنوان شبكة — ستّون صفًّا لدقائق الساعة تدور على
-- نفسها، فلا يكبر الجدول ولا يحتاج تنظيفًا، ولا يدخل اللقطة (`snapshot_coverage.sql`).
--
-- **والمرجع `client_history` لا `bookings`** (§٧و): الحذف الجماعيّ لا يمحو من خلصت خدمتها،
-- والحذف المفرد يُخرج حجزًا وُضع خطأً. و«مكتملة» (`done`) وحدها تُعدّ: المؤكَّد الذي لم يأتِ
-- موعده ليس عودة. والمفتاح آخر تسعة أرقام، فـ«٠٥…» و«٩٦٦٥…» و«+966 5…» رقمٌ واحد.

-- ⟪core⟫
create table if not exists public.returning_checks (
  slot   smallint primary key check (slot between 0 and 59),
  minute timestamptz not null,
  n      integer not null default 0
);
comment on table public.returning_checks is
  'عدّاد سؤال is_returning_client: صفٌّ لكلّ دقيقةٍ من الساعة يدور على نفسه. بلا هويّة، وخارج اللقطة عن قصد.';
alter table public.returning_checks enable row level security;
revoke all on public.returning_checks from anon, authenticated;

create or replace function public.is_returning_client(p_phone text)
returns boolean
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $fn$
declare
  v_key  text := right(regexp_replace(
                   translate(coalesce(p_phone, ''), '٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'),
                   '[^0-9]', '', 'g'), 9);
  v_min  timestamptz := date_trunc('minute', now());
  v_n    integer;
  v_hour integer;
begin
  -- رقمٌ ناقص لا يُسأل عنه ولا يُحسب على الحدّ.
  if v_key !~ '^5[0-9]{8}$' then
    return false;
  end if;

  -- صفُّ هذه الدقيقة: يُزاد إن كان لها، ويُبدأ من واحد إن كان لدقيقةٍ من ساعةٍ مضت.
  insert into public.returning_checks as c (slot, minute, n)
  values (extract(minute from v_min)::smallint, v_min, 1)
  on conflict (slot) do update
     set n      = case when c.minute = excluded.minute then c.n + 1 else 1 end,
         minute = excluded.minute
  returning c.n into v_n;

  select coalesce(sum(n), 0)::integer into v_hour
    from public.returning_checks
   where minute > v_min - interval '1 hour';

  if v_n > 10 or v_hour > 60 then
    return false;
  end if;

  return exists (
    select 1 from public.client_history h
     where h.status = 'done'
       and right(regexp_replace(coalesce(h.phone, ''), '[^0-9]', '', 'g'), 9) = v_key);
end $fn$;
revoke all on function public.is_returning_client(text) from public;
grant execute on function public.is_returning_client(text) to anon, authenticated;
-- ⟪/core⟫
