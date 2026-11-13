#!/usr/bin/env python3
"""يلفّ الترحيل ٠٠٤١ وفحصَه في معاملةٍ واحدة تُرجَع، ليُجرَّب على الحيّ قبل أن يُطبَّق (§٥).

الترحيل يُنفَّذ بـ EXECUTE داخل كتلة الفحص نفسها، ثمّ تجري عليه الفحوص، ثمّ يرفع الاستثناءُ
الأخير فتُرجَع المعاملة كاملةً بما فيها DDL. الناتج ملفّ SQL يُلصق في محرّر Supabase أو يُمرَّر
لأداة الإدارة؛ وقراءةُ «ROLLBACK_OK ... ok=N bad=0» هي الحكم.

    .venv/bin/python tools/trial_reserved.py > /tmp/trial.sql
"""
import pathlib, re, sys

REPO = pathlib.Path(__file__).resolve().parent.parent
mig = (REPO / "supabase/migrations/0041_reserved_periods.sql").read_text(encoding="utf-8")
test = (REPO / "supabase/tests/reserved_periods.sql").read_text(encoding="utf-8")
for tag in ("$mig41$", "$trial$"):
    assert tag not in mig + test, f"الوسم {tag} مستعمَل في النصّ"
m = re.search(r"do \$do\$\n(.*?\n)  -- ⟪test⟫\n", test, re.S)
assert m, "لم أجد مقدّمة كتلة الفحص"
head = m.group(1)                                   # declare … begin … create temp table
tail = test[test.index("  -- ⟪test⟫\n"):test.rindex("end $do$;")]
# التعليقات الكاملة السطر لا أثرَ لها في التنفيذ، وحذفُها يُصغّر ما يُلصق في المحرّر. وتُحذف
# من الترحيل ما بدأ بـ-- في أوّل السطر وحده (ما داخل متون الدوالّ مُزاحٌ فيبقى).
mig = "\n".join(l for l in mig.split("\n") if not l.startswith("--"))
tail = "\n".join(l for l in tail.split("\n") if not l.lstrip().startswith("--"))
sys.stdout.write(f"do $trial$\n{head}  execute $mig41${mig}$mig41$;\n{tail}end $trial$;\n")
