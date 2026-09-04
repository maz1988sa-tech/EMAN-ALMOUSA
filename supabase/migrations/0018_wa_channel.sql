-- قناة الإرسال: من الطابور إلى واتساب.
--
-- الجدولة كانت تنتهي عند الطابور ثم تقف. هذا ما يكملها: كلُّ رسالةٍ حلّ
-- موعدُها تُصاغ وتُرسل إلى Graph API، ويُقرأ جوابُ ميتا فيُكتب في سطرها.
--
-- والنداء من داخل القاعدة بـ pg_net لا من خادمٍ ثانٍ: أقلُّ قطعةٍ متحرّكة
-- أقلُّ عطبًا، والمفتاح يبقى في خزنة Supabase وحدها — لا في المستودع ولا
-- في جدولٍ يُقرأ بـ select.
--
-- ورسائل الأعمال عند ميتا لا تُرسل نصًّا حرًّا: تُعتمد قوالبُها مسبقًا،
-- ومتغيّراتها مرقّمة {{1}} {{2}}. وأسماء إيمان — {الاسم} و{التاريخ} —
-- تُترجم إليها هنا بترتيب ظهورها، فيُولَّد نصُّ القالب كما يُقدَّم لميتا
-- بلا أن تكتبه بيدها فتخطئ ترتيبًا.

/* ═══ ١) القالب المعتمد عند ميتا ═══════════════════════════════════════ */

alter table public.message_templates
  add column if not exists wa_template_name text,
  add column if not exists wa_template_lang text not null default 'ar',
  add column if not exists wa_template_ok   boolean not null default false;

alter table public.settings
  add column if not exists wa_test_phone text;

/* ═══ ٢) الطابور يحمل أثر النداء ═══════════════════════════════════════ */

alter table public.message_outbox
  add column if not exists request_id bigint,
  alter column booking_id drop not null;

do $$
begin
  alter table public.message_outbox drop constraint if exists outbox_status_ck;
  alter table public.message_outbox add constraint outbox_status_ck
    check (status in ('queued', 'sending', 'sent', 'failed', 'cancelled', 'preview'));
end $$;

create index if not exists message_outbox_sending_idx
  on public.message_outbox (request_id) where status = 'sending';

/* ═══ ٣) المفتاح من الخزنة وحدها ═══════════════════════════════════════ */

create or replace function public.wa_token()
returns text language sql stable security definer set search_path to 'vault', 'public', 'pg_temp'
as $$
  select decrypted_secret from vault.decrypted_secrets where name = 'WA_TOKEN' limit 1;
$$;
revoke all on function public.wa_token() from public, anon, authenticated;

/* ═══ ٤) من أسماء إيمان إلى أرقام ميتا ═════════════════════════════════ */

create or replace function public.wa_vars(p_body text)
returns text[] language plpgsql immutable as $fn$
declare m text; acc text[] := '{}';
begin
  for m in select (regexp_matches(coalesce(p_body, ''), '\{[^}]{1,24}\}', 'g'))[1]
  loop
    if not (m = any(acc)) then acc := acc || m; end if;
  end loop;
  return acc;
end $fn$;

/** نصّ القالب كما يُقدَّم لميتا: {الاسم} تصير {{1}} بترتيب ظهورها. */
create or replace function public.wa_template_text(p_body text)
returns text language plpgsql immutable as $fn$
declare vs text[]; i int; acc text := coalesce(p_body, '');
begin
  vs := public.wa_vars(p_body);
  for i in 1 .. coalesce(array_length(vs, 1), 0) loop
    acc := replace(acc, vs[i], '{{' || i || '}}');
  end loop;
  return acc;
end $fn$;
grant execute on function public.wa_template_text(text) to authenticated;
grant execute on function public.wa_vars(text) to authenticated;

/** قيم المتغيّرات لحجزٍ بعينه، بنفس ترتيب القالب. */
create or replace function public.wa_params(p_body text, p_booking uuid)
returns text[] language plpgsql stable security definer set search_path to 'public', 'pg_temp'
as $fn$
declare vs text[]; i int; acc text[] := '{}'; v text;
begin
  vs := public.wa_vars(p_body);
  for i in 1 .. coalesce(array_length(vs, 1), 0) loop
    -- ميتا ترفض المتغيّر إن حمل سطرًا جديدًا أو فراغات متتالية.
    v := regexp_replace(coalesce(public.render_template(vs[i], p_booking), ''),
                        '[\r\n\t]+|\s{4,}', ' ', 'g');
    acc := acc || v;
  end loop;
  return acc;
end $fn$;

/* ═══ ٥) النداء ════════════════════════════════════════════════════════
   قالبٌ معتمد لرسالةٍ تبدأها إيمان، ونصٌّ حرّ للتجربة وحدها — ولا يقبله
   واتساب إلّا داخل أربعٍ وعشرين ساعة من آخر رسالةٍ أرسلتها العميلة. */

create or replace function public.wa_send(
  p_to text, p_text text default null,
  p_template text default null, p_lang text default 'ar', p_params text[] default '{}'
) returns bigint
language plpgsql security definer set search_path to 'public', 'extensions', 'pg_temp'
as $fn$
declare
  s        record;
  v_token  text;
  v_to     text;
  v_body   jsonb;
begin
  select * into s from public.settings where id = 1;
  v_token := public.wa_token();
  if coalesce(s.wa_phone_id, '') = '' then raise exception 'wa_phone_id غير مضبوط'; end if;
  if coalesce(v_token, '') = ''        then raise exception 'WA_TOKEN غير موجود في الخزنة'; end if;

  v_to := regexp_replace(coalesce(p_to, ''), '\D', '', 'g');
  if length(v_to) < 8 then raise exception 'رقم غير صالح: %', p_to; end if;

  if p_template is not null then
    v_body := jsonb_build_object(
      'messaging_product', 'whatsapp', 'recipient_type', 'individual',
      'to', v_to, 'type', 'template',
      'template', jsonb_build_object(
        'name', p_template,
        'language', jsonb_build_object('code', coalesce(p_lang, 'ar')),
        'components', case when coalesce(array_length(p_params, 1), 0) = 0 then '[]'::jsonb
          else jsonb_build_array(jsonb_build_object(
                 'type', 'body',
                 'parameters', (select jsonb_agg(jsonb_build_object('type', 'text', 'text', x))
                                  from unnest(p_params) as x)))
          end));
  else
    v_body := jsonb_build_object(
      'messaging_product', 'whatsapp', 'recipient_type', 'individual',
      'to', v_to, 'type', 'text',
      'text', jsonb_build_object('preview_url', true, 'body', coalesce(p_text, '')));
  end if;

  return net.http_post(
    url     := 'https://graph.facebook.com/v25.0/' || s.wa_phone_id || '/messages',
    headers := jsonb_build_object('Authorization', 'Bearer ' || v_token,
                                  'Content-Type', 'application/json'),
    body    := v_body,
    timeout_milliseconds := 15000);
end $fn$;
revoke all on function public.wa_send(text, text, text, text, text[]) from public, anon, authenticated;

/* ═══ ٦) الإرسال ═══════════════════════════════════════════════════════ */

create or replace function public.dispatch_due_messages(p_limit integer default 50)
returns TABLE (out_id uuid, out_status text)
language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
declare
  s      record;
  m      record;
  v_live boolean;
  v_body text;
  v_req  bigint;
  v_new  text;
  v_err  text;
begin
  select * into s from public.settings where id = 1;
  v_live := coalesce(s.wa_auto_enabled, false)
        and coalesce(s.wa_phone_id, '') <> ''
        and coalesce(public.wa_token(), '') <> '';

  for m in
    select o.*, t.body as tpl_body, t.wa_template_name, t.wa_template_lang, t.wa_template_ok
      from public.message_outbox o
      left join public.message_templates t on t.id = o.template_id
     where o.status = 'queued' and o.due_at <= now()
     order by o.due_at
     limit greatest(p_limit, 1)
     for update of o skip locked
  loop
    -- النصّ يُصاغ الآن لا وقت الجدولة: فلو عدّلت إيمان الرسالة بعد أن
    -- جُدولت، وصل التعديلُ إلى العميلة لا النصُّ القديم.
    v_body := public.render_template(m.tpl_body, m.booking_id);
    v_req  := null; v_err := null;

    if not v_live then
      v_new := 'preview';
      v_err := 'وضع المعاينة — لم يُربط حساب واتساب بعد';
    elsif coalesce(m.wa_template_name, '') = '' or not m.wa_template_ok then
      -- قالبٌ غير معتمد يرفضه واتساب، فلا يُرمى النداء عبثًا: يُقال السبب.
      v_new := 'failed';
      v_err := 'لم يُعتمد قالب هذه الرسالة عند ميتا بعد';
    else
      begin
        v_req := public.wa_send(
          p_to       => m.to_phone,
          p_template => m.wa_template_name,
          p_lang     => coalesce(m.wa_template_lang, 'ar'),
          p_params   => public.wa_params(m.tpl_body, m.booking_id));
        v_new := 'sending';
      exception when others then
        v_new := 'failed'; v_err := sqlerrm;
      end;
    end if;

    update public.message_outbox o
       set body = v_body, attempts = o.attempts + 1,
           status = v_new, error = v_err, request_id = v_req
     where o.id = m.id;

    out_id := m.id; out_status := v_new;
    return next;
  end loop;
end $fn$;
revoke all on function public.dispatch_due_messages(integer) from public, anon, authenticated;

/* ═══ ٧) قراءة جواب ميتا ═══════════════════════════════════════════════
   pg_net لا ينتظر الجواب، فيُقرأ في الدورة التالية. وجوابُ ميتا يُكتب
   كما هو حين يفشل: «رقم غير مسجَّل» يعالَج، و«فشل» وحدها لا تعالَج. */

create or replace function public.reconcile_sent_messages()
returns integer
language plpgsql security definer set search_path to 'public', 'net', 'extensions', 'pg_temp'
as $fn$
declare m record; r record; n integer := 0;
begin
  for m in select * from public.message_outbox
            where status = 'sending' and request_id is not null
  loop
    select * into r from net._http_response where id = m.request_id;
    if not found then
      -- ما زال في الطريق، أو مُسح سجلُّه بعد طول انتظار.
      if m.created_at < now() - interval '2 hours' then
        update public.message_outbox
           set status = 'failed', error = 'انقطع الجواب ولم يُعرف مصيرها'
         where id = m.id;
        n := n + 1;
      end if;
      continue;
    end if;

    if r.status_code between 200 and 299 then
      update public.message_outbox
         set status = 'sent', sent_at = now(), error = null,
             provider_id = (r.content::jsonb -> 'messages' -> 0 ->> 'id')
       where id = m.id;
    else
      update public.message_outbox
         set status = 'failed',
             error = coalesce(
               nullif(r.content::jsonb -> 'error' ->> 'message', ''),
               nullif(r.error_msg, ''),
               'رفضت ميتا الإرسال (' || coalesce(r.status_code::text, '?') || ')')
       where id = m.id;
    end if;
    n := n + 1;
  end loop;
  return n;
end $fn$;
revoke all on function public.reconcile_sent_messages() from public, anon, authenticated;

/* ═══ ٨) الدورة ════════════════════════════════════════════════════════ */

create or replace function public.tick_messages()
returns void language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
begin
  perform public.reconcile_sent_messages();
  perform public.dispatch_due_messages(50);
end $fn$;
revoke all on function public.tick_messages() from public, anon, authenticated;

do $$
begin perform cron.unschedule('dispatch-auto-messages'); exception when others then null; end $$;
do $$
begin perform cron.unschedule('tick-messages'); exception when others then null; end $$;

select cron.schedule('tick-messages', '*/5 * * * *', $$select public.tick_messages();$$);

/* ═══ ٩) ما تضغطه إيمان ════════════════════════════════════════════════ */

/** رسالة تجربة إلى رقمٍ تكتبه هي. نصٌّ حرّ لا قالب — فيلزم أن تكون قد
 *  راسلَت الرقمَ من جوّالها قبل قليل، وإلّا رفضه واتساب. */
drop function if exists public.admin_send_test(text);
create function public.admin_send_test(p_phone text)
returns uuid
language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
declare s record; v_req bigint; v_id uuid; v_txt text;
begin
  if not public.is_admin() then raise exception 'not authorised'; end if;
  select * into s from public.settings where id = 1;
  if coalesce(s.wa_phone_id, '') = '' or coalesce(public.wa_token(), '') = '' then
    raise exception 'لم يُربط حساب واتساب بعد';
  end if;

  v_txt := 'رسالة تجربة من ' || coalesce(s.business_name, 'المنصّة')
        || ' — إن وصلتك هذه فالإرسال التلقائي يعمل.';
  v_req := public.wa_send(p_to => p_phone, p_text => v_txt);

  insert into public.message_outbox (booking_id, template_id, trigger_kind, to_phone,
                                     due_at, status, body, attempts, request_id)
  values (null, null, 'test', p_phone, now(), 'sending', v_txt, 1, v_req)
  returning id into v_id;
  return v_id;
end $fn$;
revoke all on function public.admin_send_test(text) from public, anon;
grant execute on function public.admin_send_test(text) to authenticated;

/** تُستدعى بعد التجربة لقراءة الجواب فورًا بدل انتظار الدورة. */
drop function if exists public.admin_reconcile();
create function public.admin_reconcile()
returns integer language plpgsql security definer set search_path to 'public', 'pg_temp'
as $fn$
begin
  if not public.is_admin() then raise exception 'not authorised'; end if;
  return public.reconcile_sent_messages();
end $fn$;
revoke all on function public.admin_reconcile() from public, anon;
grant execute on function public.admin_reconcile() to authenticated;

/* السجلّ يُظهر رسائل التجربة أيضًا، ولا حجزَ لها. */
drop function if exists public.admin_outbox(integer);
create function public.admin_outbox(p_limit integer default 100)
returns TABLE (
  id uuid, booking_id uuid, ref text, client_name text, to_phone text,
  title text, trigger_kind text, due_at timestamptz, status text,
  body text, error text, sent_at timestamptz
)
language sql stable security definer set search_path to 'public', 'pg_temp'
as $$
  select o.id, o.booking_id, coalesce(b.ref, '—'),
         coalesce(b.client_name, case when o.trigger_kind = 'test' then 'رسالة تجربة' else '—' end),
         o.to_phone, coalesce(t.title, case when o.trigger_kind = 'test' then 'تجربة الإرسال' else '—' end),
         o.trigger_kind, o.due_at, o.status, o.body, o.error, o.sent_at
    from public.message_outbox o
    left join public.bookings b on b.id = o.booking_id
    left join public.message_templates t on t.id = o.template_id
   where public.is_admin()
   order by o.due_at desc
   limit greatest(coalesce(p_limit, 100), 1);
$$;
revoke all on function public.admin_outbox(integer) from public, anon;
grant execute on function public.admin_outbox(integer) to authenticated;
