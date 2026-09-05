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

async def openForm(pg):
    await pg.evaluate("()=>{window.__pick(1,3); window.__goto(2);}"); await pg.wait_for_timeout(1100)
    await pg.evaluate("()=>{const b=[...document.querySelectorAll('#week button.day:not([disabled])')]; if(b.length) b[b.length>2?2:0].click();}")
    await pg.wait_for_timeout(900)
    await pg.evaluate("()=>{const t=[...document.querySelectorAll('#times [data-slot]')]; if(t.length) t[0].click();}")
    await pg.wait_for_timeout(600)
    await pg.click("#confirmBtn"); await pg.wait_for_timeout(800)

FIT = """()=>{const b=document.getElementById('sheetBody');
  // النقطة المخفيّة (الموقع حين لا يكون إلزاميًّا) عقدةٌ قائمة لا تُرى،
  // فتُعدّ المرئيّة وحدها.
  const dots=[...document.querySelectorAll('.field label .req')]
    .filter(e=>getComputedStyle(e).display!=='none');
  const lab=getComputedStyle(document.querySelector('label[for=nm]')).fontSize;
  return {over: b.scrollHeight-b.clientHeight, dots: dots.length,
    dotColor: dots.length?getComputedStyle(dots[0]).backgroundColor:'',
    people: !!document.getElementById('peopleFields'),
    labelSize: lab,
    reqOn: ['nm','ph','locTxt'].map(i=>document.getElementById(i).required)};}"""

async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
    for vw,vh in ((360,620),(390,660),(390,700),(414,780),(430,932)):
      ctx=await b.new_context(viewport={"width":vw,"height":vh},has_touch=True,is_mobile=True,device_scale_factor=2)
      await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript",body=MOCK)))
      pg=await ctx.new_page(); errs=[]; pg.on("pageerror",lambda e:errs.append(str(e)))
      await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1500)
      await openForm(pg)
      m=await pg.evaluate(FIT)
      rec(f"[{vw}x{vh}] اللوحة تكتمل بلا سحب", m["over"]<=0, f"over={m['over']}")
      if vw==430:
        rec("صندوق أسماء المجموعة محذوف", not m["people"])
        rec("ثلاث نقاط حمراء على الإلزامي (والموقع اختياري)",
            m["dots"]==3 and "192, 69, 58" in m["dotColor"], f"{m['dots']} {m['dotColor']}")
        rec("العناوين أكبر (11.5px)", m["labelSize"]=="11.5px", m["labelSize"])
        rec("required على الحقول الثلاثة", all(m["reqOn"]), str(m["reqOn"]))

        # البوابة: لا استمرار بلا اسم/جوال/حي
        st=[]
        async def dis(): return await pg.evaluate("()=>document.getElementById('toPay').disabled")
        st.append(("فارغ", await dis()))
        await pg.fill("#nm","نورة العتيبي"); await pg.wait_for_timeout(150); st.append(("اسم فقط", await dis()))
        await pg.fill("#ph","٠٥٠١٢٣٤٥٦٧"); await pg.wait_for_timeout(200)
        v=await pg.input_value("#ph")
        rec("الأرقام العربية تُوحَّد فورًا", v=="0501234567", f"القيمة={v!r}")
        st.append(("بلا حي", await dis()))
        await pg.fill("#locTxt","حي النخيل، الرياض"); await pg.wait_for_timeout(200)
        st.append(("مكتمل", await dis()))
        rec("لا استمرار إلا باكتمال الثلاثة",
            st[0][1] and st[1][1] and st[2][1] and not st[3][1], str(st))
        # صيغ إدخال أخرى
        for raw,want in (("+966501234567","0501234567"),("٩٦٦٥٠١٢٣٤٥٦٧","0501234567"),
                         ("00966 50 123 4567","0501234567"),("۰۵۰۱۲۳۴۵۶۷","0501234567")):
          await pg.fill("#ph",raw); await pg.wait_for_timeout(180)
          got=await pg.input_value("#ph")
          rec(f"توحيد {raw}", got==want, f"→{got!r}")
        # الحي فارغ بعد مغادرته يُعلَّم أحمر
        await pg.fill("#locTxt",""); await pg.evaluate("()=>document.getElementById('locTxt').blur()"); await pg.wait_for_timeout(250)
        bad=await pg.evaluate("()=>document.getElementById('locTxt').closest('.field').classList.contains('bad')")
        rec("الحي الفارغ يُعلَّم أحمر بعد المغادرة", bad)
        await pg.fill("#locTxt","حي النخيل"); await pg.wait_for_timeout(200)
        await pg.screenshot(path=f"{_H.SHOTS}/18-form.png")
        # نصّ لوحة العربون
        await pg.click("#toPay"); await pg.wait_for_timeout(700)
        t=await pg.evaluate("()=>document.querySelector('.pane[data-pane=pay] .sub-line').textContent.trim()")
        rec("نصّ لوحة العربون الجديد", t.startswith("عزيزتي العميلة، لتأكيد الحجز"), t)
        po=await pg.evaluate("()=>{const b=document.getElementById('sheetBody');return b.scrollHeight-b.clientHeight;}")
        rec("لوحة العربون تكتمل", po<=0, f"over={po}")
        await pg.screenshot(path=f"{_H.SHOTS}/18-pay.png")
      rec(f"[{vw}x{vh}] بلا أخطاء", not errs, "; ".join(errs[:2]))
      await ctx.close()
    await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
