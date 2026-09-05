import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, sys, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright
ROOT=str(_H.ROOT)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=socketserver.TCPServer(("127.0.0.1",0),functools.partial(H,directory=ROOT))
PORT=srv.server_address[1]; threading.Thread(target=srv.serve_forever,daemon=True).start()
MOCK=open(os.path.join(ROOT,"dev/mock-supabase.js"),encoding="utf-8").read()
R=[]
def rec(n,ok,note=""): R.append((n,ok)); print(("PASS " if ok else "FAIL ")+n+((" — "+note) if note else ""))

async def openSettings(pg):
    await pg.wait_for_timeout(1200)
    await pg.evaluate("()=>{const t=[...document.querySelectorAll('[data-tab]')].find(e=>/الإعدادات/.test(e.textContent)); if(t) t.click();}")
    await pg.wait_for_timeout(900)
    await pg.evaluate("()=>{const p=[...document.querySelectorAll('[data-pane],.panebar button,.seg button')].find(e=>/عام|الإعدادات/.test(e.textContent)); if(p&&p.click) p.click();}")
    await pg.wait_for_timeout(900)

async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
    ctx=await b.new_context(viewport={"width":430,"height":932},device_scale_factor=2)
    await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript",body=MOCK)))
    pg=await ctx.new_page(); errs=[]; pg.on("pageerror",lambda e:errs.append(str(e)))
    await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
    await pg.goto(f"http://127.0.0.1:{PORT}/admin.html")
    await openSettings(pg)
    has = await pg.evaluate("()=>!!document.getElementById('pg-scope')")
    rec("بطاقة الحذف موجودة في الإعدادات", has)
    if not has:
        print(await pg.evaluate("()=>document.body.innerText.slice(0,400)"))
    else:
        await pg.wait_for_timeout(700)
        m = await pg.evaluate("()=>({txt:document.getElementById('pg-count').innerText, dis:document.getElementById('pg-go').disabled})")
        rec("المعاينة تعدّ تلقائيًا", ('حجز' in m["txt"] or 'حجوزات' in m["txt"] or 'لا حجوزات' in m["txt"]), m["txt"])

        # كل الحجوزات يلزمه كتابة الكلمة
        await pg.select_option("#pg-scope","all"); await pg.wait_for_timeout(700)
        m1 = await pg.evaluate("()=>({dis:document.getElementById('pg-go').disabled, conf:!document.getElementById('pg-confirm').hidden, txt:document.getElementById('pg-count').innerText})")
        rec("«الكل» يطلب كلمة تأكيد والزر معطّل", m1["conf"] and m1["dis"], m1["txt"])
        await pg.fill("#pg-word","حذف"); await pg.wait_for_timeout(300)
        m2 = await pg.evaluate("()=>document.getElementById('pg-go').disabled")
        rec("الزر يعمل بعد كتابة «حذف»", not m2)
        await pg.fill("#pg-word","xx"); await pg.wait_for_timeout(250)
        m3 = await pg.evaluate("()=>document.getElementById('pg-go').disabled")
        rec("كلمة خاطئة تُعطّل الزر", m3)

        # النطاق المخصّص يُظهر حقلي التاريخ ويمنع قبل اكتمالهما
        await pg.select_option("#pg-scope","range"); await pg.wait_for_timeout(600)
        m4 = await pg.evaluate("()=>({d:!document.getElementById('pg-dates').hidden, dis:document.getElementById('pg-go').disabled, t:document.getElementById('pg-count').innerText})")
        rec("النطاق المخصّص يُظهر التاريخين ويمنع قبل ملئهما", m4["d"] and m4["dis"], m4["t"])

        # أسبوع قادم
        await pg.select_option("#pg-scope","week"); await pg.wait_for_timeout(800)
        m5 = await pg.evaluate("()=>document.getElementById('pg-count').innerText")
        rec("أسبوع قادم يعرض عدّة", ('حجز' in m5 or 'حجوزات' in m5 or 'لا حجوزات' in m5), m5)

        # التنفيذ الفعلي
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.select_option("#pg-scope","all"); await pg.wait_for_timeout(700)
        await pg.fill("#pg-word","حذف"); await pg.wait_for_timeout(250)
        before = await pg.evaluate("()=>document.getElementById('pg-count').innerText")
        await pg.click("#pg-go"); await pg.wait_for_timeout(1800)
        after = await pg.evaluate("()=>document.getElementById('pg-count') ? document.getElementById('pg-count').innerText : 'reloaded'")
        rec("الحذف ينفَّذ ويعيد العدّ إلى صفر", 'لا حجوزات' in after or after=='reloaded', f"{before!r} -> {after!r}")
    rec("بلا أخطاء", not errs, "; ".join(errs[:2]))
    await ctx.close(); await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
