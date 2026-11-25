# -*- coding: utf-8 -*-
"""صورة معاينة الرابط كما يقرؤها واتساب (§٧ف).

واتساب لا يشغّل JavaScript ولا يرى الصفحة مرسومة: يقرأ نصّ المستند كما يُخدَم، فيأخذ منه `og:image` ثمّ يجلبها.
فإن غاب الملفّ، أو ثقل، أو خالف مقاسُه الوسمَ، أُسقطت الصورة بصمت وعادت البطاقة عنوانًا ووصفًا بلا صورة — ولا خطأ
يُرى في أيّ مكان. فهذا الفحص يقرأ النصّ لا الصفحة: الوسوم في رأس المستند، ثمّ الملفّ الذي تشير إليه في جذر الفحص.
"""
import re, sys, pathlib
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
from PIL import Image

R = []
def rec(n, ok, note=""):
    R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

ROOT = pathlib.Path(_H.ROOT)


class Head(HTMLParser):
    """وسوم <meta> في الرأس وحده، وعنوان الصفحة — ما يقرؤه الزاحف قبل أيّ شيء آخر."""
    def __init__(self):
        super().__init__(); self.meta, self.title, self._in_title, self._head = {}, '', False, True
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'body': self._head = False
        elif tag == 'title': self._in_title = True
        elif tag == 'meta' and self._head:
            key = a.get('property') or a.get('name')
            if key: self.meta[key] = a.get('content') or ''
    def handle_endtag(self, tag):
        if tag == 'title': self._in_title = False
    def handle_data(self, d):
        if self._in_title: self.title += d


html = (ROOT / 'index.html').read_text(encoding='utf-8')
h = Head(); h.feed(html); m = h.meta

need = ['og:type', 'og:title', 'og:description', 'og:image', 'og:image:width', 'og:image:height', 'twitter:card']
missing = [k for k in need if not m.get(k)]
rec('الوسوم كلّها في رأس الصفحة', not missing, '، '.join(missing))
# العنوان والوصف نسختان من عنوان الصفحة ووصفها: إن غُيّر أحدهما وحده افترقت البطاقة عن الصفحة صامتةً.
rec('عنوان البطاقة هو عنوان الصفحة نفسه', m.get('og:title') == h.title.strip(), m.get('og:title', ''))
rec('ووصفها هو وصف الصفحة نفسه', m.get('og:description') == m.get('description'), m.get('og:description', ''))
rec('والبطاقة بصورةٍ كبيرة لا مصغّرة', m.get('twitter:card') == 'summary_large_image', m.get('twitter:card', ''))

src = m.get('og:image', '')
u = urlparse(src)
rec('رابط الصورة مطلقٌ على نطاق الموقع', u.scheme == 'https' and u.netloc == 'eman-aalmousa.com', src)
vers = set(re.findall(r'assets/[A-Za-z0-9_./-]+\?v=(\d+)', html))
v = parse_qs(u.query).get('v', [None])[0]
rec('وبصمتُه بصمةُ الأصول في الصفحة', len(vers) == 1 and v in vers, f'{v} من {sorted(vers)}')

f = ROOT / u.path.lstrip('/')
rec('والملفّ الذي يشير إليه موجود', f.is_file(), u.path)
if f.is_file():
    im = Image.open(f); kb = f.stat().st_size / 1024
    rec('JPEG', im.format == 'JPEG', str(im.format))
    rec('بالمقاس الذي يُعرض كبيرًا ١٢٠٠×٦٣٠', im.size == (1200, 630), f'{im.width}×{im.height}')
    rec('والمقاس في الوسم يطابق الملفّ',
        (m.get('og:image:width'), m.get('og:image:height')) == (str(im.width), str(im.height)),
        f"{m.get('og:image:width')}×{m.get('og:image:height')}")
    rec('وأخفّ من ٣٠٠ ك.ب', kb < 300, f'{kb:.0f} ك.ب')
    # والصورة ليست صفحةً فارغة: الحافة ورقُ العلامة، ووسطها الشعار بأسوده، وتحته سطرُ أميري بنحاسيّه.
    g = im.convert('RGB')
    lum = lambda p: 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]
    edge = g.getpixel((12, 315))
    rec('حافّتها ورق العلامة', edge[0] > 225 and edge[1] > 215 and edge[2] > 205 and edge[0] >= edge[1] >= edge[2], str(edge))
    logo = g.crop((400, 72, 800, 444)); n = logo.width * logo.height
    dark = sum(1 for p in logo.getdata() if lum(p) < 80) / n
    rec('ووسطها الشعار لا فراغ', dark > 0.03, f'{dark:.1%} من منطقته داكن')
    line = g.crop((330, 515, 870, 565)); n = line.width * line.height
    ink = sum(1 for p in line.getdata() if lum(p) < 170) / n
    rec('وتحته سطرُ النصّ', ink > 0.02, f'{ink:.1%} من منطقته حبر')

# اللوحة صفحةُ صاحبة العمل، لا تُرسَل لأحد: لا بطاقة معاينة لها.
adm = Head(); adm.feed((ROOT / 'admin.html').read_text(encoding='utf-8'))
rec('واللوحة بلا معاينة', 'og:image' not in adm.meta)

ok = sum(1 for _, o in R if o)
print(f"\n=== {ok}/{len(R)} passed ===")
sys.exit(0 if ok == len(R) else 1)
