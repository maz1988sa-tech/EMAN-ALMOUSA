-- الرسالة التي تُرسل بلا يد.
--
-- الرسائل موجودة أصلًا في «الرسائل»، تكتبها إيمان وترسلها بيدها من بطاقة
-- العميلة. وهذا الملفّ لا ينشئ رسائل جديدة، بل يعلّق على كلِّ رسالةٍ منها
-- سؤالًا واحدًا: متى تُرسَل وحدها؟ فالنصّ واحد في الحالتين — إن عدّلته
-- عدّلته في اليد والآلة معًا، ولا يبقى نصّان يتباعدان.
--
-- والطابور (message_outbox) هو الذاكرة: كلُّ رسالةٍ مجدولة سطرٌ فيه، له
-- موعدٌ وحالة. ومنه يُعرَف ما أُرسل وما فشل ولماذا — ولولاه لكان الإرسال
-- التلقائي صندوقًا مغلقًا لا يُراجَع.
--
-- ولا يُرسَل شيء قبل ربط حساب واتساب: تبقى الرسائل في الطابور بحالة
-- «معاينة»، فترى إيمان ما كان سيصل ومتى، قبل أن يصل أحدًا.

/* ═══ ١) الأتمتة تُعلَّق على الرسالة نفسها ════════════════════════════ */

alter table public.message_templates
  add column if not exists auto_enabled    boolean  not null default false,
  add column if not exists auto_trigger    text,
  add column if not exists auto_offset_min integer  not null default 0,
  add column if not exists auto_at_hour    smallint;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'tpl_auto_trigger_ck') then
    alter table public.message_templates add constraint tpl_auto_trigger_ck
      check (auto_trigger is null or auto_trigger in
             ('on_pending', 'on_confirmed', 'before_appt', 'after_done'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'tpl_auto_hour_ck') then
    alter table public.message_templates add constraint tpl_auto_hour_ck
      check (auto_at_hour is null or auto_at_hour between 0 and 23);
  end if;
  -- مفعّلةٌ بلا مُطلِق تعني رسالةً لا تُرسل أبدًا وتبدو مفعّلة: تُمنع.
  if not exists (select 1 from pg_constraint where conname = 'tpl_auto_needs_trigger_ck') then
    alter table public.message_templates add constraint tpl_auto_needs_trigger_ck
      check (not auto_enabled or auto_trigger is not null);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'tpl_auto_offset_ck') then
    alter table public.message_templates add constraint tpl_auto_offset_ck
      check (auto_offset_min between 0 and 43200);   -- شهرٌ سقفًا
  end if;
end $$;

/* ═══ ٢) الربط والحدود في الإعدادات ═══════════════════════════════════ */

alter table public.settings
  add column if not exists wa_auto_enabled boolean  not null default false,
  add column if not exists wa_phone_id     text,
  add column if not exists wa_quiet_from   smallint not null default 22,
  add column if not exists wa_quiet_to     smallint not null default 9;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'settings_quiet_ck') then
    alter table public.settings add constraint settings_quiet_ck
      check (wa_quiet_from between 0 and 23 and wa_quiet_to between 0 and 23);
  end if;
end $$;

/* ═══ ٣) الطابور ══════════════════════════════════════════════════════ */

create table if not exists public.message_outbox (
  id          uuid primary key default gen_random_uuid(),
  booking_id  uuid not null references public.bookings(id)          on delete cascade,
  template_id uuid          references public.message_templates(id) on delete cascade,
  trigger_kind text not null,
  to_phone    text not null,
  due_at      timestamptz not null,
  status      text not null default 'queued',
  body        text,
  attempts    integer not null default 0,
  error       text,
  sent_at     timestamptz,
  provider_id text,
  created_at  timestamptz not null default now(),
  -- رسالةٌ واحدة من كلِّ نوعٍ لكلِّ حجز: التكرار على العميلة أسوأ من الصمت.
  unique (booking_id, template_id)
);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'outbox_status_ck') then
    alter table public.message_outbox add constraint outbox_status_ck
      check (status in ('queued', 'sent', 'failed', 'cancelled', 'preview'));
  end if;
end $$;

create index if not exists message_outbox_due_idx
  on public.message_outbox (due_at) where status = 'queued';
create index if not exists message_outbox_booking_idx
  on public.message_outbox (booking_id);

alter table public.message_outbox enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies
                 where schemaname = 'public' and tablename = 'message_outbox'
                   and policyname = 'outbox admin all') then
    create policy "outbox admin all" on public.message_outbox
      for all to authenticated using (public.is_admin()) with check (public.is_admin());
  end if;
end $$;

/* ═══ ٤) صياغة النصّ — مصدرٌ واحد للحقيقة ═════════════════════════════
   المعاينة في اللوحة والرسالة التي تصل العميلة تخرجان من هنا معًا. ولو
   كُتبت الصياغة مرّتين لتباعدتا، فترى إيمان نصًّا وتقرأ العميلة غيره. */

create or replace function public.fmt_money(v numeric)
returns text language sql immutable as $$
  select to_char(round(coalesce(v, 0)), 'FM999,999,999') || ' ر.س';
$$;

create or replace function public.fmt_ar_date(d date)
returns text language sql immutable as $$
  select (array['الأحد','الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت'])
           [extract(dow from d)::int + 1]
      || ' ' || extract(day from d)::int
      || ' ' || (array['يناير','فبراير','مارس','أبريل','مايو','يونيو',
                       'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'])
                  [extract(month from d)::int]
      || ' ' || extract(year from d)::int;
$$;

create or replace function public.fmt_ar_time(t time)
returns text language sql immutable as $$
  select (case when extract(hour from t)::int % 12 = 0 then 12
               else extract(hour from t)::int % 12 end)::text
      || ':' || lpad(extract(minute from t)::int::text, 2, '0')
      || ' ' || (case when extract(hour from t)::int < 12 then 'ص' else 'م' end);
$$;

drop function if exists public.render_template(text, uuid);
create function public.render_template(p_body text, p_booking uuid)
returns text
language plpgsql stable security definer set search_path to 'public', 'pg_temp'
as $fn$
declare
  b       record;
  s       record;
  v_svc   text;
  v_link  text;
  v_out   text := coalesce(p_body, '');
begin
  -- المفتاح: المدير، أو نداءٌ من داخل الخادم بلا جلسة (الجدولة الدورية).
  if auth.uid() is not null and not public.is_admin() then
    raise exception 'not authorised';
  end if;
  select * into b from public.bookings where id = p_booking;
  if not found then return v_out; end if;
  select * into s from public.settings where id = 1;

  select string_agg(i.service_name, ' + ' order by i.sort, i.service_name)
    into v_svc from public.booking_items i where i.booking_id = b.id;

  v_link := 'https://eman-aalmousa.com/?t=' || b.public_token::text;

  -- الحقل المجهول يبقى كما هو لا يُمحى: خطأ الكتابة يجب أن يُرى.
  v_out := replace(v_out, '{الاسم}',         coalesce(b.client_name, ''));
  v_out := replace(v_out, '{التاريخ}',       public.fmt_ar_date(b.the_date));
  v_out := replace(v_out, '{الوقت}',         public.fmt_ar_time(b.start_time));
  v_out := replace(v_out, '{الخدمة}',        coalesce(v_svc, ''));
  v_out := replace(v_out, '{الإجمالي}',      public.fmt_money(b.price));
  v_out := replace(v_out, '{العربون}',       public.fmt_money(b.deposit));
  v_out := replace(v_out, '{المتبقي}',       public.fmt_money(greatest(coalesce(b.price,0) - coalesce(b.deposit,0), 0)));
  v_out := replace(v_out, '{الموقع}',        coalesce(b.loc_text, ''));
  v_out := replace(v_out, '{رابط الحجز}',    v_link);
  v_out := replace(v_out, '{الاسم التجاري}', coalesce(s.business_name, ''));
  return v_out;
end $fn$;

revoke all on function public.render_template(text, uuid) from public;
grant execute on function public.render_template(text, uuid) to authenticated;

/* ═══ ٥) الجدولة ══════════════════════════════════════════════════════
   تُستدعى عند كلِّ تغيّرٍ في حالة الحجز. تحسب لكلِّ رسالةٍ مفعّلة موعدَها،
   وتضعها في الطابور مرّةً واحدة. ولا تجدول ماضيًا: تذكيرٌ بموعدٍ فات
   ليس تذكيرًا بل إزعاج. */

create or replace function public.schedule_auto_messages(p_booking uuid)
returns integer
language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
declare
  b        record;
  s        record;
  t        record;
  tz       text;
  v_base   timestamptz;
  v_due    timestamptz;
  v_local  timestamp;
  v_hour   int;
  v_n      integer := 0;
begin
  select * into b from public.bookings where id = p_booking;
  if not found then return 0; end if;
  select * into s from public.settings where id = 1;
  tz := coalesce(s.timezone, 'Asia/Riyadh');

  -- حجزٌ انتهى بلا خدمة: يُسحب ما لم يُرسل بعد. الرسالة التي فقدت سببها
  -- لا تُترك في الطابور تنتظر ساعتها.
  if b.status in ('cancelled', 'rejected', 'no_show') then
    update public.message_outbox
       set status = 'cancelled', error = 'أُلغي الحجز'
     where booking_id = b.id and status = 'queued';
    return 0;
  end if;

  for t in
    select * from public.message_templates
     where auto_enabled and active is distinct from false and auto_trigger is not null
     order by sort, title
  loop
    -- هل يخصّ هذا المُطلِق حالةَ الحجز الآن؟
    continue when (t.auto_trigger = 'on_pending'   and b.status <> 'pending')
              or  (t.auto_trigger = 'on_confirmed' and b.status <> 'confirmed')
              or  (t.auto_trigger = 'before_appt'  and b.status <> 'confirmed')
              or  (t.auto_trigger = 'after_done'   and b.status <> 'done');

    v_base := case t.auto_trigger
                when 'before_appt' then (b.the_date + b.start_time) at time zone tz
                when 'after_done'  then coalesce(b.completed_at, now())
                else now()
              end;

    v_due := case t.auto_trigger
               when 'before_appt' then v_base - make_interval(mins => t.auto_offset_min)
               when 'after_done'  then v_base + make_interval(mins => t.auto_offset_min)
               else v_base
             end;

    -- تثبيت الساعة: «قبل الموعد بيوم» وحدها تعني الثالثة فجرًا أحيانًا.
    -- فإن اختارت إيمان ساعة، أُخذ اليومُ من الحساب والساعةُ من اختيارها.
    if t.auto_at_hour is not null and t.auto_trigger in ('before_appt', 'after_done') then
      v_local := (v_due at time zone tz);
      v_due   := (date_trunc('day', v_local) + make_interval(hours => t.auto_at_hour)) at time zone tz;
    end if;

    -- ساعات الهدوء: لا رسالة تُوقظ أحدًا. تُؤجَّل إلى أوّل ساعةٍ مسموحة.
    if t.auto_trigger in ('before_appt', 'after_done') then
      v_local := (v_due at time zone tz);
      v_hour  := extract(hour from v_local)::int;
      if (s.wa_quiet_from < s.wa_quiet_to  and v_hour >= s.wa_quiet_from and v_hour < s.wa_quiet_to)
      or (s.wa_quiet_from >= s.wa_quiet_to and (v_hour >= s.wa_quiet_from or v_hour < s.wa_quiet_to)) then
        v_local := date_trunc('day', v_local) + make_interval(hours => s.wa_quiet_to)
                 + (case when v_hour >= s.wa_quiet_from and s.wa_quiet_from >= s.wa_quiet_to
                         then interval '1 day' else interval '0' end);
        v_due := v_local at time zone tz;
      end if;
    end if;

    -- موعدٌ فات بأكثر من ساعتين لا يُجدول: مضى وقتُه ومعناه.
    continue when t.auto_trigger in ('before_appt', 'after_done')
              and v_due < now() - interval '2 hours';

    insert into public.message_outbox (booking_id, template_id, trigger_kind, to_phone, due_at)
    values (b.id, t.id, t.auto_trigger, b.client_phone, greatest(v_due, now()))
    on conflict (booking_id, template_id) do nothing;

    if found then v_n := v_n + 1; end if;
  end loop;

  return v_n;
end $fn$;

create or replace function public.tg_schedule_auto_messages()
returns trigger
language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
begin
  perform public.schedule_auto_messages(new.id);
  return null;
exception when others then
  -- خللٌ في الجدولة يجب ألّا يمنع عميلةً من الحجز: يُبتلع هنا ويُسجَّل،
  -- ولا يصعد فيُسقط المعاملة كلَّها.
  raise warning 'schedule_auto_messages failed for %: %', new.id, sqlerrm;
  return null;
end $fn$;

drop trigger if exists bookings_auto_msg on public.bookings;
create trigger bookings_auto_msg
  after insert or update of status on public.bookings
  for each row execute function public.tg_schedule_auto_messages();

/* ═══ ٦) الإرسال ══════════════════════════════════════════════════════
   قبل ربط حساب واتساب لا يُرسل شيء: تُختم الرسالة «معاينة» ويُحفظ نصّها
   كما كان سيصل. فترى إيمان الأثر كاملًا قبل أن يخرج إلى أحد. */

create or replace function public.dispatch_due_messages(p_limit integer default 50)
returns TABLE (out_id uuid, out_status text)
language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
declare
  s      record;
  m      record;
  v_live boolean;
begin
  select * into s from public.settings where id = 1;
  v_live := coalesce(s.wa_auto_enabled, false) and coalesce(s.wa_phone_id, '') <> '';

  for m in
    select o.*, t.body as tpl_body
      from public.message_outbox o
      left join public.message_templates t on t.id = o.template_id
     where o.status = 'queued' and o.due_at <= now()
     order by o.due_at
     limit greatest(p_limit, 1)
     for update of o skip locked
  loop
    -- النصّ يُصاغ الآن لا وقت الجدولة: فلو عدّلت إيمان الرسالة بعد أن
    -- جُدولت، وصل التعديلُ إلى العميلة لا النصُّ القديم.
    update public.message_outbox o
       set body     = public.render_template(m.tpl_body, m.booking_id),
           attempts = o.attempts + 1,
           status   = case when v_live then 'failed' else 'preview' end,
           error    = case when v_live
                           then 'رُبط الحساب لكن قناة الإرسال لم تُفعَّل بعد'
                           else 'وضع المعاينة — لم يُربط حساب واتساب بعد' end
     where o.id = m.id;

    out_id := m.id;
    out_status := case when v_live then 'failed' else 'preview' end;
    return next;
  end loop;
end $fn$;

revoke all on function public.dispatch_due_messages(integer) from public;

/* كل خمس دقائق. الجدولة داخل القاعدة لا خارجها: لا خادمَ إضافيًّا يُشغَّل
   ولا مفتاحَ يُخزَّن في مكانٍ ثانٍ. */
do $$
begin
  perform cron.unschedule('dispatch-auto-messages');
exception when others then null;
end $$;

select cron.schedule('dispatch-auto-messages', '*/5 * * * *',
                     $$select public.dispatch_due_messages(50);$$);

/* ═══ ٧) ما تراه اللوحة ═══════════════════════════════════════════════ */

drop function if exists public.admin_outbox(integer);
create function public.admin_outbox(p_limit integer default 100)
returns TABLE (
  id uuid, booking_id uuid, ref text, client_name text, to_phone text,
  title text, trigger_kind text, due_at timestamptz, status text,
  body text, error text, sent_at timestamptz
)
language sql stable security definer set search_path to 'public', 'pg_temp'
as $$
  select o.id, o.booking_id, b.ref, b.client_name, o.to_phone,
         coalesce(t.title, '—'), o.trigger_kind, o.due_at, o.status,
         o.body, o.error, o.sent_at
    from public.message_outbox o
    join public.bookings b on b.id = o.booking_id
    left join public.message_templates t on t.id = o.template_id
   where public.is_admin()
   order by o.due_at desc
   limit greatest(coalesce(p_limit, 100), 1);
$$;
revoke all on function public.admin_outbox(integer) from public;
grant execute on function public.admin_outbox(integer) to authenticated;

/* إعادة الجدولة لكلّ الحجوزات القائمة — تُستدعى بعد تغيير قاعدةٍ تلقائية،
   وإلّا سرت القاعدة على الحجوزات القادمة وحدها. */
drop function if exists public.admin_reschedule_auto();
create function public.admin_reschedule_auto()
returns integer
language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
declare r record; n integer := 0;
begin
  if not public.is_admin() then raise exception 'not authorised'; end if;
  -- ما لم يُرسل بعد يُمسح ثمّ يُعاد بناؤه: وإلّا احتفظ الطابور بتوقيتٍ
  -- قديمٍ بعد تغيير القاعدة، فبدا التعديل نافذًا وهو غير نافذ.
  delete from public.message_outbox where status in ('queued', 'preview');
  for r in select id from public.bookings
            where status in ('pending', 'confirmed', 'done')
              and the_date >= current_date - 30
  loop
    n := n + public.schedule_auto_messages(r.id);
  end loop;
  return n;
end $fn$;
revoke all on function public.admin_reschedule_auto() from public;
grant execute on function public.admin_reschedule_auto() to authenticated;

/* ═══ ٨) الإعدادات العامّة للعميلة لا تحمل شيئًا من هذا ══════════════
   حدود الإرسال وربط واتساب شأنُ اللوحة وحدها، فلا تُنشر في الدالة
   العامّة التي تقرأها صفحة العميلة. */
