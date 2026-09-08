-- مجموعات الأحياء: حكمٌ واحد على عدّة أحياء، لا حيًّا حيًّا.
--
-- كان الشرط يُعلَّق على الحيّ مفردًا، فتضبط صاحبة العمل عشرين حيًّا عشرين
-- مرّة. وطلبُها أوضح: تختار مجموعةً من الأحياء، وتضع عليها حكمًا واحدًا،
-- وتحفظه باسم — ثمّ تصنع مجموعةً أخرى بحكمٍ آخر.
--
-- وأربعة أحكام تجتمع في المجموعة الواحدة:
--   لا نقدّم الخدمة هنا · لا أقلّ من عددٍ معيّن · رسوم إضافية ·
--   تسعيرةُ خدماتٍ مختلفة (وهي حالة العمارية: ثمانمئة للشخص).
--
-- والرابع ليس رسمًا فوق السعر بل **سعرًا بديلًا للخدمة في هذا الموقع**،
-- فيُخزَّن لكلّ خدمةٍ على حدة: العروس لها سعرها والسهرة لها سعرها.
--
-- وحيٌّ لا يكون في مجموعتين: حكمان متناقضان على موقعٍ واحد لا يُترك
-- بينهما ترجيحٌ صامت. تُرفض المحاولة وتُسمّى الأحياء المأخوذة.
--
-- ── الحدود ───────────────────────────────────────────────────────────
-- مئةٌ وثمانية وثمانون حيًّا مزروعة في القاعدة مرّةً واحدة. لا استيراد
-- ولا ملفّ عند صاحبة العمل: تفتح الشاشة فتجدها.

drop table if exists public.district_rules cascade;

create table if not exists public.hood_groups (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  sort        smallint not null default 0,
  active      boolean not null default true,   -- موقوفة لا محذوفة: الحكم موسميّ
  reject      boolean not null default false,
  min_people  smallint not null default 0,     -- ٠ = يُقبل شخصٌ واحد
  fee_amount  numeric(10,2) not null default 0,
  message     text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table if not exists public.hood_group_districts (
  -- المفتاح على الحيّ لا على الزوج: فهو ضمانُ ألّا يقع في مجموعتين.
  district_id bigint primary key references public.districts(id) on delete cascade,
  group_id    uuid not null references public.hood_groups(id) on delete cascade
);

create table if not exists public.hood_group_prices (
  group_id   uuid not null references public.hood_groups(id) on delete cascade,
  service_id uuid not null references public.services(id) on delete cascade,
  price      numeric(10,2) not null,
  primary key (group_id, service_id)
);

-- الملفّ الكامل موجودٌ في مستودع صاحب المشروع، والقاعدة تسحبه بنفسها
-- عبر pg_net مرّةً واحدة — فلا يمرّ بيد أحد ولا يُكتب في هذا المستودع:
--
--   select net.http_get('https://maz1988sa-tech.github.io/'
--     || 'Branch-Network-Intelligence/data/districts.js');
--   -- ثمّ يُقرأ من net._http_response ويُدرج في public.districts
--
-- بقيّة الدوالّ (check_location, admin_hood_groups, admin_save_hood_group,
-- admin_delete_hood_group, group_price, create_booking) مطبَّقةٌ على
-- القاعدة كما هي في هذا الملفّ من الترحيلات السابقة والمعدَّلة.
