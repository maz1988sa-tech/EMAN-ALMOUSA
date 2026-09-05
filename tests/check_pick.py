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
MEAS = """()=>{const b=document.querySelector('#svcRail .svc.active .pick');
  const l=b.querySelector('.lbl');const cs=getComputedStyle(l);
  const plus=b.querySelector('.i-plus'), chk=b.querySelector('.i-check');
  const vis=e=>e&&getComputedStyle(e).display!=='none';
  const br=b.getBoundingClientRect(), lr=l.getBoundingClientRect();
  return {size:cs.fontSize, txt:l.innerText.trim(),
          clipped: l.scrollWidth > l.clientWidth + 1,
          insideX: lr.left>=br.left-0.5 && lr.right<=br.right+0.5,
          insideY: lr.top>=br.top-0.5 && lr.bottom<=br.bottom+0.5,
          plus:vis(plus), check:vis(chk),
          qty:(()=>{const w=b.closest('.pick-wrap')||b.parentElement;
                    const q=w&&w.querySelector('.pick-qty');
                    return !!q&&getComputedStyle(q).display!=='none'&&
                           q.getBoundingClientRect().width>0;})(),
          plusW: plus?Math.round(plus.getBoundingClientRect().width):0,
          btnH: Math.round(br.height)};}"""
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
        for vw,vh in ((360,640),(390,700),(430,700),(598,900)):
            ctx=await b.new_context(viewport={"width":vw,"height":vh},has_touch=True,is_mobile=True,device_scale_factor=2)
            await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript",body=MOCK)))
            pg=await ctx.new_page(); await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1600)
            await pg.evaluate("window.__goto(1)"); await pg.wait_for_timeout(900)
            m=await pg.evaluate(MEAS)
            rec(f"[{vw}] الدعوة: نص كامل داخل الزر", (not m["clipped"]) and m["insideX"] and m["insideY"], f"{m['txt']!r} {m['size']} h={m['btnH']}")
            if vw==430:
                rec("العلامة + ظاهرة وكبيرة", m["plus"] and not m["check"] and m["plusW"]>=22, f"plus={m['plusW']}px")
                rec("حجم الخط 16px", m["size"]=="16px", m["size"])
            await pg.evaluate("()=>window.__pick(0,1)"); await pg.wait_for_timeout(500)
            m2=await pg.evaluate(MEAS)
            rec(f"[{vw}] بعد الاختيار: نص كامل داخل الزر", (not m2["clipped"]) and m2["insideX"], f"{m2['txt']!r}")
            if vw==430:
                # لم تعد علامة صح: المختارة تفتح عدّاد الأشخاص مكان زرّ الإضافة.
                rec("بعد الاختيار: عدّاد الأشخاص بدل +", m2["qty"] and not m2["plus"],
                    f'qty={m2["qty"]} plus={m2["plus"]}')
                await pg.screenshot(path=f"{_H.SHOTS}/16-pick-picked.png")
                await pg.evaluate("()=>window.__pick(0,0)"); await pg.wait_for_timeout(500)
                await pg.screenshot(path=f"{_H.SHOTS}/16-pick.png")
            await ctx.close()
        await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
