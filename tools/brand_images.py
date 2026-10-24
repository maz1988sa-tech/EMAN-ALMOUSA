# -*- coding: utf-8 -*-
"""صور العلامة كما تُخدَم: مشتقّات WebP من الأصول، بمقاس الشاشة لا مقاس الملفّ.

الأصول (`.jpg` و`.png` في `lab/assets/brand/`) تبقى كما سُلّمت — هي المرجع
الذي تُستبدل منه الصورة يوم تتغيّر. وما تطلبه الصفحة هو ما يُولَّد هنا:
WebP بعرضٍ يكفي شاشة الجوال وجودةٍ لا تُرى تحتها فرق.

كان الغلاف يُنزَّل 565 ك.ب بمقاس 1290×2795 — ضعف ما تعرضه أعلى شاشة جوال —
فالفتح الأوّل كان 1.3 م.ب على بيانات الجوال، وثلثُ الزائرات يخرجن من
الشاشة الأولى. فصار الغلاف مقاسين يختار المتصفّح منهما بكثافة شاشته
(`srcset`)، والبقيّة مقاسًا واحدًا.

    python3 tools/brand_images.py          # يولّد ما تغيّر أو غاب
    python3 tools/brand_images.py --force  # يعيد توليد الكلّ

يُكتب الناتج بجانب الأصل: `hero_still-800.webp` من `hero_still.jpg`.
"""
import argparse, pathlib, sys
from PIL import Image

BRAND = pathlib.Path(__file__).resolve().parent.parent / 'lab' / 'assets' / 'brand'

# (الأصل، العرض بالبكسل، الجودة) — العرض يُحذف من الاسم حين يكون واحدًا.
DERIVED = [
    # الغلاف يملأ ارتفاع الشاشة: 390 نقطة عرضًا على جوال، بكثافة ٢ أو ٣.
    ('hero_still.jpg',    800,  75, 'hero_still-800.webp'),
    ('hero_still.jpg',    1170, 75, 'hero_still-1170.webp'),
    # نسيجٌ يُفرَش بشفافية: جودةٌ أدنى لا تُرى.
    ('dust_a.jpg',        800,  68, 'dust_a.webp'),
    ('dust_light.jpg',    760,  68, 'dust_light.webp'),
    # ملصقات الفيديو ومصغّرات الخدمات بمقاسها الأصليّ.
    ('pst_bridal.jpg',    720,  75, 'pst_bridal.webp'),
    ('pst_evening.jpg',   720,  75, 'pst_evening.webp'),
    ('thumb_bridal.jpg',  480,  75, 'thumb_bridal.webp'),
    ('thumb_evening.jpg', 480,  75, 'thumb_evening.webp'),
]

def build(src: pathlib.Path, width: int, quality: int, dst: pathlib.Path) -> int:
    im = Image.open(src).convert('RGB')
    if width < im.width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(dst, 'WEBP', quality=quality, method=6)
    return dst.stat().st_size

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    total_in = total_out = 0
    for name, width, q, out in DERIVED:
        src, dst = BRAND / name, BRAND / out
        if not src.exists():
            print(f'✗ الأصل غائب: {src.name}'); return 1
        fresh = dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime
        if fresh and not a.force:
            size = dst.stat().st_size; mark = '·'
        else:
            size = build(src, width, q, dst); mark = '✓'
        total_in += src.stat().st_size; total_out += size
        print(f'{mark} {out:24} {size // 1024:4} ك.ب  ← {name} ({src.stat().st_size // 1024} ك.ب)')
    print(f'\nالمجموع: {total_in // 1024} ← {total_out // 1024} ك.ب')
    return 0

if __name__ == '__main__':
    sys.exit(main())
