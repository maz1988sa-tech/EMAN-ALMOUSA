#!/usr/bin/env bash
# يرفع تحديث **المختبر وحده** إلى maz1988sa-tech/EMAN-ALMOUSA.
#
# التشغيل:   bash push-lab.sh
#
# الفرق عن push-to-github.sh: هذا يرفض الرفع إن كانت الحزمة تغيّر ملفًّا
# من النسخة الحيّة. الوعد بأنّ «الجذر لم يُلمس» لا يكفي — يُفحص قبل كل
# رفعة، فلا يصل زوجتَك شيءٌ لم تعتمده أنت.
#
# وحين تعتمد المختبر وتريد نقله إلى الحيّ، هناك مسارٌ آخر:
#   bash tools/promote.sh   داخل نسخة العمل، ثم push-to-github.sh

set -uo pipefail

REPO="https://github.com/maz1988sa-tech/EMAN-ALMOUSA.git"
BRANCH="claude/iman-booking-system-s8s6rh"
HERE="$(cd "$(dirname "$0")" && pwd)"
BUNDLE="$HERE/eam-update.bundle"

# ملفّات النسخة الحيّة: ما يفتحه الناس على eman-aalmousa.com
LIVE=(index.html admin.html sw.js manifest.webmanifest manifest-admin.webmanifest assets)

if ! command -v git >/dev/null 2>&1; then
  echo "✗ git غير مثبّت. شغّل:  xcode-select --install"; exit 1
fi
if [ ! -f "$BUNDLE" ]; then
  echo "✗ ما لقيت eam-update.bundle بجانب السكربت."; exit 1
fi

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

echo "› استنساخ المستودع…"
if ! git clone --quiet --branch "$BRANCH" "$REPO" "$WORK/repo"; then
  echo "✗ تعذّر الاستنساخ — تأكد من الاتصال بالإنترنت."; exit 1
fi
cd "$WORK/repo"

echo "› فحص الحزمة…"
if ! git bundle verify "$BUNDLE" >/dev/null 2>&1; then
  echo "✗ الحزمة لا تطابق هذا المستودع. محتواها:"
  git bundle list-heads "$BUNDLE"; exit 1
fi

BEFORE="$(git rev-parse HEAD)"
REF="$(git bundle list-heads "$BUNDLE" | awk '{print $2}' | grep -v '^HEAD$' | head -1)"
[ -z "$REF" ] && REF="HEAD"

echo "› سحب الكومت من الحزمة… ($REF)"
if ! git fetch --quiet "$BUNDLE" "$REF"; then
  echo "✗ تعذّر قراءة الحزمة."; exit 1
fi
if ! git merge --ff-only --quiet FETCH_HEAD 2>/dev/null; then
  echo
  echo "✗ الحزمة لا تكمّل ما على GitHub — التاريخان تباعدا."
  echo "  على GitHub : $(git --no-pager log --oneline -1 HEAD)"
  echo "  في الحزمة  : $(git --no-pager log --oneline -1 FETCH_HEAD)"
  exit 1
fi
AFTER="$(git rev-parse HEAD)"

if [ "$BEFORE" = "$AFTER" ]; then
  if git merge-base --is-ancestor FETCH_HEAD HEAD 2>/dev/null; then
    echo "✓ كل شيء مرفوع — ما في الحزمة موجودٌ على GitHub بالفعل."; exit 0
  fi
  echo "✗ الحزمة لا تحمل جديدًا — الملف قديم. اطلب نسخة جديدة."; exit 1
fi

# ── الحارس: هل تمسّ هذه الرفعة النسخة الحيّة؟ ──────────────────────────
echo "› فحص النسخة الحيّة…"
TOUCHED="$(git diff --name-only "$BEFORE" "$AFTER" -- "${LIVE[@]}")"
if [ -n "$TOUCHED" ]; then
  echo
  echo "✗ أُوقفت الرفعة: هذه الحزمة تغيّر النسخة الحيّة."
  echo
  echo "  الملفّات التي ستتغيّر عند زوجتك:"
  echo "$TOUCHED" | sed 's/^/    · /' | head -20
  echo
  echo "  إن كنتَ تقصد الترقية فعلًا، استخدم:  bash push-to-github.sh"
  echo "  وإلّا فأخبرني لأصلح الحزمة."
  exit 1
fi
echo "  ✓ لم يتغيّر أيُّ ملفٍّ حيّ — الرفعة تمسّ المختبر وحده."

echo
echo "› الكومت الجاهز للرفع ($(git rev-list --count "$BEFORE".."$AFTER")):"
git --no-pager log --oneline "$BEFORE".."$AFTER"
echo
echo "› الرفع… (إن طلب Username اكتب: maz1988sa-tech)"
echo "  وإن طلب Password فهو Personal Access Token لا كلمة السرّ."
echo

if git push origin "$BRANCH"; then
  echo
  echo "✓ تم الرفع — المختبر وحده."
  echo
  echo "  المختبر : https://eman-aalmousa.com/lab/"
  echo "  اللوحة  : https://eman-aalmousa.com/lab/admin.html"
  echo
  echo "  والنسخة الحيّة كما هي: https://eman-aalmousa.com/"
else
  echo
  echo "✗ فشل الرفع — غالبًا صلاحية دخول."
  echo "  أنشئ توكن: https://github.com/settings/tokens ← Generate new token (classic) ← repo"
  exit 1
fi
