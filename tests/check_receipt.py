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

PNG=("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

async def toPay(pg):
    await pg.evaluate("()=>{window.__pick(1,3); window.__goto(2);}"); await pg.wait_for_timeout(1100)
    await pg.evaluate("()=>{const x=[...document.querySelectorAll('#week button.day:not([disabled])')]; if(x.length) x[x.length>2?2:0].click();}")
    await pg.wait_for_timeout(900)
    await pg.evaluate("()=>{const t=[...document.querySelectorAll('#times [data-slot]')]; if(t.length) t[0].click();}")
    await pg.wait_for_timeout(600)
    await pg.click("#confirmBtn"); await pg.wait_for_timeout(700)
    await pg.fill("#nm","نورة"); await pg.fill("#ph","0501234567"); await pg.fill("#locTxt","حي النخيل")
    await pg.wait_for_timeout(250)
    await pg.click("#toPay"); await pg.wait_for_timeout(700)

async def attach(pg):
    await pg.set_input_files("#rcptFile", {"name":"receipt.png","mimeType":"image/png",
                                           "buffer": __import__('base64').b64decode(PNG)})
    await pg.wait_for_timeout(900)

ST = """()=>({txt:document.getElementById('rcptChk').innerText.trim(),
  cls:document.getElementById('rcptChk').className,
  hid:document.getElementById('rcptChk').hidden,
  sendDis:document.getElementById('sendBooking').disabled,
  amt:document.getElementById('payAmt').innerText.trim(),
  over:(()=>{const b=document.getElementById('sheetBody');return b.scrollHeight-b.clientHeight;})()})"""

async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
    # الحكم لم يعد يُحسب في المتصفّح: صار من القاعدة (receipt_state). فما
    # يُفحص هنا هو ما يفعله المتصفّح بالحكم، لا كيف يبلغه. وتفاصيل الحكم
    # نفسه — الآيبان والمبلغ وصمت الرفض — في check_receipt2.
    cases = [
      ("الفحص مطفأ: أي صورة تمرّ", False, {"ok":True}, "ok", False, None),
      ("حكمها «مقبول» ⇒ الإرسال مفتوح", True, {"ok":True}, "ok", False, "تم التحقق"),
      ("حكمها «مرفوض» ⇒ الإرسال مقفل", True, {"ok":True}, "bad", True, None),
      ("القراءة تعطّلت: لا نمنع من المتصفّح", True,
       {"ok":False,"reason":"ocr_failed"}, "wait", False, "تم رفع الإيصال"),
    ]
    for title, guard, reply, verdict, expectBlocked, expectTxt in cases:
      ctx=await b.new_context(viewport={"width":390,"height":760},has_touch=True,is_mobile=True,device_scale_factor=2)
      await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript",body=MOCK)))
      pg=await ctx.new_page(); errs=[]; pg.on("pageerror",lambda e:errs.append(str(e)))
      await pg.add_init_script(
          f"window.__ocrReply = {__import__('json').dumps(reply)};"
          f"window.__RECEIPT__ = {verdict!r};")
      await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1500)
      if guard:
          await pg.evaluate("()=>{window.__state().settings.receipt_ocr_required = true;}")
      await toPay(pg); await attach(pg)
      m=await pg.evaluate(ST)
      rec(title, m["sendDis"]==expectBlocked and (expectTxt is None or expectTxt in m["txt"]),
          f"زر={'معطّل' if m['sendDis'] else 'مفعّل'} نص={m['txt']!r}")
      if title.startswith("حكمها «مقبول»"):
          rec("العربون مجموع الخدمات = 450", m["amt"].replace(",","").startswith("450"), m["amt"])
          rec("اللوحة تتّسع مع سطر الفحص", m["over"]<=0, f"over={m['over']}")
      rec(f"بلا أخطاء — {title}", not errs, "; ".join(errs[:1]))
      await ctx.close()
    await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
