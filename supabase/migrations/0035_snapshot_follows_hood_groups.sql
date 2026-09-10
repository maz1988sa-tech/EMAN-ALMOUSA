-- ٠٠٣٥ — النسخة الاحتياطية تلحق بالمجموعات.
--
-- ٠٠٢٦ أسقط `district_rules` وبنى مكانه `hood_groups` وأخواته، ولم يمسّ
-- اللقطة. فبقيت `admin_snapshot` تقرأ جدولًا لا وجود له — **فسقطت من
-- يومها**: كلُّ نداءٍ يرفع `relation "public.district_rules" does not
-- exist`، والنسخةُ السحابية والملفُّ المنزَّل كلاهما منها. أي أنّ المشروع
-- بلا نسخةٍ احتياطية منذ ٠٠٢٦، وبلا إنذارٍ لأنّ لا أحد نادى.
--
-- وهذا العطبُ بعينه هو ما بُني `snapshot_coverage.sql` ليمنعه (§٧ج) —
-- ولم يُشغَّل بعد ٠٠٢٦. فالحارس الذي لا يُشغَّل ليس حارسًا، وهو درسُ
-- التنبيه في §٧د نفسه.
--
-- والتصحيح يُشتقّ من التعريف القائم بالاستبدال لا يُعاد كتابةً: نسخةٌ
-- تُكتب باليد لدالّةٍ من مئةٍ وخمسين سطرًا تتباعد عن أصلها.

do $do$
declare v_src text; v_new text;
begin
  -- ١) اللقطة: الجداول الثلاثة مكان الجدول الساقط، ومعها عدّاداتها —
  --    فما حُفظ ولم يُذكر يُسقط الفحص (§٧ج).
  select pg_get_functiondef(p.oid) into v_src
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'admin_snapshot';
  if v_src is null then raise exception 'admin_snapshot غير موجودة'; end if;

  v_new := replace(v_src, E'    ''district_rules'',     coalesce((select jsonb_agg(to_jsonb(x) order by x.district_id) from public.district_rules x), ''[]''::jsonb),', E'    ''hood_groups'',          coalesce((select jsonb_agg(to_jsonb(x) order by x.sort, x.created_at) from public.hood_groups x), ''[]''::jsonb),\n    ''hood_group_districts'', coalesce((select jsonb_agg(to_jsonb(x) order by x.district_id) from public.hood_group_districts x), ''[]''::jsonb),\n    ''hood_group_prices'',    coalesce((select jsonb_agg(to_jsonb(x) order by x.group_id, x.service_id) from public.hood_group_prices x), ''[]''::jsonb),');
  if v_new = v_src then raise exception 'لم يُعثر على سطر district_rules في اللقطة'; end if;
  v_src := v_new;

  v_new := replace(v_src, E'    ''district_rules'', jsonb_array_length(v->''district_rules''),', E'    ''hood_groups'', jsonb_array_length(v->''hood_groups''),\n    ''hood_group_districts'', jsonb_array_length(v->''hood_group_districts''),\n    ''hood_group_prices'', jsonb_array_length(v->''hood_group_prices''),');
  if v_new = v_src then raise exception 'لم يُعثر على عدّاد district_rules'; end if;
  execute v_new;

  -- ٢) الاستعادة: بالترتيب نفسه — المجموعة قبل أحيائها وأسعارها، فكلاهما
  --    يشير إليها بمفتاحٍ أجنبيّ. وصفٌّ يشير إلى غائبٍ يُترك بدل أن يُسقط
  --    الاستعادة كلَّها؛ فحيٌّ أو خدمةٌ لم يعودا لا يمنعان بقيّة النسخة.
  select pg_get_functiondef(p.oid) into v_src
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'admin_restore_snapshot';
  if v_src is null then raise exception 'admin_restore_snapshot غير موجودة'; end if;

  v_new := replace(v_src, E'  n_act int := 0; n_scan int := 0; n_dis int := 0; n_drul int := 0;', E'  n_act int := 0; n_scan int := 0; n_dis int := 0;\n  n_hg int := 0; n_hgd int := 0; n_hgp int := 0;');
  if v_new = v_src then raise exception 'لم يُعثر على سطر التصريح في الاستعادة'; end if;
  v_src := v_new;

  v_new := replace(v_src, E'  with src as (select * from jsonb_populate_recordset(null::public.district_rules,\n                                 coalesce(p_data->''district_rules'', ''[]''::jsonb)))\n  , ins as (insert into public.district_rules\n            select s.* from src s\n             where exists (select 1 from public.districts d where d.id = s.district_id)\n            on conflict (district_id) do nothing returning 1)\n  select count(*) into n_drul from ins;', E'  with src as (select * from jsonb_populate_recordset(null::public.hood_groups,\n                                 coalesce(p_data->''hood_groups'', ''[]''::jsonb)))\n  , ins as (insert into public.hood_groups select * from src\n            on conflict (id) do nothing returning 1)\n  select count(*) into n_hg from ins;\n\n  with src as (select * from jsonb_populate_recordset(null::public.hood_group_districts,\n                                 coalesce(p_data->''hood_group_districts'', ''[]''::jsonb)))\n  , ins as (insert into public.hood_group_districts\n            select s.* from src s\n             where exists (select 1 from public.districts d where d.id = s.district_id)\n               and exists (select 1 from public.hood_groups g where g.id = s.group_id)\n            on conflict (district_id) do nothing returning 1)\n  select count(*) into n_hgd from ins;\n\n  with src as (select * from jsonb_populate_recordset(null::public.hood_group_prices,\n                                 coalesce(p_data->''hood_group_prices'', ''[]''::jsonb)))\n  , ins as (insert into public.hood_group_prices\n            select s.* from src s\n             where exists (select 1 from public.hood_groups g where g.id = s.group_id)\n               and exists (select 1 from public.services v where v.id = s.service_id)\n            on conflict (group_id, service_id) do nothing returning 1)\n  select count(*) into n_hgp from ins;');
  if v_new = v_src then raise exception 'لم يُعثر على كتلة استعادة الشروط'; end if;
  v_src := v_new;

  v_new := replace(v_src, E'    ''districts'', n_dis, ''district_rules'', n_drul,', E'    ''districts'', n_dis, ''hood_groups'', n_hg,\n    ''hood_group_districts'', n_hgd, ''hood_group_prices'', n_hgp,');
  if v_new = v_src then raise exception 'لم يُعثر على سطر الحصيلة في الاستعادة'; end if;
  execute v_new;
end $do$;

revoke all on function public.admin_restore_snapshot(jsonb, boolean) from public, anon;
grant execute on function public.admin_restore_snapshot(jsonb, boolean) to authenticated;
grant execute on function public.admin_snapshot() to authenticated, service_role;
