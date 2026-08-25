-- وسائط الخدمة: فيديو تسويقي أو صورة، مع تموضعها داخل الإطار.
--
-- كانت خلفية بطاقة الخدمة عند العميلة مُثبَّتة في الشيفرة وتُطابَق باسم
-- الخدمة، فخدمةٌ جديدة تأخذ خلفية غيرها أو لا تأخذ شيئًا. هنا تُرفع
-- لكل خدمة وسيطتها، ويُحفظ معها موضعها فيظهر الوجه في المنتصف كما
-- ضبطته صاحبته لا كما تصادف القصّ.

alter table public.services
  add column if not exists media_kind  text,          -- 'video' | 'image' | null
  add column if not exists media_path   text,
  add column if not exists poster_path  text,         -- صورةٌ تسبق تشغيل الفيديو
  add column if not exists media_x      numeric not null default 50,   -- ٪ أفقيًّا
  add column if not exists media_y      numeric not null default 50,   -- ٪ رأسيًّا
  add column if not exists media_zoom   numeric not null default 1;

alter table public.services
  drop constraint if exists services_media_kind_chk;
alter table public.services
  add constraint services_media_kind_chk
  check (media_kind is null or media_kind in ('video', 'image'));

alter table public.services
  drop constraint if exists services_media_frame_chk;
alter table public.services
  add constraint services_media_frame_chk
  check (media_x between 0 and 100 and media_y between 0 and 100
         and media_zoom between 1 and 3);

-- دلوٌ عامّ للقراءة: هذه وسائط تسويقيّة تُعرض لكل من يفتح رابط الحجز،
-- وإخفاؤها خلف توقيعٍ مؤقّت يبطئ الصفحة بلا سرٍّ يُحمى. الكتابة للمالكة
-- وحدها.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('service-media', 'service-media', true, 26214400,
        array['image/jpeg','image/png','image/webp','video/mp4','video/webm','video/quicktime'])
on conflict (id) do update
  set public = excluded.public,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "service media readable"  on storage.objects;
drop policy if exists "service media writable"  on storage.objects;
drop policy if exists "service media updatable" on storage.objects;
drop policy if exists "service media deletable" on storage.objects;

create policy "service media readable" on storage.objects
  for select using (bucket_id = 'service-media');

create policy "service media writable" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'service-media' and public.is_admin());

create policy "service media updatable" on storage.objects
  for update to authenticated
  using (bucket_id = 'service-media' and public.is_admin())
  with check (bucket_id = 'service-media' and public.is_admin());

create policy "service media deletable" on storage.objects
  for delete to authenticated
  using (bucket_id = 'service-media' and public.is_admin());
