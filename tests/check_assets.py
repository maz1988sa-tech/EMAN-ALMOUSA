# -*- coding: utf-8 -*-
"""بصمة الأصول: رقمٌ واحد في كل مرجع، ويتقدّم متى تغيّر ملفّ.

الصفحة تطلب assets/x.css?v=N. فإن تغيّر الملفّ وبقي N، خدم المتصفّح
نسخته المحفوظة — فيصل التعديل إلى المستودع ولا يصل إلى الشاشة. وهذا ما
وقع فعلًا: شريط التقويم الجديد وصل بلا تنسيقه.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import io, re, subprocess, sys, pathlib

# مكان العمل هو المختبر لا الجذر: الجذر مجمَّدٌ على ما يراه الناس حتى
# تُعتمد النسخة، فبصمة الأصول تُقاس على ما يُطوَّر فعلًا.
REPO = pathlib.Path(str(_H.REPO))
ROOT = REPO / 'lab'
PAGES = ['index.html', 'admin.html']
ok = fail = 0
def rec(n, c, x=""):
    global ok, fail
    if c: ok += 1;   print(f"PASS {n}" + (f" — {x}" if x else ""))
    else: fail += 1; print(f"FAIL {n} — {x}")

vers, refs = set(), []
for page in PAGES:
    text = (ROOT / page).read_text(encoding='utf-8')
    for m in re.finditer(r'(assets/[A-Za-z0-9_./-]+)\?v=(\d+)', text):
        refs.append((page, m.group(1), m.group(2)))
        vers.add(m.group(2))

rec("كل مرجعٍ يحمل إصدارًا", len(refs) >= 6, f"{len(refs)} مرجعًا")
rec("والإصدار واحدٌ في الصفحتين", len(vers) == 1, "، ".join(sorted(vers)))

missing = [r for r in refs if not (ROOT / r[1]).exists()]
rec("وكلُّ ملفٍّ مُشار إليه موجود", not missing, str(missing[:2]))

# الأصول التي تغيّرت منذ آخر رفعٍ للإصدار يجب أن تكون قبل ذلك الرفع
v = sorted(vers)[0] if vers else '0'
bump = subprocess.run(
    ['git', '-C', str(REPO), 'log', '-1', '--format=%H',
     '-S', f'?v={v}', '--', 'lab/index.html', 'lab/admin.html',
     'index.html', 'admin.html'],
    capture_output=True, text=True).stdout.strip()
rec("ولرفع الإصدار كومت يُعرَف", bool(bump), bump[:8])

if bump:
    changed = subprocess.run(
        ['git', '-C', str(REPO), 'diff', '--name-only', f'{bump}..HEAD', '--', 'lab/assets'],
        capture_output=True, text=True).stdout.split()
    dirty = subprocess.run(
        ['git', '-C', str(REPO), 'status', '--porcelain', '--', 'lab/assets'],
        capture_output=True, text=True).stdout.split('\n')
    dirty = [l[3:] for l in dirty if l.strip()]
    stale = sorted(set(changed) | set(dirty))
    rec("ولا أصلَ تغيّر بعده بلا رفعٍ جديد", not stale,
        "، ".join(stale[:3]) + (f" (+{len(stale)-3})" if len(stale) > 3 else ""))

print(f"\n=== {ok}/{ok+fail} passed ===")
sys.exit(1 if fail else 0)
