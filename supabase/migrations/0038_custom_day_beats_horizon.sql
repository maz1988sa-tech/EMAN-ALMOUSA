-- ٠٠٣٨ — «عمل خاص» يسبق مدى الحجز.
--
-- فترةُ «عمل خاص» فعلٌ صريح من صاحبة العمل: «في هذا اليوم أعمل، وهذه
-- ساعاتي». وكانت تُقدَّم على الإجازة (`day_windows`) ولا تُقدَّم على
-- **أقصى مدى للحجز**: يومان في يناير خارج المدى يُضبطان في اللوحة ولا
-- يظهران للعميلة قطّ — فالشهر مشطوب، واليوم يُردّ من `available_slots`
-- قبل أن يُسأل عن ساعاته.
--
-- والحال الواقعة: الشهور القادمة مغلقة كلُّها، ويومان بعينهما تريد أن
-- تعمل فيهما. فالمدى حكمٌ عامّ، والفترةُ الخاصّة استثناءٌ منه بالاسم —
-- وما ضُبط باليوم يسبق ما ضُبط بالعدد.
--
-- ثلاثة مواضع: `available_slots` تقبل اليوم الخاصّ خارج المدى (ومنها
-- `days_with_availability` و`create_booking` فلا يتباعدان)، و`open_days_ahead`
-- تُخبر الصفحة بالأيام الخاصّة خارج المدى لتُظهر شهرَها في اللوح بدل
-- شطبه، والماضي يبقى ماضيًا.

create or replace function public.custom_day(p_date date)
returns boolean language sql stable
set search_path to 'public', 'pg_temp'
as $$
  select exists (
    select 1 from public.date_overrides o
     where o.kind = 'custom'
       and p_date between o.the_date and coalesce(o.end_date, o.the_date));
$$;
revoke execute on function public.custom_day(date) from public, anon;

do $do$
declare v_src text; v_new text;
begin
  select pg_get_functiondef(p.oid) into v_src
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'available_slots';
  if v_src is null then raise exception 'available_slots غير موجودة'; end if;
  v_new := replace(v_src,
    E'  if p_date < v_today or p_date > v_today + v_advance then\n    return;\n  end if;',
    E'  -- الماضي لا يُفتح. وما بعد المدى يُفتح إن ضُبط يومُه «عمل خاص» باسمه:\n'
     '  -- المدى حكمٌ بالعدد، والفترةُ الخاصّة حكمٌ باليوم، والأخصّ يسبق.\n'
     '  if p_date < v_today then return; end if;\n'
     '  if p_date > v_today + v_advance and not public.custom_day(p_date) then return; end if;');
  if v_new = v_src then raise exception 'لم يُعثر على شرط المدى في available_slots'; end if;
  execute v_new;
end $do$;

-- الأيام الخاصّة خارج المدى: تقرؤها الصفحة مرّةً مع الإعدادات، فتُبقي
-- شهرَها قابلًا للاختيار في اللوح ويصل السهم إليه. وما داخل المدى لا
-- يُذكر — هو ظاهرٌ أصلًا.
create or replace function public.open_days_ahead()
returns table(the_date date)
language sql stable security definer
set search_path to 'public', 'pg_temp'
as $$
  select distinct d::date
    from public.date_overrides o
    cross join lateral generate_series(o.the_date::timestamp,
                                       coalesce(o.end_date, o.the_date)::timestamp,
                                       interval '1 day') as d
   where o.kind = 'custom'
     and d::date > public.local_today()
                   + (select coalesce(max_advance_days, 0) from public.settings where id = 1)
   order by 1;
$$;
revoke execute on function public.open_days_ahead() from public;
grant execute on function public.open_days_ahead() to anon, authenticated, service_role;
