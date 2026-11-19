#!/usr/bin/env python3
"""يلفّ ترحيلًا وفحصَه في معاملةٍ واحدة تُرجَع، ليُجرَّب على الحيّ قبل أن يُطبَّق (§٥).

الترحيل يُنفَّذ بـ EXECUTE داخل كتلة الفحص نفسها، ثمّ تجري عليه الفحوص، ثمّ يرفع الاستثناءُ
الأخير فتُرجَع المعاملة كاملةً بما فيها DDL. الناتج ملفّ SQL يُلصق في محرّر Supabase أو يُمرَّر
لأداة الإدارة؛ وقراءةُ «ROLLBACK_OK ... ok=N bad=0» هي الحكم.

    .venv/bin/python tools/trial_reserved.py > /tmp/trial.sql            # ٠٠٤١ وفحصه
    .venv/bin/python tools/trial_reserved.py supabase/migrations/0042_reserved_beyond_horizon.sql \\
        supabase/tests/reserved_horizon.sql > /tmp/trial.sql             # ترحيلٌ وفحصٌ بعينهما

والفحص يُعلَّم بـ⟪test⟫ و⟪/test⟫: ما بينهما يُنقل بعد الترحيل، وما قبلهما (declare … begin) رأسُ الكتلة.
"""
import pathlib, re, sys

REPO = pathlib.Path(__file__).resolve().parent.parent
args = sys.argv[1:]
mig = (REPO / (args[0] if args else "supabase/migrations/0041_reserved_periods.sql")).read_text(encoding="utf-8")
test = (REPO / (args[1] if len(args) > 1 else "supabase/tests/reserved_periods.sql")).read_text(encoding="utf-8")
for tag in ("$mig$", "$trial$"):
    assert tag not in mig + test, f"الوسم {tag} مستعمَل في النصّ"
m = re.search(r"do \$do\$\n(.*?\n)  -- ⟪test⟫\n", test, re.S)
assert m, "لم أجد مقدّمة كتلة الفحص"
head = m.group(1)                                   # declare … begin … create temp table
tail = test[test.index("  -- ⟪test⟫\n"):test.rindex("end $do$;")]
# التعليقات الكاملة السطر لا أثرَ لها في التنفيذ، وحذفُها يُصغّر ما يُلصق في المحرّر. وتُحذف
# من الترحيل ما بدأ بـ-- في أوّل السطر وحده (ما داخل متون الدوالّ مُزاحٌ فيبقى).
mig = "\n".join(l for l in mig.split("\n") if not l.startswith("--"))
tail = "\n".join(l for l in tail.split("\n") if not l.lstrip().startswith("--"))
sys.stdout.write(f"do $trial$\n{head}  execute $mig${mig}$mig$;\n{tail}end $trial$;\n")
