import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, json, os, re, sys, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright
ROOT=str(_H.ROOT); OUT=f"{_H.SHOTS}"
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=socketserver.TCPServer(("127.0.0.1",0),functools.partial(H,directory=ROOT))
PORT=srv.server_address[1]; threading.Thread(target=srv.serve_forever,daemon=True).start()
BASE=f"http://127.0.0.1:{PORT}/"
MOCK=open(os.path.join(ROOT,"dev/mock-supabase.js"),encoding="utf-8").read()
R=[]
def rec(n,ok,note=""): R.append((n,ok)); print(("PASS " if ok else "FAIL ")+n+((" — "+note) if note else ""))

# s1=عروس 1500 (لا خصم) · s2=سهرة 600 (خصم 100/شخص) · s3=تسريحة 400
CASES = [
  # (bridal, evening, expected_subtotal, expected_discount)
  (0,1, 600,   0),
  (0,2, 1200, 200),
  (0,3, 1800, 300),
  (2,0, 3000,   0),
  (1,3, 3300, 300),
  (2,2, 4200, 200),
]
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
        ctx=await b.new_context(viewport={"width":430,"height":700},has_touch=True,is_mobile=True,device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript",body=MOCK)))
        errs=[]
        pg=await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
        await pg.goto(BASE+"index.html"); await pg.wait_for_timeout(1700)

        for br, ev, exp_sub, exp_disc in CASES:
            await pg.evaluate(f"()=>{{window.__pick(0,{br}); window.__pick(1,{ev});}}")
            await pg.wait_for_timeout(350)
            got = await pg.evaluate("()=>{const m=window.__money();return {sub:m.sub,disc:m.disc,tot:m.total,n:m.people};}")
            ok = got['sub']==exp_sub and got['disc']==exp_disc and got['tot']==exp_sub-exp_disc
            rec(f"عروس {br} + سهرة {ev} ⇒ خصم {exp_disc}", ok,
                f"subtotal={got['sub']} discount={got['disc']} total={got['tot']} people={got['n']}")

        # سطر الخصم يظهر في شاشة المراجعة
        await pg.evaluate("()=>{window.__pick(0,1); window.__pick(1,3);}"); await pg.wait_for_timeout(400)
        await pg.click("#cartGo"); await pg.wait_for_timeout(1300)
        await pg.eval_on_selector("#week .day:not(.blank):not([disabled])","e=>e.click()"); await pg.wait_for_timeout(1100)
        await pg.eval_on_selector("#times button:not([disabled])","e=>e.click()"); await pg.wait_for_timeout(400)
        await pg.click("#toConfirm"); await pg.wait_for_timeout(1100)
        info = await pg.evaluate("""()=>{const off=document.querySelector('#sumLines .ln.off');
          return {shown:!!off, txt:off?off.innerText.replace(/\\s+/g,' ').trim():'',
                  total:document.getElementById('sumTotal').innerText.trim(),
                  lines:document.querySelectorAll('#sumLines .ln').length};}""")
        rec("سطر الخصم يظهر في المراجعة", info["shown"] and "300" in info["txt"], info["txt"][:60])
        rec("الإجمالي بعد الخصم = 3,000", info["total"].replace(",","").startswith("3000"), f"total={info['total']!r}")
        over = await pg.evaluate("()=>{const p=document.querySelector('#deck .screen:nth-child(4) .pad');return p.scrollHeight-p.clientHeight;}")
        rec("المراجعة تتّسع مع سطر الخصم", over<=0, f"over={over}")
        await pg.screenshot(path=f"{OUT}/disc-review.png")

        # ولوحة العربون
        await pg.click("#confirmBtn"); await pg.wait_for_timeout(700)
        await pg.fill("#nm","نورة"); await pg.fill("#ph","0501234567"); await pg.fill("#locTxt","حي النخيل"); await pg.wait_for_timeout(300)
        await pg.click("#toPay"); await pg.wait_for_timeout(700)
        pay = await pg.evaluate("""()=>({row:!document.getElementById('pyDiscRow').hidden,
          disc:document.getElementById('pyDisc').innerText.trim(),
          amt:document.getElementById('payAmt').innerText.trim(),
          tot:document.getElementById('payTotal').innerText.trim(),
          over:(()=>{const b=document.getElementById('sheetBody');return b.scrollHeight-b.clientHeight;})()})""")
        rec("سطر الخصم في لوحة العربون", pay["row"] and "300" in pay["disc"], pay["disc"])
        # عربون ثابت لكل خدمة: عروس 375 + ثلاث سهرات ×150 = 825
        rec("العربون مجموع مبالغ الخدمات = 825", pay["amt"].replace(",","").startswith("825"), f"amount={pay['amt']!r} total={pay['tot']!r}")
        rec("لوحة العربون تتّسع مع سطر الخصم", pay["over"]<=0, f"over={pay['over']}")
        await pg.screenshot(path=f"{OUT}/disc-pay.png")

        # شخص واحد ⇒ لا سطر خصم إطلاقًا
        await pg.click("#payBack"); await pg.wait_for_timeout(400)
        await pg.evaluate("()=>{window.__pick(0,0); window.__pick(1,1);}"); await pg.wait_for_timeout(500)
        gone = await pg.evaluate("()=>({disc:window.__money().disc, off:!!document.querySelector('#sumLines .ln.off')})")
        rec("شخص واحد ⇒ لا خصم ولا سطر", gone["disc"]==0 and not gone["off"], str(gone))

        rec("بلا أخطاء", len(errs)==0, "; ".join(errs[:3]))
        await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
