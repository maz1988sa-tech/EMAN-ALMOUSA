-- رسائل التواصل التي تكتبها بنفسها.
--
-- القوالب كانت محفورة في الكود: تعديل جملةٍ واحدة يحتاج إصدارًا جديدًا،
-- وإضافة رسالةٍ لم تكن ممكنة أصلًا. صارت صفوفًا تملكها هي.
--
-- والنصّ يحمل حقولًا بين قوسين معقوفين تُبدَّل عند الإرسال — فلا تكتب اسم
-- كل عميلة بيدها في كل مرّة، وهو أكثر ما يجعل قالبًا يُستعمل أو يُهجر.

create table if not exists public.message_templates (
  id          uuid primary key default gen_random_uuid(),
  title       text not null,
  body        text not null,
  sort        integer not null default 100,
  pinned      boolean not null default false,
  active      boolean not null default true,
  builtin     boolean not null default false,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists message_templates_sort_idx
  on public.message_templates (sort, created_at);

alter table public.message_templates enable row level security;

drop policy if exists "templates admin all" on public.message_templates;
create policy "templates admin all" on public.message_templates
  for all to authenticated
  using (public.is_admin()) with check (public.is_admin());

create or replace function public.message_templates_touch()
returns trigger language plpgsql
set search_path to 'public', 'pg_temp'
as $$ begin new.updated_at := now(); return new; end; $$;

drop trigger if exists message_templates_touch_trg on public.message_templates;
create trigger message_templates_touch_trg before update on public.message_templates
  for each row execute function public.message_templates_touch();

grant execute on function public.message_templates_touch() to authenticated;

-- القوالب التي كانت في الكود تُزرع مرّةً واحدة لتصير قابلةً للتعديل.
insert into public.message_templates (title, body, sort, builtin)
select * from (values
  ('تأكيد الحجز',
   E'أهلاً {الاسم} 🌸\nتم تأكيد موعدك مع {الاسم التجاري}:\n\n📅 {التاريخ}\n🕐 {الوقت}\n💄 {الخدمة}\n💰 الإجمالي: {الإجمالي}\n✅ العربون المستلم: {العربون}\n⏳ المتبقي: {المتبقي}\n\nلمتابعة حجزك:\n{رابط الحجز}\n\nبانتظارك 💗',
   10, true),
  ('تذكير بالموعد',
   E'تذكير بموعدك غدًا مع {الاسم التجاري} 🌸\n\n📅 {التاريخ}\n🕐 {الوقت}\n📍 {الموقع}\n\nالمتبقي: {المتبقي}\n\nنراكِ غدًا 💗',
   20, true),
  ('طلب العربون',
   E'أهلاً {الاسم} 🌸\nلتثبيت موعدك بتاريخ {التاريخ} الساعة {الوقت}، يلزم عربون {العربون} من إجمالي {الإجمالي}.\n\nشاكرين لكِ 💗',
   30, true),
  ('تأكيد الموقع',
   E'أهلاً {الاسم} 🌸\nوصلني موقعك، أراكِ {التاريخ} بإذن الله 💗',
   40, false),
  ('شكر بعد الخدمة',
   E'شكرًا لثقتك {الاسم} 🌸\nسعدنا بخدمتك اليوم.\n\nإن أعجبك العمل نتشرف بتقييمك ومشاركة صورك معنا 💗',
   50, true),
  ('اعتذار عن الموعد',
   E'أهلاً {الاسم} 🌸\nنعتذر، موعد {التاريخ} الساعة {الوقت} غير متاح حاليًا.\n\nيسعدنا اقتراح موعد آخر يناسبك 💗',
   60, true)
) as t(title, body, sort, builtin)
where not exists (select 1 from public.message_templates);
