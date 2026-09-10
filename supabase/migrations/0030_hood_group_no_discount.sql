-- الحكم الخامس: سعرٌ صافٍ — بلا خصم مجموعات.
--
-- كتبت صاحبة العمل للعمارية «٨٠٠ لكل وحدة»، وسعرُ «ميك اب سهرة» ٨٠٠
-- أصلًا. فلو كان قصدُها السعر نفسه لما قالت «الأسعار فيها تختلف».
-- والفرق أنّ خصم المجموعات (٢٠٠ للفرد) يجعل ثلاث عميلات يدفعن ٦٠٠ لكل
-- واحدة — فـ«٨٠٠ لكل وحدة» تعني: لا خصم هنا. وأكّده صاحب المشروع.
--
-- والأحكام الأربعة السابقة لا تعبّر عن هذا: تعديلُ سعر الخدمة إلى ٨٠٠
-- يبقى يُخصم منه ٢٠٠ فيعود ٦٠٠ صامتًا. لأنّ الخصم كان قرارَ **خدمة**
-- (`services.group_discount`) لا قرارَ **موقع**. فصار للموقع فيه قول.
--
-- ويمسّ الأثرُ موضعين: `create_booking` يحسب، و`check_location` يُبلّغ
-- الصفحةَ لتعرض الإجمالي الصحيح قبل الإرسال. وبلا الثاني ترى العميلة
-- ٦٠٠ ثمّ تُطالَب بـ٨٠٠.
--
-- والتعديل يُشتقّ من التعاريف القائمة بـ`pg_get_functiondef` لا يُعاد
-- كتابةً — الدوالّ طويلة، ونسخُها باليد يُدخل خطأً لا يراه أحد.
-- جُرّب في معاملةٍ رُجعت، وتُحقّق من صفر أثر قبل التطبيق.

alter table public.hood_groups
  add column if not exists no_group_discount boolean not null default false;

comment on column public.hood_groups.no_group_discount is
  'سعرٌ صافٍ في هذه المجموعة: خصم المجموعات لا يُطبَّق. العمارية ٨٠٠ للفرد لا ٦٠٠.';

do $do$
declare src text; out text;
begin
  -- ١) القراءة إلى اللوحة
  select pg_get_functiondef(p.oid) into src from pg_proc p join pg_namespace ns on ns.oid=p.pronamespace
   where ns.nspname='public' and p.proname='admin_hood_groups';
  if src not like '%no_group_discount%' then
    execute replace(src, '''message'', g.message,',
                         '''message'', g.message, ''no_group_discount'', g.no_group_discount,');
  end if;

  -- ٢) الحفظ من اللوحة
  select pg_get_functiondef(p.oid) into src from pg_proc p join pg_namespace ns on ns.oid=p.pronamespace
   where ns.nspname='public' and p.proname='admin_save_hood_group';
  if src not like '%no_group_discount%' then
    out := replace(src, 'fee_amount, message)', 'fee_amount, message, no_group_discount)');
    out := replace(out, 'nullif(btrim(coalesce(p_group->>''message'','''')), ''''))
    returning id into v_id;',
                        'nullif(btrim(coalesce(p_group->>''message'','''')), ''''),
            coalesce((p_group->>''no_group_discount'')::boolean, false))
    returning id into v_id;');
    out := replace(out, 'message = nullif(btrim(coalesce(p_group->>''message'','''')), ''''),
      updated_at = now()',
                        'message = nullif(btrim(coalesce(p_group->>''message'','''')), ''''),
      no_group_discount = coalesce((p_group->>''no_group_discount'')::boolean, false),
      updated_at = now()');
    execute out;
  end if;

  -- ٣) الحساب عند الحفظ
  select pg_get_functiondef(p.oid) into src from pg_proc p join pg_namespace ns on ns.oid=p.pronamespace
   where ns.nspname='public' and p.proname='create_booking';
  if src not like '%v_nodisc%' then
    out := replace(src, 'v_state text; v_people integer; v_loc jsonb;',
                        'v_state text; v_people integer; v_loc jsonb; v_nodisc boolean := false;');
    out := replace(out, 'v_gid   := nullif(v_loc->>''group_id'', '''')::uuid;',
                        'v_gid   := nullif(v_loc->>''group_id'', '''')::uuid;
    v_nodisc := coalesce((v_loc->>''no_group_discount'')::boolean, false);');
    out := replace(out, 'if v_grp >= 2 then v_disc := least(coalesce(v_rate, 0) * v_grp, v_total); end if;',
                        '/* خصمُ المجموعة قرارُ موقعٍ أيضًا: بعض الأحياء سعرُها صافٍ. */
  if v_grp >= 2 and not v_nodisc then
    v_disc := least(coalesce(v_rate, 0) * v_grp, v_total);
  end if;');
    if out not like '%and not v_nodisc%' then
      raise exception 'موضع الخصم في create_booking تغيّر — راجع التعريف';
    end if;
    execute out;
  end if;

  -- ٤) الإبلاغ إلى الصفحة
  select pg_get_functiondef(p.oid) into src from pg_proc p join pg_namespace ns on ns.oid=p.pronamespace
   where ns.nspname='public' and p.proname='check_location';
  if src not like '%no_group_discount%' then
    out := replace(src, 'v_prices jsonb := ''[]''::jsonb;',
                        'v_prices jsonb := ''[]''::jsonb; v_nodisc boolean := false;');
    out := replace(out, 'v_fee := grp.fee_amount; v_msg := grp.message;',
                        'v_fee := grp.fee_amount; v_msg := grp.message;
    v_nodisc := coalesce(grp.no_group_discount, false);');
    -- والسعرُ الصافي وحده شرطٌ يُبلَّغ عنه، وإلّا مرّ صامتًا
    out := replace(out, 'if v_fee > 0 or v_min > 1 or jsonb_array_length(v_prices) > 0 then',
                        'if v_fee > 0 or v_min > 1 or jsonb_array_length(v_prices) > 0 or v_nodisc then');
    out := replace(out, '''min_people'',v_min,''fee'',v_fee,''prices'',v_prices,',
                        '''min_people'',v_min,''fee'',v_fee,''prices'',v_prices,''no_group_discount'',v_nodisc,');
    execute out;
  end if;
end $do$;
