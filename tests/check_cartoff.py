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
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
        for vh in (640, 700, 932):
            ctx=await b.new_context(viewport={"width":430,"height":vh},has_touch=True,is_mobile=True,device_scale_factor=2)
            await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript",body=MOCK)))
            pg=await ctx.new_page(); await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1600)
            await pg.evaluate("window.__goto(1)"); await pg.wait_for_timeout(900)

            # شخص واحد: لا سطر خصم
            await pg.evaluate("()=>window.__pick(1,1)"); await pg.wait_for_timeout(500)
            st=await pg.evaluate("()=>{const e=document.getElementById('cartOff');return {hidden:e.hidden,pop:e.classList.contains('pop')};}")
            if vh==700: rec("شخص واحد: لا سطر خصم", st["hidden"], str(st))

            # شخصان: يظهر ويقفز
            await pg.evaluate("()=>window.__pick(1,2)")
            await pg.wait_for_timeout(120)
            mid=await pg.evaluate("()=>{const e=document.getElementById('cartOff');const cs=getComputedStyle(e);return {pop:e.classList.contains('pop'),anim:cs.animationName,t:cs.transform};}")
            await pg.wait_for_timeout(800)
            end=await pg.evaluate("""()=>{const e=document.getElementById('cartOff');const cs=getComputedStyle(e);
              const bar=document.getElementById('svcCart').getBoundingClientRect();
              const inner=document.querySelector('#svcRail .svc.active .svc-inner');
              const btn=document.querySelector('#svcRail .svc.active .pick').getBoundingClientRect();
              return {size:cs.fontSize, t:cs.transform, txt:e.innerText.replace(/\\s+/g,' ').trim(),
                      barTop:Math.round(bar.top), btnBottom:Math.round(btn.bottom),
                      barH:Math.round(bar.height)};}""")
            if vh==700:
                rec("القفزة تعمل عند الظهور", mid["pop"] and mid["anim"]=="offPop", str(mid)[:80])
                rec("يستقرّ ثابتًا بعدها", end["t"] in ("none","matrix(1, 0, 0, 1, 0, 0)"), end["t"])
                rec("الخط أكبر (17px)", end["size"]=="17px", end["size"])
                rec("النص صحيح", "تم تطبيق خصم المجموعة" in end["txt"] and "200" in end["txt"], end["txt"])
            rec(f"[{vh}] الشريط لا يغطّي زر الحجز", end["btnBottom"] <= end["barTop"],
                f"btn={end['btnBottom']} bar={end['barTop']} h={end['barH']}")

            # تغيّر المبلغ يعيد القفزة
            await pg.evaluate("()=>window.__pick(1,3)"); await pg.wait_for_timeout(120)
            again=await pg.evaluate("()=>document.getElementById('cartOff').classList.contains('pop')")
            if vh==700: rec("تغيّر المبلغ يعيد القفزة", again, "")
            if vh==700: await pg.screenshot(path=f"{_H.SHOTS}/15-cart-off.png")
            await ctx.close()
        await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
