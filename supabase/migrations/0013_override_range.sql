-- اليوم الاستثنائي صار نطاقًا.
--
-- الإجازة نادرًا ما تكون يومًا واحدًا: سفرٌ أسبوع، أو عيدٌ ثلاثة أيام. وكان
-- على زوجتك أن تُدخل كل يومٍ صفًّا مستقلًّا — عشرة صفوف لعشرة أيام، وأيُّ
-- يومٍ يُنسى ثغرةٌ تُحجَز فيها وهي مسافرة.
--
-- العمود الجديد end_date يجعل الصفَّ نطاقًا مغلقًا [the_date, end_date].
-- ويومٌ واحد نطاقٌ طرفاه سواء، فلا حالة خاصّة في الواجهة ولا في القاعدة،
-- والصفوف القديمة تبقى صحيحة: end_date فيها يساوي يومها.

alter table public.date_overrides
  add column if not exists end_date date;

update public.date_overrides set end_date = the_date where end_date is null;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'date_overrides_range_ck') then
    alter table public.date_overrides
      add constraint date_overrides_range_ck
      check (end_date is null or end_date >= the_date);
  end if;
end $$;

-- من أدخل صفًّا بلا نهاية قصدَ يومًا واحدًا؛ يُملأ الطرف عنه.
create or replace function public.overrides_default_end()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  new.end_date := coalesce(new.end_date, new.the_date);
  return new;
end;
$$;

drop trigger if exists overrides_default_end_trg on public.date_overrides;
create trigger overrides_default_end_trg
  before insert or update on public.date_overrides
  for each row execute function public.overrides_default_end();

-- الفهرس الفريد كان يمنع إجازتين تبدآن اليوم نفسه، ويبقى صحيحًا مع
-- النطاقات: تداخل نطاقين مغلقين لا يضرّ — اليوم مغلقٌ على الحالين.
create index if not exists date_overrides_range_idx
  on public.date_overrides (the_date, end_date);

-- نوافذ اليوم: يقع اليوم داخل النطاق، لا أن يساوي بدايته.
create or replace function public.day_windows(p_date date)
returns table (win_start time, win_end time)
language plpgsql stable
set search_path = public, pg_temp
as $$
begin
  if exists (select 1 from public.date_overrides o
              where p_date between o.the_date and coalesce(o.end_date, o.the_date)
                and o.kind = 'closed') then
    return;
  end if;

  if exists (select 1 from public.date_overrides o
              where p_date between o.the_date and coalesce(o.end_date, o.the_date)
                and o.kind = 'custom') then
    return query
      select o.start_time, o.end_time
      from public.date_overrides o
      where p_date between o.the_date and coalesce(o.end_date, o.the_date)
        and o.kind = 'custom'
      order by o.start_time;
    return;
  end if;

  return query
    select r.start_time, r.end_time
    from public.availability_rules r
    where r.active
      and r.weekday = extract(dow from p_date)::smallint
      and (r.valid_from is null or p_date >= r.valid_from)
      and (r.valid_to   is null or p_date <= r.valid_to)
    order by r.start_time;
end;
$$;
