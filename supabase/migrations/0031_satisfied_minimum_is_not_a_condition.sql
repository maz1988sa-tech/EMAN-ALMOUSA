-- أقلُّ عددٍ مستوفًى ليس شرطًا يُعرض.
--
-- كان اختبار «هل على هذا الموقع شرط؟» يضمّ `v_min > 1`، فمجموعةٌ حكمُها
-- «شخصان فأكثر» تُظهر نافذةً لمن جاءت بشخصين — وقد استوفت الشرط.
-- والمنع قائمٌ قبله في حال `blocked`، فذكرُه بعد الاستيفاء ضجيجٌ لا خبر.
-- وثلاثةٌ وعشرون حيًّا حكمُها هذا، فكانت كلُّ عميلةٍ فيها ترى نافذة.
--
-- وردُّ «بلا شرط» صار يحمل المجموعة وأسعارها وحكمَ الخصم: مجموعةٌ حكمُها
-- الحدُّ وحده تعود ok، وبلا هذه الحقول تضيع تسعيرتُها الخاصّة لو أُضيفت
-- لاحقًا — عطبٌ صامت ينتظر.

do $do$
declare src text; out text;
begin
  select pg_get_functiondef(p.oid) into src from pg_proc p join pg_namespace ns on ns.oid=p.pronamespace
   where ns.nspname='public' and p.proname='check_location';

  out := replace(src,
    'if v_fee > 0 or v_min > 1 or jsonb_array_length(v_prices) > 0 or v_nodisc then',
    'if v_fee > 0 or jsonb_array_length(v_prices) > 0 or v_nodisc then');
  out := replace(out,
    'return jsonb_build_object(''state'',''ok'',''checked'',true,''district'',v_where,''district_id'',d.id);',
    'return jsonb_build_object(''state'',''ok'',''checked'',true,''district'',v_where,
    ''district_id'',d.id,''group_id'',v_gid,''prices'',v_prices,
    ''no_group_discount'',v_nodisc,''min_people'',v_min);');

  if out = src then
    raise notice 'مطبَّقٌ أصلًا — لا تغيير';
  else
    execute out;
  end if;
end $do$;
