#!/usr/bin/env bash
# ترقية المختبر إلى الحيّ.
#
# lab/ هي مكان العمل: كل تعديل يهبط فيها أوّلًا، ويُجرَّب على
# eman-aalmousa.com/lab/ بينما تبقى النسخة الحيّة كما هي. وحين تُعتمد،
# يُشغَّل هذا فينسخ المختبر فوق الجذر — نسخٌ محض بلا تحويل: الملفّان
# متطابقان بايتًا ببايت، فلا يوجد فرقٌ صامت بين ما جُرّب وما نُشر.
#
#   bash tools/promote.sh          يرقّي ثم يتحقّق
#   bash tools/promote.sh --check  يتحقّق فقط، بلا نسخ
#
# الشارة الحمراء تختفي من الحيّ وحدها: الصفحة تعرف موضعها من مسارها،
# فالملفّ نفسه يصمت في الجذر ويتكلّم في /lab/.

set -euo pipefail
cd "$(dirname "$0")/.."

ITEMS=(index.html admin.html sw.js manifest.webmanifest manifest-admin.webmanifest assets)
CHECK_ONLY="${1:-}"

if [ ! -d lab ]; then
  echo "✗ ما لقيت مجلّد lab/."; exit 1
fi

if [ "$CHECK_ONLY" != "--check" ]; then
  echo "› نسخ المختبر فوق الجذر…"
  for it in "${ITEMS[@]}"; do
    if [ -d "lab/$it" ]; then rm -rf "$it"; fi
    cp -a "lab/$it" "$it"
  done
fi

echo "› فحص التطابق…"
fail=0
for it in "${ITEMS[@]}"; do
  if ! diff -rq "lab/$it" "$it" >/dev/null 2>&1; then
    echo "  ✗ يختلف: $it"; diff -rq "lab/$it" "$it" | head -5; fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo; echo "✗ الجذر لا يطابق المختبر."; exit 1
fi

echo "✓ الجذر يطابق المختبر بايتًا ببايت."
if [ "$CHECK_ONLY" != "--check" ]; then
  echo
  echo "الخطوة التالية:"
  echo "  git add -A && git commit -m 'رقّي المختبر إلى الحيّ' && bash push-to-github.sh"
fi
