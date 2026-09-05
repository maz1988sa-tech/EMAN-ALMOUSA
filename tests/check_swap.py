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
ORDER="""()=>{const f=document.querySelector('#svcRail .svc.active .pick');
 const q=f.querySelector('.pick-qty');
 const m=q.querySelector('.q-minus').getBoundingClientRect();
 const p=q.querySelector('.q-plus').getBoundingClientRect();
 const v=q.querySelector('.q-val').getBoundingClientRect();
 const off=document.getElementById('cartOff');
 return {plusLeftOfMinus: p.left < m.left, valBetween: v.left>Math.min(p.left,m.left) && v.right<Math.max(p.right,m.right),
   offSize: off?getComputedStyle(off).fontSize:'', offTxt: off?off.innerText.trim():''};}"""
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
    for vw,vh in ((360,640),(390,700),(430,932)):
      ctx=await b.new_context(viewport={"width":vw,"height":vh},has_touch=True,is_mobile=True,device_scale_factor=2)
      await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript",body=MOCK)))
      pg=await ctx.new_page(); await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1500)
      await pg.evaluate("window.__goto(1)"); await pg.wait_for_timeout(800)
      await pg.evaluate("()=>window.__svc(1)"); await pg.wait_for_timeout(800)
      await pg.click("#svcRail .svc.active .pick-main"); await pg.wait_for_timeout(700)
      await pg.click("#svcRail .svc.active .q-plus"); await pg.wait_for_timeout(400)
      await pg.click("#svcRail .svc.active .q-plus"); await pg.wait_for_timeout(600)
      m=await pg.evaluate(ORDER)
      rec(f"[{vw}] + على اليسار و− على اليمين", m["plusLeftOfMinus"])
      rec(f"[{vw}] الرقم بين الزرّين", m["valBetween"])
      n=await pg.evaluate("()=>document.querySelector('#svcRail .svc.active .q-val').textContent")
      rec(f"[{vw}] + ما زال يزيد و− ينقص", n=="3", f"n={n}")
      await pg.click("#svcRail .svc.active .q-minus"); await pg.wait_for_timeout(450)
      n2=await pg.evaluate("()=>document.querySelector('#svcRail .svc.active .q-val').textContent")
      rec(f"[{vw}] − ينقص", n2=="2", f"n={n2}")
      rec(f"[{vw}] سطر الخصم 17px", m["offSize"]=="17px", f"{m['offSize']} {m['offTxt']!r}")
      # الشريط لا يغطّي إطار الحجز
      cov=await pg.evaluate("""()=>{const b=document.querySelector('#svcRail .svc.active .pick').getBoundingClientRect();
        const c=document.getElementById('svcCart').getBoundingClientRect();
        return Math.round(b.bottom - c.top);}""")
      rec(f"[{vw}] الشريط لا يغطّي الإطار", cov<=0, f"تداخل={cov}px")
      if vw==430: await pg.screenshot(path=f"{_H.SHOTS}/19-swap.png")
      await ctx.close()
    await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
