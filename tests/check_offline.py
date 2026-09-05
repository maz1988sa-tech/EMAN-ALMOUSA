# سقوط الشبكة أثناء الحفظ: تُعاد المحاولة بنفس المفتاح، وإن أصرّ الانقطاع
# ظهرت رسالة عربية لا "Load failed".
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, sys, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright
ROOT=str(_H.ROOT); OUT=f"{_H.SHOTS}"
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=socketserver.TCPServer(("127.0.0.1",0),functools.partial(H,directory=ROOT))
PORT=srv.server_address[1]; threading.Thread(target=srv.serve_forever,daemon=True).start()
MOCK=open(os.path.join(ROOT,"dev/mock-supabase.js"),encoding="utf-8").read()

# نُسقط النداء الذرّي أوّل __failN مرّة بخطأ سفاري نفسه.
OLD = "          if (fn === 'admin_create_booking' || fn === 'admin_replace_items') {"
NEW = """          if (fn === 'admin_create_booking' || fn === 'admin_replace_items') {
            if ((window.__failN || 0) > 0) {
              window.__failN--;
              return Promise.reject(new TypeError('Load failed'));
            }"""
assert OLD in MOCK; MOCK = MOCK.replace(OLD, NEW, 1)
# المحاكي يسجّل كل نداء مرّة واحدة، فتُقرأ المحاولات الثلاث كما وقعت.
R=[]
def rec(n,ok,note=""): R.append((n,ok)); print(("PASS " if ok else "FAIL ")+n+((" — "+note) if note else ""))

async def openSheet(pg):
    await pg.eval_on_selector_all("button, a",
        "els=>{const t=els.find(e=>/حجز يدوي|إضافة حجز/.test(e.textContent)); t && t.click();}")
    await pg.wait_for_timeout(600)
    # صار الزرّ يسأل: فردٌ أم مجموعة؟ فنمضي إلى الفرديّة.
    if await pg.evaluate("()=>!!document.getElementById('k-one')"):
        await pg.click("#k-one")
    await pg.wait_for_timeout(700)
    sid = await pg.evaluate("()=>document.querySelectorAll('[data-nd=\"+\"]')[1].dataset.sid")
    await pg.click(f'[data-nd="+"][data-sid="{sid}"]'); await pg.wait_for_timeout(200)
    await pg.fill("#n-name","اختبار الانقطاع")
    await pg.fill("#n-phone","0501234567")

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
        ctx=await b.new_context(viewport={"width":430,"height":900},device_scale_factor=2,locale="ar-SA")
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript",body=MOCK)))
        errs=[]
        pg=await ctx.new_page()
        await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
        pg.on("pageerror",lambda e:errs.append(str(e)))
        pg.on("console",lambda m:errs.append(m.text) if m.type=="error" and "404" not in m.text else None)
        await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(2000)

        # ── انقطاع عابر: محاولتان تسقطان ثمّ ينجح الحفظ ──────────────────
        await openSheet(pg)
        await pg.evaluate("()=>{window.__failN=2; window.__RPC=[];}")
        await pg.click("#n-save"); await pg.wait_for_timeout(6000)
        calls = await pg.evaluate("()=>(window.__RPC||[]).filter(r=>r.name==='admin_create_booking')")
        rec("الانقطاع العابر يُعاد تلقائيًا حتى ينجح", len(calls)==3, "محاولات=%d" % len(calls))
        keys = {c["args"].get("p_idem") for c in calls}
        rec("كل المحاولات بمفتاح واحد فلا يتكرّر الحجز", len(keys)==1, str(keys))
        saved = await pg.evaluate("()=>!document.querySelector('#sheet.on')")
        dbg = await pg.evaluate("()=>{const e=document.getElementById('n-err');const b=document.getElementById('n-save');return JSON.stringify({err:e?e.innerText.trim():'(لا ورقة)',btn:b?b.textContent.trim():null,sheetOpen:!!document.querySelector('#sheet.on')});}")
        rec("الورقة تُغلق بعد النجاح", saved, dbg[:90])

        # ── انقطاع مستمر: رسالة عربية لا Load failed ────────────────────
        await pg.wait_for_timeout(600)
        await openSheet(pg)
        await pg.evaluate("()=>{window.__failN=99; window.__RPC=[];}")
        await pg.click("#n-save"); await pg.wait_for_timeout(4500)
        msg = await pg.evaluate("()=>{const e=document.getElementById('n-err');return e?e.innerText.trim():'';}")
        rec("لا تظهر رسالة المتصفّح الخام", "Load failed" not in msg and "TypeError" not in msg, msg[:60])
        rec("تظهر رسالة عربية مفهومة", "تعذّر الوصول للإنترنت" in msg, msg[:60])
        rec("الرسالة تطمئنها أن الحجز لن يتكرّر", "لن يتكرّر" in msg, msg[:80])
        again = await pg.evaluate("()=>{const b=document.getElementById('n-save');return b?{on:!b.disabled,t:b.textContent.trim()}:null;}")
        rec("الزرّ يعود قابلًا للضغط", bool(again) and again["on"] and again["t"]=="حفظ الحجز", str(again))
        calls2 = await pg.evaluate("()=>(window.__RPC||[]).filter(r=>r.name==='admin_create_booking').length")
        rec("لا تُعاد المحاولة إلى ما لا نهاية", calls2==3, "محاولات=%s" % calls2)
        await pg.screenshot(path=f"{OUT}/offline-message.png", full_page=True)

        rec("بلا أخطاء", len(errs)==0, "; ".join(errs[:3]))
        await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
