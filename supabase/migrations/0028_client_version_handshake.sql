-- مصافحةُ النسخة: مفتاحٌ يُشعل لا يكسر صفحةً لا تعرفه.
--
-- وقع مرّتين، والثانيةُ ضاع فيها حجزُ عميلة: مفتاح `loc_check_enabled`
-- في القاعدة، والقاعدة مشتركة بين المختبر والحيّ (§٢). فتُجرَّب
-- الاشتراطات في المختبر فيشتعل المفتاح على الصفحة الحيّة — وهي لا تحمل
-- شيفرة الفحص فلا ترسل إحداثيّات — فيردّ `create_booking` كلَّ حجز
-- بـ«نحتاج تحديد موقعك على الخريطة».
--
-- والتنبيه في اللوحة لم يكفِ: التنبيه يُقرأ ويُنسى، والحارس يجب أن
-- يمتنع من نفسه. فصار الإلزام يعرف **من ينادي**: الصفحة الجديدة تقول
-- `p_client_v = 2`، وما لم تقُلها فهي صفحةٌ لا تعرف الموقع أصلًا
-- فلا تُطالَب به. وهذا يُبقي المفتاح صالحًا للتجربة في المختبر في أيّ
-- لحظة، بلا أثرٍ على العميلات حتى تُرقّى الصفحات.
--
-- والثمن مقبول: من ينادي القاعدة مباشرةً بنسخةٍ ١ يتخطّى شرط الحيّ.
-- والحجز يصل `pending` وتراه صاحبة العمل قبل التأكيد، فالخسارة محدودة
-- — بخلاف انقطاع الحجز كلِّه، وقد وقع مرّتين. ويُوسَم التخطّي في
-- `activity_log.detail->>'loc_skipped'` فلا يمرّ صامتًا.
--
-- والتعديل يُشتقّ من التعريف القائم بـ`pg_get_functiondef` لا يُعاد
-- كتابته: الدالّة مئةُ سطر، ونسخُها بالید يُدخل خطأً لا يراه أحد.

do $do$
declare
  src text; out text; n1 int; n2 int; n3 int;
  sig_old text := 'text,text,date,time without time zone,uuid[],text[],'
                  || 'text,text,text,text,numeric,numeric';
begin
  select pg_get_functiondef(p.oid) into src
    from pg_proc p join pg_namespace ns on ns.oid = p.pronamespace
   where ns.nspname = 'public' and p.proname = 'create_booking'
   order by p.pronargs desc limit 1;

  if src is null then
    raise exception 'create_booking غير موجودة';
  end if;

  -- طُبِّق سابقًا؟ لا شيء يُفعل.
  if src like '%p_client_v integer DEFAULT 1%' then
    raise notice 'المصافحة مركّبة أصلًا — لا تغيير';
    return;
  end if;

  select count(*) into n1 from regexp_matches(src, 'p_lng numeric DEFAULT NULL::numeric\)', 'g');
  select count(*) into n2 from regexp_matches(src, 'if coalesce\(v_locchk, false\) then', 'g');
  select count(*) into n3 from regexp_matches(src, '''hood_group'', v_gid\)\);', 'g');
  if n1 <> 1 or n2 <> 1 or n3 <> 1 then
    raise exception 'مواضع التعديل غير متوقّعة: وسيط=% شرط=% سجلّ=% — راجع التعريف',
      n1, n2, n3;
  end if;

  out := replace(src, 'p_lng numeric DEFAULT NULL::numeric)',
                      'p_lng numeric DEFAULT NULL::numeric, p_client_v integer DEFAULT 1)');
  out := replace(out, 'if coalesce(v_locchk, false) then',
                      'if coalesce(v_locchk, false) and coalesce(p_client_v, 1) >= 2 then');
  out := replace(out, '''hood_group'', v_gid));',
                      '''hood_group'', v_gid, ''loc_skipped'', '
                   || '(coalesce(v_locchk,false) and coalesce(p_client_v,1) < 2)));');

  execute out;

  /* والقديمةُ تُسقط: توقيعان لاسمٍ واحد يُعجزان PostgREST عن الاختيار.
     والصفحة القديمة تنادي بالأسماء ووسيطُها الجديد له افتراض، فتصل
     الدالّةَ الجديدة بلا تعديلٍ فيها. */
  execute 'drop function if exists public.create_booking(' || sig_old || ')';
  execute 'grant execute on function public.create_booking('
       || sig_old || ',integer) to anon, authenticated';
end $do$;
