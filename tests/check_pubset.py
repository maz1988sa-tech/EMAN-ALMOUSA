# -*- coding: utf-8 -*-
"""ما تقرؤه الصفحة من الإعدادات لا بدّ أن تُرجعه القاعدة.

`get_public_settings` تُعدِّد أعمدتها بالاسم. فعمودٌ يُضاف إلى جدول
الإعدادات ولا يُضاف إليها لا يصل صفحة العميلة أبدًا — والصفحة تقرؤه
`undefined` فتتصرّف كأنّه مُطفأ، صامتةً بلا خطأ.

وقع فعلًا: `loc_check_enabled` أُضيف إلى الجدول ولم يُضف إلى الدالّة،
فبقي فحص الموقع لا يعمل على صفحة حجزٍ حقيقية ولا مرّة — بينما نجحت
الطُّقُم كلُّها، لأنّ المحاكي كان يردّ الجدول كلَّه.

فهذا الفحص يقارن **ما تقرؤه الصفحة** بـ**ما يردّه المحاكي**، والمحاكي
مقيَّدٌ بقائمة أعمدة الدالّة الحقيقية. ودرِيْفُ القاعدة نفسها يحرسه
`supabase/tests/public_settings_coverage.sql`.
"""
import re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H

R = []
def rec(n, ok, note=""):
    R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

ROOT = pathlib.Path(_H.ROOT)
page = (ROOT / "index.html").read_text(encoding="utf-8")
mock = (ROOT / "dev/mock-supabase.js").read_text(encoding="utf-8")

# ما تقرؤه الصفحة
read = set(re.findall(r"state\.settings\??\.([a-z_]+)", page))
rec("الصفحة تقرأ إعداداتٍ بالاسم", len(read) >= 8, f"{len(read)} مفتاحًا")

# ما يردّه المحاكي — وهو مقيَّدٌ بأعمدة الدالّة الحقيقية
m = re.search(r"const PUBLIC_SETTING_KEYS = \[(.*?)\];", mock, re.S)
rec("المحاكي يُعلن قائمة أعمدة الدالّة", bool(m))
served = set(re.findall(r"'([a-z_]+)'", m.group(1))) if m else set()
rec("والقائمة غير فارغة", len(served) >= 15, f"{len(served)} عمودًا")

missing = sorted(read - served)
rec("كلُّ ما تقرؤه الصفحة تردّه القاعدة",
    not missing, "غائب: " + "، ".join(missing) if missing else "")

# ولا يُقيَّد المحاكي بقائمةٍ ثم يردّ غيرها
rec("والمحاكي يردّ الإسقاط لا الجدول كلَّه",
    "publicSettings()" in mock and "ok([SETTINGS])" not in mock)

# مفتاح فحص الموقع بعينه — العطب الذي أوجد هذا الفحص
rec("مفتاح فحص الموقع يصل الصفحة",
    "loc_check_enabled" in served and "loc_check_enabled" in read)

bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
