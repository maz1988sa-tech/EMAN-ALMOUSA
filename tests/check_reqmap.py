# -*- coding: utf-8 -*-
"""رابط الموقع: إلزاميّ أو لا، بمفتاحٍ واحد.

المفتاح يغيّر ثلاثة أشياء لا شيئًا واحدًا: ما يقوله الحقل عن نفسه، ومتى
يُفتح زرّ المتابعة، وما يقبله الخادم. الفحص يمرّ عليها الثلاثة، لأنّ
واجهةً تمنع وخادمًا يسمح ليست حمايةً بل مظهرها.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright

ROOT = str(_H.ROOT)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
MOCK = open(os.path.join(ROOT, "dev/mock-supabase.js"), encoding="utf-8").read()

ok = fail = 0
def rec(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1;   print(f"PASS {name}" + (f" — {extra}" if extra else ""))
    else:    fail += 1; print(f"FAIL {name} — {extra}")

async def openForm(pg):
    await pg.evaluate("()=>{window.__pick(1,3); window.__goto(2);}"); await pg.wait_for_timeout(1100)
    await pg.evaluate("()=>{const b=[...document.querySelectorAll('#week button.day:not([disabled])')]; if(b.length) b[b.length>2?2:0].click();}")
    await pg.wait_for_timeout(900)
    await pg.evaluate("()=>{const t=[...document.querySelectorAll('#times [data-slot]')]; if(t.length) t[0].click();}")
    await pg.wait_for_timeout(600)
    await pg.click("#confirmBtn"); await pg.wait_for_timeout(800)
    await pg.fill("#nm", "نورة العتيبي")
    await pg.fill("#ph", "0501234567")
    await pg.fill("#locTxt", "حي النخيل، الرياض")
    await pg.wait_for_timeout(300)

async def scenario(b, need):
    mock = MOCK.replace("require_loc_map:false,", f"require_loc_map:{'true' if need else 'false'},")
    ctx = await b.new_context(viewport={"width": 430, "height": 932}, has_touch=True,
                              is_mobile=True, device_scale_factor=2)
    def h(route):
        asyncio.ensure_future(route.fulfill(content_type="application/javascript", body=mock))
    await ctx.route("**/assets/vendor/supabase.js", h)
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1500)
    await openForm(pg)

    tag = "إلزامي" if need else "اختياري"
    lab = await pg.evaluate("""()=>({opt:document.getElementById('locOpt').textContent.trim(),
        dot:!document.getElementById('locReq').hidden,
        req:document.getElementById('loc').hasAttribute('required')})""")
    rec(f"[{tag}] الحقل يقول عن نفسه", (tag in lab["opt"]) and lab["dot"] == need and lab["req"] == need, str(lab))

    dis = lambda: pg.evaluate("()=>document.getElementById('toPay').disabled")
    empty = await dis()
    rec(f"[{tag}] الزرّ والحقل فارغ", empty == need, f"معطّل={empty}")

    await pg.fill("#loc", "https://example.com/not-maps"); await pg.wait_for_timeout(250)
    bad = await dis()
    rec(f"[{tag}] رابطٌ ليس خرائط يُرفض في الحالين", bad is True, f"معطّل={bad}")

    await pg.fill("#loc", "https://maps.app.goo.gl/aBcD1234"); await pg.wait_for_timeout(250)
    good = await dis()
    rec(f"[{tag}] الرابط الصحيح يفتح المتابعة", good is False, f"معطّل={good}")

    if need:
        await pg.fill("#loc", ""); await pg.evaluate("()=>document.getElementById('loc').blur()")
        await pg.wait_for_timeout(300)
        msg = await pg.evaluate("""()=>{const e=document.getElementById('locErr');
            return {on:e.classList.contains('on'), txt:e.textContent.trim()};}""")
        rec("[إلزامي] الفراغ يقول سببه لا يصمت",
            msg["on"] and "مطلوب" in msg["txt"], msg["txt"][:46])
        await pg.screenshot(path="/home/claude/proj/cmp/23-reqmap.png")

    rec(f"[{tag}] بلا أخطاء", len(errs) == 0, "; ".join(errs[:2]))
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(
            **_H.CHROME,
            args=["--no-sandbox"])
        await scenario(b, False)
        await scenario(b, True)
        await b.close()

asyncio.run(main())
print(f"\n=== {ok}/{ok+fail} passed ===")
