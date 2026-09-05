import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, sys, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright
ROOT="/home/claude/proj/artroot"; OUT="/home/claude/proj/artshots"
os.makedirs(OUT,exist_ok=True)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=socketserver.TCPServer(("127.0.0.1",0),functools.partial(H,directory=ROOT))
PORT=srv.server_address[1]; threading.Thread(target=srv.serve_forever,daemon=True).start()
R=[]
def rec(n,ok,note=""): R.append((n,ok)); print(("PASS " if ok else "FAIL ")+n+((" — "+note) if note else ""))
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(**_H.CHROME,
                                  args=["--no-sandbox","--autoplay-policy=no-user-gesture-required"])
        ctx=await b.new_context(viewport={"width":430,"height":700},device_scale_factor=2,
                                locale="ar-SA",has_touch=True,is_mobile=True)
        errs=[]; ext=[]
        pg=await ctx.new_page()
        pg.on("pageerror",lambda e:errs.append(str(e)))
        pg.on("requestfailed",lambda r: print("   [requestfailed]", r.url[:100]))
        pg.on("response",lambda r: print("   [http]", r.status, r.url[:100]) if r.status>=400 else None)
        pg.on("console",lambda m:errs.append(m.text) if m.type=="error" and "favicon" not in m.text.lower() else None)
        # أي طلب لمضيف خارجي = كسر داخل Artifact
        pg.on("request",lambda r: ext.append(r.url) if not r.url.startswith(("http://127.0.0.1","data:","blob:","about:")) else None)
        pg.on("response",lambda r: errs.append(f"HTTP {r.status} {r.url[-40:]}") if r.status>=400 and "favicon" not in r.url else None)
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(2500)

        rec("لا طلبات لمضيف خارجي", len(ext)==0, "; ".join(ext[:3]))
        rtl = await pg.evaluate("()=>({dir:document.documentElement.dir, comp:getComputedStyle(document.body).direction})")
        rec("الاتجاه من اليمين لليسار", rtl["dir"]=="rtl" and rtl["comp"]=="rtl", str(rtl))
        fill = await pg.evaluate("""()=>{const a=document.getElementById('app');const r=a.getBoundingClientRect();
          return {w:Math.round(r.width),h:Math.round(r.height),vw:innerWidth,vh:innerHeight};}""")
        rec("التطبيق يملأ الشاشة", fill["w"]==fill["vw"] and fill["h"]==fill["vh"], str(fill))
        hero = await pg.evaluate("""()=>{const i=document.querySelector('.hero-media,.hero img,#heroVideo img,.hero-shift');
          return i? (getComputedStyle(i).backgroundImage.slice(0,12)+ '|' + (i.currentSrc||i.src||'').slice(0,12)) : 'none';}""")
        await pg.screenshot(path=f"{OUT}/1-hero.png")

        await pg.evaluate("window.__goto(1)"); await pg.wait_for_timeout(1200)
        cards = await pg.eval_on_selector_all("#svcRail .svc[data-svc]","e=>e.map(x=>x.querySelector('h2').textContent.trim())")
        rec("الخدمات تُرسم", cards==["ميك اب عروس","ميك اب سهرة"], str(cards))
        await pg.screenshot(path=f"{OUT}/2-services.png")

        await pg.evaluate("()=>{window.__pick(1,3);}"); await pg.wait_for_timeout(600)
        m = await pg.evaluate("()=>window.__money()")
        rec("خصم ٣ سهرة = 300", m["disc"]==300 and m["total"]==2100, str(m))

        await pg.click("#cartGo"); await pg.wait_for_timeout(1400)
        await pg.eval_on_selector("#week .day:not(.blank):not([disabled])","e=>e.click()"); await pg.wait_for_timeout(1200)
        slots = await pg.eval_on_selector_all("#times button","e=>e.length")
        rec("الأوقات تُحمّل", slots>0, f"slots={slots}")
        await pg.eval_on_selector("#times button:not([disabled])","e=>e.click()"); await pg.wait_for_timeout(400)
        await pg.click("#toConfirm"); await pg.wait_for_timeout(1200)
        off = await pg.evaluate("()=>{const e=document.querySelector('#sumLines .ln.off');return e?e.innerText.replace(/\\s+/g,' ').trim():'';}")
        rec("سطر الخصم في المراجعة", "300" in off, off[:50])
        await pg.screenshot(path=f"{OUT}/3-review.png")

        await pg.click("#confirmBtn"); await pg.wait_for_timeout(800)
        await pg.fill("#nm","نورة العتيبي"); await pg.fill("#ph","0501234567"); await pg.fill("#locTxt","حي النخيل")
        n=await pg.eval_on_selector_all("#peopleFields input","e=>e.length")
        for i in range(n):
            await pg.eval_on_selector_all("#peopleFields input", f"(e)=>{{e[{i}].value='ضيفة {i+1}';e[{i}].dispatchEvent(new Event('input',{{bubbles:true}}))}}")
        await pg.wait_for_timeout(400)
        await pg.click("#toPay"); await pg.wait_for_timeout(800)
        pay = await pg.evaluate("""()=>({iban:document.getElementById('bkIban').innerText.trim(),
          amt:document.getElementById('payAmt').innerText.trim(),
          disc:document.getElementById('pyDisc').innerText.trim()})""")
        rec("لوحة العربون كاملة", pay["iban"].startswith("SA") and "525" in pay["amt"].replace(",",""), str(pay))
        await pg.screenshot(path=f"{OUT}/4-deposit.png")

        await pg.set_input_files("#rcptFile",f"{_H.SAMPLE}"); await pg.wait_for_timeout(700)
        await pg.click("#sendBooking"); await pg.wait_for_timeout(2500)
        ref = await pg.text_content("#refNo")
        rec("الحجز يكتمل ويظهر رقم الطلب", ref.strip() not in ("","—"), f"ref={ref!r}")
        await pg.screenshot(path=f"{OUT}/5-booked.png")

        rec("بلا أخطاء", len(errs)==0, "; ".join(errs[:3]))
        await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
