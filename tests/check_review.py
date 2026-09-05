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
CASES=[(1,3),(2,2),(1,1),(0,1)]
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
        bad=0
        for vh in (620, 660, 700, 760, 820, 932):
            ctx=await b.new_context(viewport={"width":430,"height":vh},has_touch=True,is_mobile=True,device_scale_factor=2)
            await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript",body=MOCK)))
            pg=await ctx.new_page(); await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1600)
            out=[]
            for br,ev in CASES:
                await pg.evaluate(f"()=>{{window.__pick(0,{br}); window.__pick(1,{ev});}}"); await pg.wait_for_timeout(400)
                if not out:
                    await pg.click("#cartGo"); await pg.wait_for_timeout(1300)
                    await pg.eval_on_selector("#week .day:not(.blank):not([disabled])","e=>e.click()"); await pg.wait_for_timeout(1100)
                    await pg.eval_on_selector("#times button:not([disabled])","e=>e.click()"); await pg.wait_for_timeout(400)
                    await pg.click("#toConfirm"); await pg.wait_for_timeout(1000)
                else:
                    await pg.evaluate("window.__goto(3)"); await pg.wait_for_timeout(700)
                m=await pg.evaluate("""()=>{const pad=document.querySelector('#deck .screen:nth-child(4) .pad');
                  const st=pad.querySelector('.stack');const a=document.getElementById('sumThumb');
                  const r=a.getBoundingClientRect();const k=[...a.children].map(e=>e.getBoundingClientRect());
                  return {clip:Math.round(st.scrollHeight-st.clientHeight),
                          outX:Math.round(Math.max(...k.map(x=>x.right))-r.right),
                          w:Math.round(k[0].width)};}""")
                flag = "" if (m['clip']<=0 and m['outX']<=0) else "  ✗"
                if flag: bad+=1
                out.append(f"{br}ع+{ev}س: قص={m['clip']} خارج={m['outX']} عرض={m['w']}{flag}")
            print(f"vh={vh}  " + " | ".join(out))
            if vh==700: await pg.screenshot(path=f"{_H.SHOTS}/review-bigger.png")
            await ctx.close()
        await b.close()
        print("\nمشاكل:", bad)
        sys.exit(1 if bad else 0)
asyncio.run(main())
