# -*- coding: utf-8 -*-
"""أيقونة اللوحة على الشاشة الرئيسية: شعار إيمان على ورق العلامة.

كانت دائرةً بأعمدة واسمُها «لوحة التحكم»، فطلب صاحب المشروع شعارَ إيمان
واسمَها (٣ نوفمبر ٢٠٢٦). والمصدر الشعار نفسه `assets/brand/mark.png`،
فيومَ يتغيّر الشعار تُشغَّل هذه فتُعاد الأيقونات منه.

- **PNG بلا شفافية:** آيفون لا يرسم SVG على الشاشة الرئيسية، ويملأ
  الشفاف بالأسود — ومنه جاءت الحوافّ السوداء حول الدائرة القديمة.
- **«maskable» أصغر:** أندرويد يقصّ الأيقونة دائرةً أو مربّعًا أو غيرهما،
  والمضمون داخل دائرةٍ قطرُها ٨٠٪ وحده. فالشعار فيها ٥٨٪ عرضًا، وقطرُه
  ٣٩٥ من ٤١٠.

    python3 tools/admin_icons.py           # إلى lab/assets
    python3 tools/admin_icons.py --root    # وإلى assets في الجذر أيضًا
"""
import argparse, pathlib
from PIL import Image

REPO = pathlib.Path(__file__).resolve().parent.parent
PAPER = (0xFA, 0xF5, 0xF0, 255)   # --paper في صفحة العميلة، ولون خلفية البيان

# الاسم: (المقاس، عرض الشعار من المقاس)
SPECS = {
    'icon-admin-180.png': (180, 0.66),          # apple-touch-icon
    'icon-admin-192.png': (192, 0.66),
    'icon-admin-512.png': (512, 0.66),
    'icon-admin-maskable-512.png': (512, 0.58),
}

def render(mark: Image.Image, size: int, frac: float) -> Image.Image:
    w = round(size * frac)
    h = round(w * mark.height / mark.width)
    m = mark.resize((w, h), Image.LANCZOS)
    c = Image.new('RGBA', (size, size), PAPER)
    c.alpha_composite(m, ((size - w) // 2, (size - h) // 2))
    return c.convert('RGB')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', action='store_true', help='اكتب إلى أصول الجذر أيضًا')
    args = ap.parse_args()
    mark = Image.open(REPO / 'lab/assets/brand/mark.png').convert('RGBA')
    mark = mark.crop(mark.getbbox())
    dirs = [REPO / 'lab/assets'] + ([REPO / 'assets'] if args.root else [])
    for name, (size, frac) in SPECS.items():
        im = render(mark, size, frac)
        for d in dirs:
            im.save(d / name, optimize=True)
        print(f'✓ {name}  {size}×{size}')

if __name__ == '__main__':
    main()
