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

async def tab(pg, rx):
    await pg.evaluate(f"()=>{{const t=[...document.querySelectorAll('[data-tab]')].find(e=>/{rx}/.test(e.textContent)); if(t) t.click();}}")
    await pg.wait_for_timeout(1100)

async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
    ctx=await b.new_context(viewport={"width":430,"height":932},device_scale_factor=2)
    await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript",body=MOCK)))
    pg=await ctx.new_page(); errs=[]; pg.on("pageerror",lambda e:errs.append(str(e)))
    await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
    await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(1700)

    # ٧ + ١٥ تقرير الدخل وملخّص الخدمات
    rep = await pg.evaluate("()=>{const t=document.body.innerText;return {inc:/دخل هذا الشهر/.test(t), per:/الدخل حسب الخدمة/.test(t), bars:document.querySelectorAll('.bar').length};}")
    rec("٧ تقرير الدخل في الرئيسية", rep["inc"] and rep["bars"]>=2, f"أشرطة={rep['bars']}")
    rec("١٥ ملخّص الدخل لكل خدمة", rep["per"])
    await pg.screenshot(path=f"{_H.SHOTS}/26-home.png", full_page=True)

    # ٤ التقويم الشهري
    await tab(pg,"الأجندة")
    cal = await pg.evaluate("()=>({cells:document.querySelectorAll('.cal .cd:not(.blank)').length, dots:document.querySelectorAll('.cal .dots i').length, nav:document.querySelectorAll('[data-mv]').length})")
    rec("٤ التقويم الشهري بخلاياه ونقاطه", cal["cells"]>=28 and cal["nav"]==2, f"خلايا={cal['cells']} نقاط={cal['dots']}")
    if cal["dots"]:
        await pg.evaluate("()=>{const d=[...document.querySelectorAll('.cal .cd')].find(c=>c.querySelector('.dots i')); if(d) d.click();}")
        await pg.wait_for_timeout(800)
        sel = await pg.evaluate("()=>document.querySelectorAll('.cal .cd[aria-pressed=\"true\"]').length")
        rec("النقر على يوم يختاره", sel==1, f"مختار={sel}")
    await pg.screenshot(path=f"{_H.SHOTS}/26-agenda.png")

    # ٢ + ٣ + ٩ البحث والفلاتر والتصدير
    await tab(pg,"الحجوزات")
    m = await pg.evaluate("()=>({q:!!document.getElementById('q'), st:document.querySelectorAll('[data-st]').length, pr:document.querySelectorAll('[data-pr]').length, csv:!!document.getElementById('bxCsv'), n:document.querySelectorAll('[data-open]').length})")
    rec("٣ شرائح الحالة والفترة", m["st"]==6 and m["pr"]==4, f"حالة={m['st']} فترة={m['pr']}")
    rec("٩ زرّ تصدير المعروض", m["csv"])
    await pg.fill("#q","نورة"); await pg.wait_for_timeout(700)
    r1 = await pg.evaluate("()=>({n:document.querySelectorAll('[data-open]').length, v:document.getElementById('q').value, focus:document.activeElement.id})")
    rec("٢ البحث بالاسم يصفّي ويحتفظ بالتركيز", r1["v"]=="نورة" and r1["focus"]=="q", f"نتائج={r1['n']}")
    await pg.evaluate("()=>document.querySelector('[data-st=\"all\"]').click()"); await pg.wait_for_timeout(500)
    await pg.fill("#q","0555554444"); await pg.wait_for_timeout(700)
    r2 = await pg.evaluate("()=>({n:document.querySelectorAll('[data-open]').length, t:document.body.innerText})")
    rec("٢ البحث برقم الجوال يجد صاحبته", r2["n"]==1 and "ريم" in r2["t"], f"نتائج={r2['n']}")
    await pg.fill("#q",""); await pg.wait_for_timeout(600)
    await pg.evaluate("()=>document.querySelector('[data-st=\"off\"]').click()"); await pg.wait_for_timeout(700)
    off = await pg.evaluate("()=>document.body.innerText")
    rec("٣ الملغاة صارت تُرى", "ملغاة" in off)
    await pg.evaluate("()=>document.querySelector('[data-pr=\"range\"]').click()"); await pg.wait_for_timeout(600)
    rng = await pg.evaluate("()=>!!document.getElementById('f-from')")
    rec("٣ نطاق التاريخ يُظهر الحقلين", rng)
    await pg.screenshot(path=f"{_H.SHOTS}/26-browse.png")

    # ١ تعديل الحجز
    await pg.evaluate("()=>document.querySelector('[data-st=\"all\"]').click()"); await pg.wait_for_timeout(700)
    await pg.evaluate("()=>document.querySelector('[data-open]').click()"); await pg.wait_for_timeout(900)
    hasEdit = await pg.evaluate("()=>!!document.getElementById('d-edit')")
    rec("١ زرّ تعديل الحجز موجود", hasEdit)
    if hasEdit:
        await pg.click("#d-edit"); await pg.wait_for_timeout(800)
        f = await pg.evaluate("()=>({n:!!document.getElementById('e-name'), d:!!document.getElementById('e-date'), t:!!document.getElementById('e-time'), m:!!document.getElementById('e-map'), st:document.querySelectorAll('[data-ed]').length, sum:document.getElementById('e-sum').innerText})")
        rec("١ نموذج التعديل كامل (اسم/تاريخ/وقت/خريطة/خدمات)",
            f["n"] and f["d"] and f["t"] and f["m"] and f["st"]>=2, f"عدّادات={f['st']} إجمالي={f['sum']}")
        await pg.evaluate("()=>document.querySelector('[data-ed=\"+\"]').click()"); await pg.wait_for_timeout(300)
        s2 = await pg.evaluate("()=>document.getElementById('e-sum').innerText")
        rec("١ الإجمالي يُعاد حسابه مع العدّاد", s2 != f["sum"], f"{f['sum']} → {s2}")
        await pg.screenshot(path=f"{_H.SHOTS}/26-edit.png")
        await pg.click("#e-back"); await pg.wait_for_timeout(700)

    # ٦ + ١٠ الحجز اليدوي
    await tab(pg,"الرئيسية")
    await pg.evaluate("()=>document.getElementById('btnNew').click()"); await pg.wait_for_timeout(800)
    # صار الزرّ يسأل: فردٌ أم مجموعة؟ فنمضي إلى الفرديّة.
    if await pg.evaluate("()=>!!document.getElementById('k-one')"):
        await pg.click("#k-one"); await pg.wait_for_timeout(800)
    nb = await pg.evaluate("()=>({st:document.querySelectorAll('[data-nd]').length, map:!!document.getElementById('n-map'), dur:document.getElementById('n-dur').innerText})")
    rec("٦ الحجز اليدوي بعدّادات جماعية", nb["st"]>=2, f"عدّادات={nb['st']}")
    rec("١٠ حقل رابط الخريطة", nb["map"])
    await pg.evaluate("()=>{document.querySelectorAll('[data-nd=\"+\"]')[0].click();document.querySelectorAll('[data-nd=\"+\"]')[0].click();}")
    await pg.wait_for_timeout(400)
    nd = await pg.evaluate("()=>({sum:document.getElementById('n-sum').innerText, dur:document.getElementById('n-dur').innerText})")
    rec("٦ الإجمالي والمدة ووقت الانتهاء", "ر.س" in nd["sum"] and "ينتهي" in nd["dur"], f"{nd['sum']} · {nd['dur']}")
    await pg.screenshot(path=f"{_H.SHOTS}/26-new.png")

    rec("بلا أخطاء", not errs, "; ".join(errs[:2]))
    await ctx.close(); await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
