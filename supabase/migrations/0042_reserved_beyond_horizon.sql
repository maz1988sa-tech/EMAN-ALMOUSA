-- ٠٠٤٢ الفترةُ المخصّصة لخدمة تسبق أقصى مدى الحجز (§٧ع في CLAUDE.md).
--
-- طلب صاحب المشروع (١٩ نوفمبر ٢٠٢٦): أقصى المدى (٩٠ يومًا مثلًا) يقفل ما بعده تلقائيًّا، فشهرٌ
-- خصّصته إيمان للعرائس بعد ١٠٠ يوم لا يظهر لأحد — ولا للعروس. والفترةُ المخصّصة فعلٌ صريح
-- باليوم كـ«عمل خاص» (٠٠٣٨)، والأخصّ يسبق: المدى حكمٌ بالعدد، والفترة حكمٌ باليوم.
--
-- - **تُفتح لمن في سلّتها خدمةٌ من المخصّصة وحدها.** وغيرها يرى الشهر البعيد كما كان: «غير
--   مفتوح» أو «غير متاح» بكلمة إيمان (`closed_month_word`) — اختيار صاحب المشروع. فلا يُعلَّم
--   «مخصّصًا» بعد المدى (`days_with_availability` تقيس الأساس بلا خدمات، وهو مقفلٌ هناك).
-- - **يُرفع حدُّ الأيام وحده.** أوقات العمل وأيام الراحة والإجازات والحجوزات القائمة ومهلةُ الحجز
--   تبقى كما هي (`day_windows` و`busy_intervals` لا تُمسّ).
-- - **المفعّلة وحدها**، وفترةٌ لم تبقَ فيها خدمةٌ موجودة لا تفتح شيئًا — كما في `reserved_block`.
-- - **أربعة مواضع**، وكلُّها تسأل `reserved_open` فيبقى الحكم في موضعٍ واحد:
--   `available_slots` (ومنها `days_with_availability`)، و`create_booking`، و`open_days_ahead`
--   التي تُخبر الصفحة بأيام ما بعد المدى المفتوحة **لهذه السلّة** فلا يُشطب شهرُها.
-- - **متوافقٌ مع الصفحات القديمة:** بلا خدماتٍ (null) تعمل الثلاث كما كانت. و`create_booking` لا
--   تسأل عن الموعد بخدمات السلّة إلّا لمن قال إنّه يعرف الفترات (`p_features` بتّ ١، §٧ع) — ومن لا
--   يعرفها يُسأل كما كان، فلا يتغيّر عليه شيء.

-- الأداة نفسها في ٠٠٤١: الموضع يُطلب مرّةً واحدة بالضبط، وإلّا توقّف الترحيل كلُّه.
create or replace function pg_temp.patch_once(p_src text, p_anchor text, p_repl text, p_what text)
returns text language plpgsql as $$
declare v_n int;
begin
  v_n := (length(p_src) - length(replace(p_src, p_anchor, ''))) / greatest(length(p_anchor), 1);
  if v_n <> 1 then
    raise exception 'لم يُعثر على «%» مرّةً واحدة بالضبط (وُجد %)', p_what, v_n;
  end if;
  return replace(p_src, p_anchor, p_repl);
end $$;

-- هل يفتح هذا اليومَ لهذه السلّة فترةٌ مخصّصة؟ مفعّلةٌ فيها اليوم، وفيها خدمةٌ موجودة، وتشترك مع
-- السلّة في خدمة. والسلّة الغائبة (null) لا تفتح شيئًا: من لا يذكر خدماته لا يُفتح له ما بعد المدى.
create or replace function public.reserved_open(p_date date, p_service_ids uuid[])
returns boolean language sql stable
set search_path to 'public', 'pg_temp'
as $$
  select p_service_ids is not null and exists (
    select 1 from public.reserved_periods r
     where r.active
       and p_date = any(r.dates)
       and exists (select 1 from public.services s where s.id = any(r.service_ids))
       and exists (select 1 from unnest(p_service_ids) c where c = any(r.service_ids)));
$$;
revoke execute on function public.reserved_open(date, uuid[]) from public, anon, authenticated;

-- ١) available_slots: ما بعد المدى يُفتح لـ«عمل خاص» (٠٠٣٨) أو لفترةٍ مخصّصة تضمّ خدمةً من السلّة.
do $do$
declare v_src text; v_new text;
begin
  v_src := pg_get_functiondef('public.available_slots(date, integer, uuid, uuid[])'::regprocedure);
  if position('reserved_open' in v_src) > 0 then return; end if;   -- طُبّق من قبل
  v_new := pg_temp.patch_once(v_src,
    $a$  if p_date > v_today + v_advance and not public.custom_day(p_date) then return; end if;
$a$,
    $b$  -- وفترةٌ مخصّصة لخدمة تفتح أيامها بعد المدى لمن في سلّتها خدمتُها (٠٠٤٢): فعلٌ باليوم كـ«عمل خاص».
  if p_date > v_today + v_advance and not public.custom_day(p_date)
     and not public.reserved_open(p_date, p_service_ids) then return; end if;
$b$,
    'شرط المدى في available_slots');
  execute v_new;
end $do$;

-- ٢) create_booking: يُسأل عن الموعد بخدمات السلّة لمن يعرف الفترات، فيُقبل حجز العروس في شهرها البعيد.
-- والسلّة التي لا تضمّ الخدمة ردّها الحارسُ قبل هذا برسالة إيمان (٠٠٤١)، فلا يصل إليها هذا السؤال.
do $do$
declare v_src text; v_new text; v_sig regprocedure;
begin
  v_sig := 'public.create_booking(text, text, date, time without time zone, uuid[], text[], text, text, text, text, numeric, numeric, integer, integer)'::regprocedure;
  v_src := pg_get_functiondef(v_sig);
  if position('(coalesce(p_features, 0) & 1) = 1 then p_service_ids end' in v_src) > 0 then return; end if;
  v_new := pg_temp.patch_once(v_src,
    $a$  if not exists (select 1 from public.available_slots(p_date, v_dur) s where s.slot = p_time) then
$a$,
    $b$  -- لمن يعرف الفترات (بتّ ١) يُسأل عن الموعد بخدمات السلّة: الفترةُ المخصّصة تفتح ما بعد المدى
  -- لمن في سلّتها خدمتُها (٠٠٤٢). ومن لا يعرفها يُسأل كما كان، فلا يتغيّر عليه شيء.
  if not exists (select 1 from public.available_slots(p_date, v_dur, null,
                   case when (coalesce(p_features, 0) & 1) = 1 then p_service_ids end) s
                  where s.slot = p_time) then
$b$,
    'سؤال الموعد في create_booking');
  execute v_new;
end $do$;

-- ٣) open_days_ahead: أيامُ ما بعد المدى المفتوحة — «عمل خاص» للجميع كما كانت، ومعها أيامُ الفترات
-- المخصّصة التي تفتحها **هذه السلّة**. تقرؤها الصفحة كلّما تغيّرت خدمات السلّة، فلا يُشطب شهرُ العروس
-- عندها، ويبقى عند غيرها «غير مفتوح» كما كان. والتوقيع القديم بلا وسائط يبقى صالحًا بالقيمة الافتراضيّة.
drop function if exists public.open_days_ahead();
create or replace function public.open_days_ahead(p_service_ids uuid[] default null)
returns table(the_date date)
language sql stable security definer
set search_path to 'public', 'pg_temp'
as $$
  with edge as (
    select public.local_today()
           + (select coalesce(max_advance_days, 0) from public.settings where id = 1) as d
  )
  select x.d
    from (
      select gs::date as d
        from public.date_overrides o
        cross join lateral generate_series(o.the_date::timestamp,
                                           coalesce(o.end_date, o.the_date)::timestamp,
                                           interval '1 day') as gs
       where o.kind = 'custom'
      union
      select u.d
        from public.reserved_periods r
        cross join lateral unnest(r.dates) as u(d)
       where public.reserved_open(u.d, p_service_ids)
    ) x, edge
   where x.d > edge.d
   order by 1;
$$;
revoke execute on function public.open_days_ahead(uuid[]) from public;
grant execute on function public.open_days_ahead(uuid[]) to anon, authenticated, service_role;
