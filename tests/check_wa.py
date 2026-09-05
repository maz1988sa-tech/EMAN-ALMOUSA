# -*- coding: utf-8 -*-
"""قناة واتساب في اللوحة — القالب المعتمد وزرّ التجربة.

الخطر هنا أنّ ما تنسخه إيمان إلى ميتا لا يطابق ما تُرسله المنصّة: ترتيب
المتغيّرات مصدره القاعدة، ومعاينته في المتصفّح. فيُفحص أنّهما واحد، وأنّ
القالب لا يُطلب من رسالةٍ يدوية، وأنّ الاعتماد يسقط بلا اسم.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, sys, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright

ROOT = str(_H.ROOT)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
MOCK = open(os.path.join(ROOT, "dev/mock-supabase.js"), encoding="utf-8").read()
_OLD = "      upsert(v) { (window.__UPSERT = window.__UPSERT || []).push(v);"
assert _OLD in MOCK, "mock upsert shape changed"

# ما تقوله القاعدة عن ترتيب المتغيّرات — يُقارن بما يقوله المتصفّح
SQL_TRUTH = {
  "أهلاً {الاسم} 🌸\nتم تأكيد موعدك مع {الاسم التجاري}:\n\n📅 {التاريخ}\n🕐 {الوقت}\n💄 {الخدمة}\n💰 الإجمالي: {الإجمالي}\n✅ العربون المستلم: {العربون}\n⏳ المتبقي: {المتبقي}\n\nلمتابعة حجزك:\n{رابط الحجز}\n\nبانتظارك 💗":
    ["{الاسم}", "{الاسم التجاري}", "{التاريخ}", "{الوقت}", "{الخدمة}",
     "{الإجمالي}", "{العربون}", "{المتبقي}", "{رابط الحجز}"],
  "تذكير بموعدك غدًا مع {الاسم التجاري} 🌸\n\n📅 {التاريخ}\n🕐 {الوقت}\n📍 {الموقع}\nأرجو ارسال الموقع\nالمتبقي: {المتبقي}\n\nنراكِ غدًا 💗":
    ["{الاسم التجاري}", "{التاريخ}", "{الوقت}", "{الموقع}", "{المتبقي}"],
}

R = []
def rec(n, ok, note=""):
    R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

async def msgs_pane(pg):
    await pg.evaluate("()=>document.querySelector('[data-tab=\"settings\"]').click()")
    await pg.wait_for_timeout(1100)
    await pg.evaluate("()=>document.querySelector('[data-pane=\"msgs\"]').click()")
    await pg.wait_for_timeout(1200)

async def open_tpl(pg, rx):
    await pg.evaluate(f"""()=>{{const r=[...document.querySelectorAll('#tplList .rowline')]
      .find(x=>/{rx}/.test(x.textContent)); r.querySelector('[data-tpl]').click();}}""")
    await pg.wait_for_timeout(700)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(
            **_H.CHROME,
            args=["--no-sandbox"])

        # ══ الجولة الأولى: غير مربوطة ══
        ctx = await b.new_context(viewport={"width": 430, "height": 932}, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js",
                        lambda r: asyncio.ensure_future(r.fulfill(
                            content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
        await pg.goto(f"http://127.0.0.1:{PORT}/admin.html")
        await pg.wait_for_timeout(1700)
        await msgs_pane(pg)

        rec("غير مربوطة: لا زرّ تجربة",
            not await pg.evaluate("()=>!!document.getElementById('wa-send-test')"))

        # ── ترتيب المتغيّرات: المتصفّح = القاعدة
        # الوحدات تُستورد مباشرةً بدل زرع خطّافات فحصٍ في كود الإنتاج
        got = await pg.evaluate(
            "async(bodies)=>{const m=await import('/assets/db.js?v=37');"
            "return bodies.map(x=>m.waVars(x));}", list(SQL_TRUTH.keys()))
        for i, (body, want) in enumerate(SQL_TRUTH.items()):
            rec(f"ترتيب المتغيّرات كما في القاعدة ({i + 1})", got[i] == want,
                f"{got[i][:3]}…")

        tpl = await pg.evaluate(
            "async(bodies)=>{const m=await import('/assets/db.js?v=37');"
            "return bodies.map(x=>m.waTemplateText(x));}", list(SQL_TRUTH.keys()))
        rec("النصّ المولَّد يرقّم بالترتيب",
            tpl[0].startswith("أهلاً {{1}}") and "{{9}}" in tpl[0], tpl[0][:24])
        rec("ولا يبقى اسمٌ عربيّ في القالب",
            not any("{ا" in t or "{ر" in t or "{ال" in t for t in tpl))

        # ── القالب لا يُطلب من رسالةٍ يدوية
        await open_tpl(pg, "تأكيد")
        m0 = await pg.evaluate("()=>({trig:document.getElementById('t-trig').value,"
                               " metaHidden:document.getElementById('t-meta').hidden})")
        rec("رسالة يدوية: لا قسم قالب", m0["trig"] == "" and m0["metaHidden"], m0["trig"])

        await pg.evaluate("()=>{const s=document.getElementById('t-trig');s.value='on_confirmed';s.onchange();}")
        await pg.wait_for_timeout(300)
        m1 = await pg.evaluate("""()=>({
          shown:!document.getElementById('t-meta').hidden,
          text:document.getElementById('t-meta-text').textContent,
          vars:document.getElementById('t-meta-vars').textContent,
          name:(document.getElementById('t-wa-name')||{}).value,
          ok:(document.getElementById('t-wa-ok')||{}).checked})""")
        rec("تفعيلها تلقائيًا يُظهر القالب", m1["shown"])
        rec("والنصّ المعروض مرقّم", m1["text"].startswith("أهلاً {{1}}"), m1["text"][:22])
        rec("وسطر المتغيّرات يشرح الترتيب",
            "{{1}} = {الاسم}" in m1["vars"], m1["vars"][:44])

        # ── الاعتماد يسقط بلا اسم قالب
        await pg.evaluate("""()=>{const o=document.getElementById('t-wa-ok'); o.checked=true;
          document.getElementById('t-wa-name').value=''; window.__UPSERT=[];}""")
        await pg.click("#t-save"); await pg.wait_for_timeout(1300)
        up = await pg.evaluate("()=>(window.__UPSERT||[])")
        pa = up[-1] if up else {}
        rec("بلا اسم قالب لا يُحفَظ اعتماد",
            pa.get("wa_template_ok") is False and pa.get("wa_template_name") is None,
            f'{pa.get("wa_template_ok")} / {pa.get("wa_template_name")}')

        await msgs_pane(pg)
        await open_tpl(pg, "تأكيد")
        await pg.evaluate("""()=>{const s=document.getElementById('t-trig');s.value='on_confirmed';s.onchange();
          document.getElementById('t-wa-name').value='booking_confirmed';
          document.getElementById('t-wa-ok').checked=true; window.__UPSERT=[];}""")
        await pg.click("#t-save"); await pg.wait_for_timeout(1300)
        up = await pg.evaluate("()=>(window.__UPSERT||[])")
        pb = up[-1] if up else {}
        rec("وباسمٍ يُحفظ الاسم والاعتماد",
            pb.get("wa_template_name") == "booking_confirmed" and pb.get("wa_template_ok") is True,
            f'{pb.get("wa_template_name")} / {pb.get("wa_template_ok")}')

        rec("[غير مربوطة] بلا أخطاء", not errs, "; ".join(errs[:2]))
        await pg.screenshot(path=f"{_H.SHOTS}/38-meta-tpl.png", full_page=True)
        await ctx.close()

        # ══ الجولة الثانية: مربوطة ══
        MOCK2 = (MOCK.replace("wa_auto_enabled:false", "wa_auto_enabled:true")
                     .replace("wa_phone_id:null", "wa_phone_id:'123456789'"))
        ctx2 = await b.new_context(viewport={"width": 430, "height": 932}, device_scale_factor=2)
        await ctx2.route("**/assets/vendor/supabase.js",
                         lambda r: asyncio.ensure_future(r.fulfill(
                             content_type="application/javascript", body=MOCK2)))
        pg2 = await ctx2.new_page()
        e2 = []; pg2.on("pageerror", lambda e: e2.append(str(e)))
        await pg2.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
        await pg2.goto(f"http://127.0.0.1:{PORT}/admin.html")
        await pg2.wait_for_timeout(1700)
        await msgs_pane(pg2)

        v = await pg2.evaluate("""()=>({btn:!!document.getElementById('wa-send-test'),
          fld:!!document.getElementById('wa-test'),
          hint:document.getElementById('view').innerText.includes('٢٤ ساعة'),
          preview:document.getElementById('view').innerText.includes('وضع المعاينة')})""")
        rec("[مربوطة] زرّ التجربة وحقل الرقم ظاهران", v["btn"] and v["fld"])
        rec("[مربوطة] وتشرح شرط الأربع والعشرين ساعة", v["hint"])
        rec("[مربوطة] ولا تقول «وضع المعاينة»", not v["preview"])

        await pg2.evaluate("()=>{document.getElementById('wa-test').value='0501234567';}")
        await pg2.click("#wa-send-test")
        await pg2.wait_for_timeout(4200)
        log = await pg2.evaluate("()=>document.getElementById('obList').innerText")
        rec("الضغط يسجّل رسالة تجربة في السجلّ",
            "تجربة" in log, log[:60].replace("\n", " "))
        rec("وتصير «أُرسلت» بعد قراءة الجواب", "أُرسلت" in log,
            log[:80].replace("\n", " "))

        bad = await pg2.evaluate("""()=>{const e=document.getElementById('wa-err');
          return e?e.innerText.trim():'';}""")
        rec("بلا خطأ معروض", not bad, bad[:50])
        rec("[مربوطة] بلا أخطاء", not e2, "; ".join(e2[:2]))
        await pg2.screenshot(path=f"{_H.SHOTS}/38-linked.png", full_page=True)
        await ctx2.close()
        await b.close()

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
