-- المشروع يمنح anon تنفيذ كل دالّة جديدة في public افتراضيًا، و«revoke من
-- public» لا يمسّ ذلك المنح لأنّه منحٌ مباشر لا وراثة. الحارس داخل الدوال
-- كان يردّ الزائر (is_admin تكذب على غير المسجَّل) لكنّ ألّا يُطرق الباب
-- أولى من أن يُطرق ويُردّ.
revoke execute on function public.admin_create_booking(jsonb, jsonb, uuid)  from anon;
revoke execute on function public.admin_replace_items(uuid, jsonb, numeric) from anon;
revoke execute on function public.admin_snapshot()                          from anon;
revoke execute on function public.admin_restore_snapshot(jsonb, boolean)    from anon;
