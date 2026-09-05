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
        for vw,vh in ((360,640),(390,700),(430,700),(430,932)):
            ctx=await b.new_context(viewport={"width":vw,"height":vh},has_touch=True,is_mobile=True,device_scale_factor=2)
            await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript",body=MOCK)))
            pg=await ctx.new_page(); await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1600)
            await pg.evaluate("window.__goto(1)"); await pg.wait_for_timeout(900)
            for picked in (0,1):
                if picked: 
                    await pg.evaluate("()=>window.__pick(0,1)"); await pg.wait_for_timeout(500)
                m=await pg.evaluate("""()=>{const card=document.querySelector('#svcRail .svc.active');
                  const inner=card.querySelector('.svc-inner');const body=card.querySelector('.svc-body');
                  const sw=card.querySelector('.svc-swipe');const cs=sw?getComputedStyle(sw):null;
                  const cardR=card.getBoundingClientRect();
                  const kids=[...body.children].filter(e=>e.offsetParent!==null);
                  const bottom=Math.max(...kids.map(e=>e.getBoundingClientRect().bottom));
                  return {size:cs?cs.fontSize:'-', lines: sw? Math.round(sw.getBoundingClientRect().height/parseFloat(cs.lineHeight||'20')) : 0,
                          swH: sw?Math.round(sw.getBoundingClientRect().height):0,
                          overflowBottom: Math.round(bottom - cardR.bottom),
                          bodyClip: body.scrollHeight - body.clientHeight};}""")
                st = "مختارة" if picked else "دعوة"
                rec(f"[{vw}x{vh}] {st}: البطاقة لا تفيض", m["overflowBottom"]<=0 and m["bodyClip"]<=0,
                    f"asfal={m['overflowBottom']} clip={m['bodyClip']} swipe={m['size']} h={m['swH']}")
            if (vw,vh)==(430,700): await pg.screenshot(path=f"{_H.SHOTS}/17-svc-card.png")
            await ctx.close()
        await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
