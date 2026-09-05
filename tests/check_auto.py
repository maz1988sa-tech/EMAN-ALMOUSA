# -*- coding: utf-8 -*-
"""الرسائل التلقائية في اللوحة — ما تراه إيمان قبل أن تصل رسالةٌ أحدًا.

المحرّك يُفحص في القاعدة (check_auto.sql)، وهنا تُفحص الواجهة: بطاقة
الحالة، وشارة كلِّ رسالة، وقسم التوقيت في المحرّر، وحمولة الحفظ، والسجلّ.
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
_OLD = "      update(v) { return {"
assert _OLD in MOCK, "mock update() shape changed"
MOCK = MOCK.replace(_OLD, "      update(v) { (window.__UPDATE = window.__UPDATE || []).push([name, v]); return {", 1)
_OLDU = "      upsert(v) { (window.__UPSERT = window.__UPSERT || []).push(v);"
assert _OLDU in MOCK, "mock upsert() shape changed"

R = []
def rec(n, ok, note=""):
    R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

async def msgs_pane(pg):
    """«الرسائل» قسمٌ فرعيّ تحت «الإعدادات» لا تبويبٌ مستقلّ."""
    await pg.evaluate("()=>document.querySelector('[data-tab=\"settings\"]').click()")
    await pg.wait_for_timeout(1100)
    await pg.evaluate("()=>document.querySelector('[data-pane=\"msgs\"]').click()")
    await pg.wait_for_timeout(1200)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(
            **_H.CHROME,
            args=["--no-sandbox"])
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

        # ── ١) بطاقة الحالة تقول الحقيقة: وضع معاينة، لا إرسال
        card = await pg.evaluate("""()=>{
          const t=document.body.innerText;
          return {preview:/وضع المعاينة/.test(t), noone:/لا تخرج رسالة إلى أحد/.test(t),
                  qf:!!document.getElementById('wa-qf'), qt:!!document.getElementById('wa-qt'),
                  qfv:(document.getElementById('wa-qf')||{}).value,
                  qtv:(document.getElementById('wa-qt')||{}).value,
                  log:/سجلّ الإرسال التلقائي/.test(t)};}""")
        rec("بطاقة «وضع المعاينة» ظاهرة", card["preview"] and card["noone"])
        rec("ساعات الهدوء موجودة بقيمها", card["qf"] and card["qt"] and card["qfv"] == "22" and card["qtv"] == "9",
            f'{card["qfv"]}→{card["qtv"]}')
        rec("قسم السجلّ موجود", card["log"])

        # ── ٢) شارة الرسالة المفعّلة مكتوبة بلغة إيمان لا بالدقائق
        pills = await pg.evaluate("""()=>[...document.querySelectorAll('#tplList .rowline')]
          .map(r=>({t:r.querySelector('.t').textContent.trim(),
                    pills:[...r.querySelectorAll('.pill')].map(p=>p.textContent.trim())}))""")
        rem = next((r for r in pills if "تذكير" in r["t"]), None)
        conf = next((r for r in pills if "تأكيد" in r["t"]), None)
        rec("الرسالة التلقائية تحمل شارة توقيتها",
            rem and any("قبل الموعد بيوم" in p for p in rem["pills"]), str(rem and rem["pills"]))
        rec("والشارة تذكر الساعة", rem and any("٦ م" in p or "6 م" in p for p in rem["pills"]),
            str(rem and rem["pills"]))
        rec("والرسالة اليدوية بلا شارة تلقائية",
            conf and not any("قبل" in p or "عند" in p or "بعد" in p for p in conf["pills"]),
            str(conf and conf["pills"]))
        rec("لا رقم دقائق خامًا في الشارة",
            rem and not any("1440" in p for p in rem["pills"]))

        await pg.screenshot(path=f"{_H.SHOTS}/36-msgs.png", full_page=True)

        # ── ٣) المحرّر: التوقيت يظهر للمُطلِق الزمنيّ وحده
        await pg.evaluate("""()=>{const r=[...document.querySelectorAll('#tplList .rowline')]
          .find(x=>/تذكير/.test(x.textContent)); r.querySelector('[data-tpl]').click();}""")
        await pg.wait_for_timeout(700)
        ed = await pg.evaluate("""()=>({
          trig:(document.getElementById('t-trig')||{}).value,
          opts:[...(document.getElementById('t-trig')||{options:[]}).options].map(o=>o.textContent.trim()),
          timed:!document.getElementById('t-timing').hidden,
          num:(document.getElementById('t-num')||{}).value,
          unit:(document.getElementById('t-unit')||{}).value,
          hour:(document.getElementById('t-hour')||{}).value,
          sum:(document.getElementById('t-auto-sum')||{}).textContent})""")
        rec("المحرّر يفتح على المُطلِق المحفوظ", ed["trig"] == "before_appt", ed["trig"])
        rec("والخيارات الخمسة موجودة", len(ed["opts"]) == 5, " / ".join(ed["opts"]))
        rec("وقسم التوقيت ظاهر", ed["timed"])
        rec("والمدّة مقروءة: يوم واحد لا ١٤٤٠ دقيقة",
            ed["num"] == "1" and ed["unit"] == "1440", f'{ed["num"]}×{ed["unit"]}')
        rec("والساعة محفوظة", ed["hour"] == "18", ed["hour"])
        rec("والملخّص يشرح الأثر", "ستُرسل تلقائيًا" in ed["sum"], ed["sum"])

        # الانتقال إلى مُطلِقٍ غير زمنيّ يخفي التوقيت
        await pg.evaluate("()=>{const s=document.getElementById('t-trig');s.value='on_confirmed';s.onchange();}")
        await pg.wait_for_timeout(200)
        h1 = await pg.evaluate("()=>({hid:document.getElementById('t-timing').hidden, sum:document.getElementById('t-auto-sum').textContent})")
        rec("«فور التأكيد» يخفي المدّة", h1["hid"], h1["sum"])
        await pg.evaluate("()=>{const s=document.getElementById('t-trig');s.value='';s.onchange();}")
        await pg.wait_for_timeout(200)
        h2 = await pg.evaluate("()=>document.getElementById('t-auto-sum').textContent")
        rec("«بيدي فقط» يقول ذلك صراحة", "بيدك" in h2, h2)

        # ── ٤) الحفظ يرسل حقول الأتمتة كاملة
        await pg.evaluate("""()=>{
          const t=document.getElementById('t-trig'); t.value='after_done'; t.onchange();
          const n=document.getElementById('t-num'); n.value='2'; n.onchange();
          const u=document.getElementById('t-unit'); u.value='1440'; u.onchange();
          const h=document.getElementById('t-hour'); h.value='11'; h.onchange();
          window.__UPSERT=[];}""")
        await pg.wait_for_timeout(200)
        sm = await pg.evaluate("()=>document.getElementById('t-auto-sum').textContent")
        rec("الملخّص يقرأ «بعد الخدمة بيومين»", "بيومين" in sm, sm)
        await pg.click("#t-save"); await pg.wait_for_timeout(1400)
        up = await pg.evaluate("()=>(window.__UPSERT||[])")
        patch = up[-1] if up else {}
        rec("الحفظ يرسل auto_enabled", patch.get("auto_enabled") is True, str(patch.get("auto_enabled")))
        rec("ويرسل المُطلِق", patch.get("auto_trigger") == "after_done", str(patch.get("auto_trigger")))
        rec("ويحوّل المدّة إلى دقائق", patch.get("auto_offset_min") == 2880, str(patch.get("auto_offset_min")))
        rec("ويرسل الساعة", patch.get("auto_at_hour") == 11, str(patch.get("auto_at_hour")))
        rec("ولم يفقد نصّ الرسالة", bool(patch.get("body")) and bool(patch.get("title")))

        # ── ٥) السجلّ يظهر بعد إعادة الجدولة
        await msgs_pane(pg)
        await pg.wait_for_timeout(1200)
        log = await pg.evaluate("""()=>{const b=document.getElementById('obList');
          return {n:b.querySelectorAll('.rowline').length, txt:b.innerText.slice(0,200)};}""")
        rec("السجلّ يعرض صفوفًا", log["n"] > 0, f'{log["n"]} صفًّا')
        rec("وفيه ختم «معاينة»", "معاينة" in log["txt"], log["txt"][:70].replace("\n", " "))

        body = await pg.evaluate("""async()=>{const b=document.getElementById('obList')
            .querySelector('[data-ob]'); if(!b) return null; b.click();
          await new Promise(r=>setTimeout(r,500));
          const s=document.querySelector('.sheet-body, #sheet');
          return s ? s.innerText : null;}""")
        rec("وضغط الصفّ يُظهر النصّ كما سيصل",
            body and ("🌸" in body or "تذكير" in body or "أهلاً" in body), (body or "")[:60].replace("\n", " "))

        rec("بلا أخطاء", not errs, "; ".join(errs[:2]))
        await pg.screenshot(path=f"{_H.SHOTS}/36-log.png", full_page=True)
        await ctx.close(); await b.close()

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
