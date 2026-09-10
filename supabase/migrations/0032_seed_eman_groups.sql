-- مجموعات صاحبة العمل الثلاث — مبنيّةٌ لها لا مكتوبةٌ عليها.
--
-- كتبت زوجةُ صاحب المشروع اشتراطاتها في واتساب: ٢٨ موضعًا وثلاثة أحكام.
-- وطلب أن تُجهَّز في اللوحة جاهزةً قابلةً للتعديل، لا أن تبنيها بيدها
-- ثلاثين اختيارًا.
--
-- **وهي بياناتٌ لا شيفرة**: تُعدَّل من اللوحة متى شاءت — تُضيف حيًّا أو
-- تنقله أو تُطفئ مجموعةً بمفتاح `active`. وهذا الملفّ يوثّق ما زُرع
-- أوّلَ مرّة، لا يفرضه ثانيةً: يمرّ صامتًا إن وجد المجموعات قائمة، فلا
-- يمسح تعديلًا أجرته.
--
-- والأسماء مأخوذة من جدول الأحياء لا من رسائلها، فما بينهما فرقٌ
-- تُصلحه هي: «مخطط الخير» أقربُ ما له «حي الخير»، و«العريجا الغربية»
-- في البيانات «حي العريجاء الغربي». وضُمّت الأحياء المشابهة بقرار صاحب
-- المشروع: ظهرة البديعة مع البديعة، ووادي لبن مع لبن، وضاحية نمار مع
-- نمار، والعريجاء الوسطى مع العريجاء.
--
-- والغروب والموسى لا تُذكران: كلتاهما داخل محافظة الدرعية وحكمُهما
-- حكمُها، فحدُّها يغطّيهما (§٠٠٢٩).

do $do$
declare
  g_rej uuid; g_two uuid; g_amm uuid; sid uuid;
  rej text[] := array['محافظة الخرج','محافظة المزاحمية','حي الخير','حي عكاظ','حي ديراب','حي عريض'];
  two text[] := array['حي الشفا','حي السويدي','حي السويدي الغربي','حي بدر','حي الحزم','حي طويق',
                      'حي العوالي','حي العزيزية','حي الدار البيضاء','حي البديعة','حي ظهرة البديعة',
                      'حي المنصورة','عرقة','محافظة الدرعية','حي ظهرة لبن','حي لبن','حي وادي لبن',
                      'حي العريجاء','حي العريجاء الغربي','حي العريجاء الوسطى','حي نمار',
                      'حي ضاحية نمار','حي المهدية'];
begin
  if exists (select 1 from public.hood_groups where name in ('لا نخدم هنا','شخصان فأكثر','العمارية')) then
    raise notice 'مجموعاتها قائمة — لا تُمسّ';
    return;
  end if;

  -- مجموعتا التجربة تزولان: «الخليج» كانت مضبوطةً على الرفض.
  delete from public.hood_group_districts
   where group_id in (select id from public.hood_groups where name in ('Test','الخليج'));
  delete from public.hood_group_prices
   where group_id in (select id from public.hood_groups where name in ('Test','الخليج'));
  delete from public.hood_groups where name in ('Test','الخليج');

  insert into public.hood_groups (name, sort, active, reject, message)
  values ('لا نخدم هنا', 1, true, true, 'نعتذر، لا نصل إلى هذا الموقع حاليًا.')
  returning id into g_rej;
  insert into public.hood_group_districts (district_id, group_id)
  select d.id, g_rej from public.districts d where d.ar = any(rej)
  on conflict (district_id) do update set group_id = excluded.group_id;

  insert into public.hood_groups (name, sort, active, min_people, message)
  values ('شخصان فأكثر', 2, true, 2, 'هذا الموقع نخدمه لحجزٍ من شخصين فأكثر.')
  returning id into g_two;
  insert into public.hood_group_districts (district_id, group_id)
  select d.id, g_two from public.districts d where d.ar = any(two)
  on conflict (district_id) do update set group_id = excluded.group_id;

  /* العمارية: ثلاثة أحكام تجتمع. وسعرُ السهرة لا يُكتب — ٨٠٠ أصلًا،
     والمقصود ألّا يُخصم منه، وذاك مفتاحٌ لا سعر. */
  insert into public.hood_groups (name, sort, active, min_people, no_group_discount, message)
  values ('العمارية', 3, true, 2, true,
          'في العمارية: السعر ٨٠٠ للفرد بلا خصم مجموعات، والعروس ٢٣٠٠، ولشخصين فأكثر.')
  returning id into g_amm;
  insert into public.hood_group_districts (district_id, group_id)
  select d.id, g_amm from public.districts d where d.ar = 'العمارية'
  on conflict (district_id) do update set group_id = excluded.group_id;

  select id into sid from public.services where name = 'ميك اب عروس';
  if sid is not null then
    insert into public.hood_group_prices (group_id, service_id, price) values (g_amm, sid, 2300);
  end if;

  if (select count(*) from public.hood_group_districts where group_id = g_two) <> 23 then
    raise exception 'أحياء «شخصان فأكثر» ليست ٢٣ — راجع الأسماء';
  end if;
end $do$;
