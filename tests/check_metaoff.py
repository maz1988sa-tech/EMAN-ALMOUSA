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
M="""()=>{const cards=[...document.querySelectorAll('#svcRail .svc')];
 return cards.map(c=>{const m=c.querySelector('.meta'), o=c.querySelector('.meta-off');
  const body=c.querySelector('.svc-body');
  return {name:c.querySelector('h2').textContent.trim(), has:!!o, txt:o?o.innerText.trim():'',
    size:o?getComputedStyle(o).fontSize:'', color:o?getComputedStyle(o).color:'',
    inside: o? (o.getBoundingClientRect().right<=m.getBoundingClientRect().right+0.5 &&
                o.getBoundingClientRect().left >=m.getBoundingClientRect().left -0.5):true,
    ovf: Math.max(0, body.scrollHeight-body.clientHeight)};});}"""
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
    for vw,vh in ((360,640),(390,700),(430,932)):
      ctx=await b.new_context(viewport={"width":vw,"height":vh},has_touch=True,is_mobile=True,device_scale_factor=2)
      await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript",body=MOCK)))
      pg=await ctx.new_page(); errs=[]; pg.on("pageerror",lambda e:errs.append(str(e)))
      await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1500)
      await pg.evaluate("window.__goto(1)"); await pg.wait_for_timeout(800)
      cards=await pg.evaluate(M)
      ev=[c for c in cards if "سهرة" in c["name"]]
      br=[c for c in cards if "عروس" in c["name"]]
      rec(f"[{vw}] السهرة تحمل الوسم", bool(ev) and ev[0]["has"] and "خصم المجموعات" in ev[0]["txt"], ev[0]["txt"] if ev else "—")
      rec(f"[{vw}] العرائس بلا وسم", bool(br) and not br[0]["has"])
      rec(f"[{vw}] الوسم داخل السطر والبطاقة لا تفيض",
          all(c["inside"] and c["ovf"]==0 for c in cards),
          f"ovf={[c['ovf'] for c in cards]}")
      if vw==430:
        rec("بلون الهوية وبحجم 12", ev[0]["size"]=="12px" and "230, 194, 177" in ev[0]["color"],
            f"{ev[0]['size']} {ev[0]['color']}")
        # لو صُفّر مبلغ الخصم في الإعدادات اختفى الوسم
        gone=await pg.evaluate("""()=>{window.__setDisc(0); return [...document.querySelectorAll('.meta-off')].length;}""")
        rec("يختفي إذا صُفّر مبلغ الخصم", gone==0, f"عدد={gone}")
        await pg.evaluate("()=>window.__setDisc(100)"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f"{_H.SHOTS}/21-metaoff.png")
      rec(f"[{vw}] بلا أخطاء", not errs, "; ".join(errs[:2]))
      await ctx.close()
    await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
