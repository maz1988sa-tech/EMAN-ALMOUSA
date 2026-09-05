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

MEAS = """()=>{const c=document.querySelector('#svcRail .svc.active');
 const f=c.querySelector('.pick'), l=f.querySelector('.lbl'), q=f.querySelector('.pick-qty');
 const val=q.querySelector('.q-val'), plus=f.querySelector('.i-plus');
 const vis=e=>{const r=e.getBoundingClientRect();const s=getComputedStyle(e);
   return s.display!=='none'&&s.visibility!=='hidden'&&+s.opacity>.5&&r.width>4;};
 const fr=f.getBoundingClientRect(), qr=q.getBoundingClientRect(), lr=l.getBoundingClientRect();
 const body=c.querySelector('.svc-body');
 return {label:l.innerText.trim(), on:f.classList.contains('on'),
   qtyVis:vis(q), n:val.textContent.trim(), plusVis:vis(plus),
   qtyInside: qr.left>=fr.left-0.5 && qr.right<=fr.right+0.5 && qr.top>=fr.top-0.5 && qr.bottom<=fr.bottom+0.5,
   labelClipped: l.scrollWidth>l.clientWidth+1,
   overlap: vis(q) ? lr.left < qr.right-0.5 : false,
   frameH: Math.round(fr.height), fontSize: getComputedStyle(l).fontSize,
   sepBox: !!c.querySelector('.qty-row'),
   cardOverflow: Math.max(0, body.scrollHeight-body.clientHeight),
   cart: (document.querySelector('#svcCart b')||{}).textContent||''};}"""

async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
    for vw,vh in ((360,640),(390,700),(430,700),(430,932)):
      ctx=await b.new_context(viewport={"width":vw,"height":vh},has_touch=True,is_mobile=True,device_scale_factor=2)
      await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript",body=MOCK)))
      pg=await ctx.new_page(); await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1600)
      await pg.evaluate("window.__goto(1)"); await pg.wait_for_timeout(900)

      for si,label in ((0,"العرائس"),(1,"السهرة")):
        if si: 
          await pg.evaluate("()=>window.__svc(1)"); await pg.wait_for_timeout(800)
        m=await pg.evaluate(MEAS)
        rec(f"[{vw}] {label} قبل الاختيار: لا عدّاد ظاهر و+ موجودة",
            (not m["qtyVis"]) and m["plusVis"] and m["label"]=="احجزي هذه الخدمة" and not m["sepBox"], m["label"])
        await pg.click("#svcRail .svc.active .pick-main"); await pg.wait_for_timeout(650)
        m=await pg.evaluate(MEAS)
        rec(f"[{vw}] {label} بعد الضغط: الرقم ١ داخل نفس الإطار",
            m["on"] and m["qtyVis"] and m["n"]=="1" and m["qtyInside"] and not m["plusVis"], f"n={m['n']} h={m['frameH']}")
        rec(f"[{vw}] {label} لا تداخل ولا قصّ للنص", (not m["overlap"]) and (not m["labelClipped"]) and m["cardOverflow"]==0,
            f"clip={m['labelClipped']} ovf={m['cardOverflow']}")
        await pg.click("#svcRail .svc.active .q-plus"); await pg.wait_for_timeout(450)
        m=await pg.evaluate(MEAS)
        rec(f"[{vw}] {label} + يزيد العدد داخل الإطار", m["n"]=="2" and m["qtyInside"], f"n={m['n']} cart={m['cart']}")
        await pg.click("#svcRail .svc.active .q-minus"); await pg.wait_for_timeout(400)
        await pg.click("#svcRail .svc.active .q-minus"); await pg.wait_for_timeout(650)
        m=await pg.evaluate(MEAS)
        rec(f"[{vw}] {label} − عند ١ يلغي ويعيد الدعوة",
            (not m["on"]) and (not m["qtyVis"]) and m["label"]=="احجزي هذه الخدمة", m["label"])
      if vw==430 and vh==932:
        await pg.click("#svcRail .svc.active .pick-main"); await pg.wait_for_timeout(700)
        await pg.screenshot(path=f"{_H.SHOTS}/17-merge-on.png")
      await ctx.close()
    await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
