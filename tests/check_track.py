# -*- coding: utf-8 -*-
"""صفحة متابعة الحجز — «بطاقة الموعد» (التصميم أ المعتمد، ٩ نوفمبر ٢٠٢٦).

تُقاس هندسةُ الصفحة لا مصدرُها: خانات الدفع متساوية، وأزرار الأيقونات
مربّعةٌ بحجمٍ واحد، وللأيقونة اسمٌ يقرؤه قارئ الشاشة، ولا يفيض الجوال
أفقيًّا، والحالات الأربع (مؤكّد بعربون، قيد المراجعة، منجَز، طلب إلغاء)
تُرسم، وطلب الإلغاء ما زال يعمل.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright

ROOT = str(_H.ROOT)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
MOCK = open(os.path.join(ROOT, "dev/mock-supabase.js"), encoding="utf-8").read()

ok = fail = 0
def rec(n, c, x=""):
    global ok, fail
    if c: ok += 1;   print(f"PASS {n}" + (f" — {x}" if x else ""))
    else: fail += 1; print(f"FAIL {n} — {x}")

GEO = """()=>{
  const q=s=>[...document.querySelectorAll('#trackView '+s)];
  const box=e=>{const r=e.getBoundingClientRect();return [Math.round(r.width),Math.round(r.height)]};
  const strip=q('.tk-strip > div').map(box);
  const acts=q('.tk-acts > *').map(box);
  const ib=q('.tk-ib').map(e=>({w:box(e)[0],h:box(e)[1],name:e.getAttribute('aria-label'),title:e.getAttribute('title')}));
  const txt=document.getElementById('trackView').innerText.replace(/\\s+/g,' ');
  return {strip,acts,ib,txt,
    over:document.documentElement.scrollWidth>innerWidth+1,
    h2:(q('h2')[0]||{}).innerText, day:(q('.tk-day b')[0]||{}).innerText,
    pill:(q('.t-pill')[0]||{}).innerText,
    qty:q('.qty').map(e=>e.innerText.trim())};}"""

async def main():
  async with async_playwright() as p:
    b = await p.chromium.launch(**_H.CHROME, args=["--no-sandbox"])
    async def open_tok(tok, w=390):
        ctx = await b.new_context(viewport={"width": w, "height": 844}, device_scale_factor=2,
                                  has_touch=True, is_mobile=(w < 700))
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html?t={tok}"); await pg.wait_for_timeout(2000)
        return ctx, pg, errs

    # ١) مؤكَّد بعربون
    ctx, pg, errs = await open_tok("tok-1")
    g = await pg.evaluate(GEO)
    rec("مؤكَّد: العنوان «موعدك مؤكّد»", g["h2"] == "موعدك مؤكّد", g["h2"])
    rec("خانات الدفع ثلاث", len(g["strip"]) == 3, str(g["strip"]))
    ws = {s[0] for s in g["strip"]}; hs = {s[1] for s in g["strip"]}
    rec("وبعرضٍ واحد وارتفاعٍ واحد", max(ws) - min(ws) <= 1 and len(hs) == 1, f"{g['strip']}")
    rec("المتبقي يظهر مع العربون", "المتبقي" in g["txt"] and "العربون المستلم" in g["txt"], "")
    rec("أزرار الأيقونات مربّعة بحجمٍ واحد",
        len(g["ib"]) == 2 and all(i["w"] == 46 and i["h"] == 46 for i in g["ib"]), str(g["ib"]))
    rec("لكل أيقونة اسمٌ وتلميح",
        all(i["name"] and i["title"] for i in g["ib"]) and
        {i["name"] for i in g["ib"]} == {"طلب إلغاء الحجز", "حجز موعد جديد"}, str(g["ib"]))
    rec("وارتفاع زرّ التواصل يطابقها", len({a[1] for a in g["acts"]}) == 1, str(g["acts"]))
    rec("لا فيض أفقيّ على الجوال", not g["over"], "")
    await pg.screenshot(path=f"{_H.SHOTS}/track-confirmed.png", full_page=True)
    rec("بلا أخطاء (مؤكَّد)", not errs, "; ".join(errs[:2]))
    await ctx.close()

    # ٢) قيد المراجعة بلا عربون: «بانتظار التأكيد»، وخانتان فقط، وبنود بعددها
    ctx, pg, errs = await open_tok("tok-3")
    g = await pg.evaluate(GEO)
    rec("قيد المراجعة: العنوان", g["h2"] == "طلبك قيد المراجعة", g["h2"])
    rec("«بانتظار التأكيد» لا «لم يُستلم»", "بانتظار التأكيد" in g["txt"] and "لم يُستلم" not in g["txt"], "")
    rec("خانتان لأنّ المتبقي لا يُحسب قبل العربون", len(g["strip"]) == 2, str(g["strip"]))
    rec("الخانتان بعرضٍ واحد", abs(g["strip"][0][0] - g["strip"][1][0]) <= 1, str(g["strip"]))
    rec("البند بعدده وسعر وحدته", "2 × 600" in g["txt"] and any("2 × 600" in q for q in g["qty"]), str(g["qty"]))
    rec("وأسماء من طلبنها", "لمى" in g["txt"] and "هند" in g["txt"], "")
    rec("بلا أخطاء (قيد المراجعة)", not errs, "; ".join(errs[:2]))
    await pg.screenshot(path=f"{_H.SHOTS}/track-pending.png", full_page=True)
    # طلب الإلغاء ما زال يعمل
    await pg.evaluate("()=>document.getElementById('askCancel').click()")
    await pg.wait_for_timeout(1200)
    rec("زرّ الإلغاء يعمل ويُعاد الرسم", await pg.evaluate("()=>!!document.getElementById('trackView').innerText"), "")
    await ctx.close()

    # ٣) منجَز: لا زرّ إلغاء، وزرّ الحجز الجديد باقٍ
    ctx, pg, errs = await open_tok("tok-2")
    g = await pg.evaluate(GEO)
    rec("منجَز: لا زرّ إلغاء", len(g["ib"]) == 1 and g["ib"][0]["name"] == "حجز موعد جديد", str(g["ib"]))
    rec("ويظهر «مسدّد بالكامل» أو المتبقي", "المتبقي" in g["txt"], "")
    rec("بلا أخطاء (منجَز)", not errs, "; ".join(errs[:2]))
    await ctx.close()

    # ٤) طلب إلغاء قائم: الرسالة تظهر ولا زرّ إلغاء
    ctx, pg, errs = await open_tok("tok-4")
    g = await pg.evaluate(GEO)
    rec("طلب إلغاء قائم: رسالة الاستلام", "وصلنا طلب الإلغاء" in g["txt"], "")
    rec("ولا زرّ إلغاء ثانٍ", all(i["name"] != "طلب إلغاء الحجز" for i in g["ib"]), str(g["ib"]))
    await ctx.close()

    # ٥) جهازٌ لوحيّ وحاسوب: لا فيض ولا تمدّد مشوّه
    for w in (768, 1280):
        ctx, pg, errs = await open_tok("tok-1", w)
        g = await pg.evaluate(GEO)
        rec(f"عرض {w}: لا فيض أفقيّ", not g["over"], "")
        rec(f"عرض {w}: خانات الدفع متساوية", max(s[0] for s in g["strip"]) - min(s[0] for s in g["strip"]) <= 1, str(g["strip"]))
        await ctx.close()
    await b.close()

asyncio.run(main())
print(f"\n=== {ok}/{ok+fail} passed ===")
sys.exit(1 if fail else 0)
