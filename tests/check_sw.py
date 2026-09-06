# -*- coding: utf-8 -*-
"""عامل الخدمة: هل تصل النسخةُ الجديدة من أوّل زيارة؟

وقع هذا فعلًا: نُشر عدُّ الزوّار، فُتحت الصفحة الحيّة، ولم تُسجَّل زيارة.
والسبب أنّ عامل الخدمة كان يخدم المستند المحفوظ أوّلًا ويحدّثه في
الخلفية — فأوّل زيارة بعد كلّ نشرٍ ترى النسخة السابقة. والأصول تحمل
بصمةً في مسارها فلا يصيبها هذا، أمّا `index.html` فمساره ثابت.

فهنا يُقاس ما يصل المتصفّح فعلًا: صفحةٌ تُحفظ، ثمّ تتغيّر على الخادم،
ثمّ تُفتح مرّةً واحدة — فإن ظهرت القديمة سقط الطقم. ويُقاس معه أنّ وعد
العمل بلا شبكة لم يُكسر.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, shutil, tempfile, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright

SITE = pathlib.Path(tempfile.mkdtemp(prefix='sw-'))
shutil.copy2(_H.LAB / 'sw.js', SITE / 'sw.js')
(SITE / 'assets').mkdir()
(SITE / 'assets' / 'app.js?v=1').write_text('', encoding='utf-8')

PAGE = """<!doctype html><html lang="ar"><head><meta charset="utf-8"><title>t</title></head>
<body><b id="mark">%s</b>
<script>
navigator.serviceWorker.register('./sw.js');
</script></body></html>"""

def put(mark):
    (SITE / 'index.html').write_text(PAGE % mark, encoding='utf-8')
    (SITE / 'admin.html').write_text(PAGE % mark, encoding='utf-8')

put('v1')

class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    # ملاحظةٌ للقادم: لا تُضِف `Cache-Control: no-store` هنا. الملفّ الذي
    # يحمله يتعذّر حفظه في Cache API، فيتعلّق تنصيب العامل ولا ينشط أبدًا،
    # فيبدو الطقم ساقطًا والمنتَج سليم.

class TS(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

srv = TS(("127.0.0.1", 0), functools.partial(H, directory=str(SITE)))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{PORT}"

R = []
def rec(n, ok, note=""):
    R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

async def controlled(pg):
    return await pg.evaluate("()=>!!navigator.serviceWorker.controller")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**_H.CHROME, args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 430, "height": 900})
        pg = await ctx.new_page()

        await pg.goto(f"{BASE}/index.html")
        # لا يُقاس شيء قبل أن يتولّى العامل فعلًا، وإلّا قِسنا لا شيء.
        ready = await pg.evaluate("""async () => {
          const t = new Promise((r) => setTimeout(() => r(false), 12000));
          return await Promise.race([navigator.serviceWorker.ready.then(() => true), t]);
        }""")
        rec("التنصيب لا يتعلّق", ready is True)
        await pg.reload(); await pg.wait_for_timeout(1000)
        for _ in range(6):
            if await controlled(pg): break
            await pg.wait_for_timeout(500); await pg.reload()
        rec("عامل الخدمة يتولّى الصفحة", await controlled(pg))

        mark = await pg.inner_text('#mark')
        rec("النسخة المحفوظة هي الأولى", mark == 'v1', mark)

        # ── نشرٌ جديد على الخادم ───────────────────────────────────────
        put('v2')
        await pg.reload(); await pg.wait_for_timeout(1200)
        mark = await pg.inner_text('#mark')
        rec("أوّل زيارة بعد النشر ترى الجديد", mark == 'v2', 'ظهر ' + mark)

        await pg.goto(f"{BASE}/admin.html"); await pg.wait_for_timeout(900)
        mark = await pg.inner_text('#mark')
        rec("ولوحة التحكّم كذلك", mark == 'v2', 'ظهر ' + mark)

        # ── الوعد الآخر: تعمل بلا شبكة ────────────────────────────────
        await ctx.set_offline(True)
        try:
            await pg.goto(f"{BASE}/index.html", wait_until='domcontentloaded', timeout=15000)
            await pg.wait_for_timeout(600)
            mark = await pg.inner_text('#mark')
            ok = mark in ('v1', 'v2')
        except Exception as e:
            mark, ok = str(e)[:60], False
        rec("بلا شبكة تُخدَم النسخة المحفوظة", ok, 'ظهر ' + mark)

        await ctx.set_offline(False)
        await ctx.close(); await b.close()

asyncio.run(main())
shutil.rmtree(SITE, ignore_errors=True)
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
