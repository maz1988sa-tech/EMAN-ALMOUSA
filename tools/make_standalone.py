# -*- coding: utf-8 -*-
"""نسخةُ تجربةٍ من ملفٍّ واحد تُفتح من القرص — بلا خادم ولا قاعدة.

صاحب المشروع يجرّب على جهازه، والصفحة الحقيقية تحتاج خادمًا (وحدات ES لا
تُحمَّل من file://) وقاعدةً ودخولًا. فهذه تبني من `lab/` ملفًّا واحدًا:

- **القاعدة محاكاةٌ** — `dev/mock-supabase.js` نفسه الذي تقيس به الطُّقُم،
  فما يُجرَّب هنا هو ما فُحص هناك. ولا اتّصال بالقاعدة الحيّة بحال.
- **الوحدات** تُربط بخريطة استيراد (import map) إلى روابط data:، فتبقى
  الشيفرة حرفيّةً كما في المختبر لا نسخةً مُعادًا كتابتُها.
- **الخطوط** تُضمَّن، فلا تسقط العربية إلى خطٍّ احتياطيّ.
- **شريطٌ** في أعلاها يقول إنّها نسخة تجربة ببيانات افتراضية.

    python3 tools/make_standalone.py admin --pane clients -o out.html
    python3 tools/make_standalone.py admin --pane clients --from root -o live.html
"""
import argparse, base64, pathlib, re, sys

REPO = pathlib.Path(__file__).resolve().parent.parent
LAB = REPO / 'lab'
SRC = LAB  # يُبدَّل بـ --from root فتُبنى التجربة من الصفحة الحيّة

def b64(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"

def fonts_css() -> str:
    css = (SRC / 'assets' / 'fonts.css').read_text(encoding='utf-8')
    def sub(m):
        f = SRC / 'assets' / m.group(1)
        return f"url('{b64(f.read_bytes(), 'font/woff2')}')" if f.exists() else m.group(0)
    return re.sub(r"url\('([^']+\.woff2)'\)", sub, css)

def build(page: str, pane: str | None, extra_js: str) -> str:
    html = (SRC / f'{page}.html').read_text(encoding='utf-8')

    # الأنماط: الخطوط مضمَّنة، والسمة كما هي.
    def css_link(m):
        name = m.group(1)
        if name == 'fonts.css':
            return f"<style>{fonts_css()}</style>"
        return f"<style>{(SRC / 'assets' / name).read_text(encoding='utf-8')}</style>"
    html = re.sub(r'<link rel="stylesheet" href="assets/([a-z-]+\.css)\?v=\d+">', css_link, html)

    # المحاكاة مكان مكتبة Supabase، والإعداد مضمَّن.
    mock = (REPO / 'dev' / 'mock-supabase.js').read_text(encoding='utf-8')
    cfg = (SRC / 'assets' / 'config.js').read_text(encoding='utf-8')
    html = html.replace('<script src="assets/vendor/supabase.js"></script>',
                        f"<script>window.__MOCK_SIGNED_IN__ = true;\n{extra_js}\n</script>\n<script>{mock}</script>")
    html = html.replace('<script src="assets/config.js"></script>', f"<script>{cfg}</script>")

    # الوحدات: خريطةُ استيرادٍ من مساراتها كما تُطلب إلى نصّها.
    specs = sorted(set(re.findall(r"from '(\./assets/[a-z]+\.js\?v=\d+)'", html)))
    imap = {s: b64((SRC / s.split('?')[0][2:]).read_bytes(), 'text/javascript') for s in specs}
    import json
    html = html.replace('<script type="module">',
                        f'<script type="importmap">{json.dumps({"imports": imap})}</script>\n<script type="module">', 1)

    # صور العلامة وفيديوهاتها تُضمَّن حيثما ذُكرت: في `src` و`srcset`، وفي
    # `url()` داخل الأنماط المضمَّنة (مسارها هناك نسبيٌّ إلى assets/)، وفي
    # نصوص JS التي تبني بطاقات الخدمات — فالمحاكاة تعرض الصفحة كما هي.
    mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'svg': 'image/svg+xml',
            'webp': 'image/webp', 'mp4': 'video/mp4'}
    def asset(m):
        f = SRC / 'assets' / 'brand' / m.group(1)
        return b64(f.read_bytes(), mime.get(f.suffix[1:], 'application/octet-stream')) if f.exists() else m.group(0)
    html = re.sub(r'(?:assets/)?brand/([A-Za-z0-9_.-]+\.(?:png|jpg|svg|webp|mp4))(?:\?v=\d+)?', asset, html)

    # ما لا يعمل من القرص ولا يلزم التجربة: عامل الخدمة والبيان.
    html = re.sub(r'<link rel="manifest"[^>]*>', '', html)

    banner = """<div style="position:fixed;inset-inline:0;bottom:0;z-index:2147483647;
      background:#2b1c16;color:#fff;font:500 12px/1.5 'IBM Plex Sans Arabic',Tahoma,sans-serif;
      text-align:center;padding:7px 12px">نسخة تجربة — بيانات افتراضية، لا تتصل بقاعدة المنصّة</div>"""
    go = ''
    if pane:
        go = f"""<script>addEventListener('load',()=>setTimeout(()=>{{
          const t=[...document.querySelectorAll('[data-tab]')].find(e=>e.dataset.tab==='settings'); t&&t.click();
          setTimeout(()=>{{const p=document.querySelector('[data-pane="{pane}"]'); p&&p.click();}},400);
        }},900));</script>"""
    return html.replace('</body>', f'{banner}\n{go}\n</body>')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('page', choices=['admin', 'index'])
    ap.add_argument('--pane', default=None)
    ap.add_argument('--from', dest='src', choices=['lab', 'root'], default='lab',
                    help='lab (الافتراضيّ) أو root: الصفحة الحيّة كما تُنشر')
    ap.add_argument('--extra', default='', help='سطر JS يُنفَّذ قبل المحاكاة (بيانات إضافية)')
    ap.add_argument('-o', '--out', required=True)
    a = ap.parse_args()
    global SRC
    SRC = LAB if a.src == 'lab' else REPO
    out = build(a.page, a.pane, a.extra)
    pathlib.Path(a.out).write_text(out, encoding='utf-8')
    print(f'✓ {a.out}  ({len(out.encode()) // 1024} ك.ب)')

if __name__ == '__main__':
    sys.exit(main())
