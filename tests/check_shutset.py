# -*- coding: utf-8 -*-
"""إعداد الشهور المغلقة في لوحة إيمان — وأثره في صفحة العميلة.

الإعداد لا يُقاس بوجود المربّع، بل بما يصل إلى الحفظ وما تراه العميلة
بعده. فيُفحص هنا: ظهور المربّع، اختفاء الصيغة حين يُطفأ، معاينةٌ مذكَّرة
صحيحة، والحقلان يُرسَلان إلى قاعدة البيانات بقيمتيهما.
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
# نقرأ ما يصل القاعدة لا ما يظهر على الشاشة: الإعداد يُصدَّق بحمولة الحفظ.
_OLD = "      update(v) { return {"
assert _OLD in MOCK, "mock update() shape changed"
MOCK = MOCK.replace(_OLD, "      update(v) { (window.__UPDATE = window.__UPDATE || []).push([name, v]); return {", 1)

R = []
def rec(n, ok, note=""):
    R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

async def tab(pg, rx):
    await pg.evaluate(f"()=>{{const t=[...document.querySelectorAll('[data-tab]')].find(e=>/{rx}/.test(e.textContent)); if(t) t.click();}}")
    await pg.wait_for_timeout(1100)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(
            **_H.CHROME,
            args=["--no-sandbox"])

        # ── لوحة إيمان
        ctx = await b.new_context(viewport={"width": 430, "height": 932}, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js",
                        lambda r: asyncio.ensure_future(r.fulfill(
                            content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
        await pg.goto(f"http://127.0.0.1:{PORT}/admin.html")
        await pg.wait_for_timeout(1700)
        await tab(pg, "الإعدادات")

        seen = await pg.evaluate("""()=>{
          const cb=document.getElementById('set-shutmo');
          const sel=document.getElementById('set-shutword');
          const wrap=document.getElementById('set-shutword-wrap');
          const lbl=cb&&cb.closest('.toggle');
          const adv=document.getElementById('set-adv');
          return {has:!!cb&&!!sel, on:cb&&cb.checked, hid:wrap&&wrap.hidden,
                  txt:lbl?lbl.innerText.trim():'',
                  opts:sel?[...sel.options].map(o=>o.value):[],
                  val:sel?sel.value:'',
                  prev:(document.getElementById('set-shutprev')||{}).textContent||'',
                  near: !!(adv&&lbl&&adv.closest('.card')===lbl.closest('.card'))};}""")
        rec("المربّع والصيغة موجودان في الإعدادات", seen["has"])
        rec("وهما في بطاقة «المواعيد» مع أبعد حجز", seen["near"])
        rec("المربّع مفعّل افتراضيًا", seen["on"])
        rec("والصيغة ظاهرة معه", not seen["hid"])
        rec("الخياران هما المطلوبان",
            seen["opts"] == ["غير مفتوحة", "غير متاحة"], str(seen["opts"]))
        rec("والافتراضي «غير مفتوحة»", seen["val"] == "غير مفتوحة", seen["val"])
        rec("المعاينة مذكَّرة صحيحة",
            "هذا الشهر غير مفتوح للحجز" in seen["prev"], seen["prev"])
        rec("نصّ المربّع يشرح الأثر",
            "لم تُفتح" in seen["txt"] or "لم تفتح" in seen["txt"], seen["txt"][:70])

        # إطفاء المربّع يخفي الصيغة
        await pg.evaluate("()=>{const c=document.getElementById('set-shutmo');c.checked=false;c.onchange();}")
        await pg.wait_for_timeout(200)
        rec("الإطفاء يخفي الصيغة",
            await pg.evaluate("()=>document.getElementById('set-shutword-wrap').hidden"))
        await pg.evaluate("()=>{const c=document.getElementById('set-shutmo');c.checked=true;c.onchange();}")
        await pg.wait_for_timeout(200)
        rec("والإشعال يعيدها",
            not await pg.evaluate("()=>document.getElementById('set-shutword-wrap').hidden"))

        # تبديل الصيغة يبدّل المعاينة
        await pg.evaluate("()=>{const s=document.getElementById('set-shutword');s.value='غير متاحة';s.onchange();}")
        await pg.wait_for_timeout(200)
        rec("تبديل الصيغة يبدّل المعاينة",
            "«هذا الشهر غير متاح للحجز.»" in await pg.evaluate("()=>document.getElementById('set-shutprev').textContent"),
            await pg.evaluate("()=>document.getElementById('set-shutprev').textContent"))

        # الحفظ يرسل الحقلين فعلًا إلى قاعدة البيانات
        await pg.evaluate("()=>{window.__UPDATE=[];}")
        await pg.evaluate("""()=>{
          const c=document.getElementById('set-shutmo'); c.checked=true; c.onchange();
          const s=document.getElementById('set-shutword'); s.value='غير متاحة'; s.onchange();}""")
        await pg.click("#saveSettings")
        await pg.wait_for_timeout(1200)
        up = await pg.evaluate("()=>(window.__UPDATE||[]).filter(x=>x[0]==='settings').map(x=>x[1])")
        patch = up[-1] if up else {}
        rec("الحفظ يرسل تحديثًا لجدول الإعدادات", bool(up), str(len(up)))
        rec("ويحمل show_closed_months=true",
            patch.get("show_closed_months") is True, str(patch.get("show_closed_months")))
        rec("ويحمل closed_month_word المختارة",
            patch.get("closed_month_word") == "غير متاحة", str(patch.get("closed_month_word")))
        rec("ولم يفقد بقيّة الحقول",
            patch.get("max_advance_days") is not None and patch.get("business_name"),
            f'{len(patch)} حقلًا')

        # والإطفاء يُرسَل كذلك
        await pg.evaluate("()=>{window.__UPDATE=[];}")
        await pg.evaluate("()=>{const c=document.getElementById('set-shutmo');c.checked=false;c.onchange();}")
        await pg.click("#saveSettings")
        await pg.wait_for_timeout(1200)
        up2 = await pg.evaluate("()=>(window.__UPDATE||[]).filter(x=>x[0]==='settings').map(x=>x[1])")
        rec("والإطفاء يصل كـ false",
            bool(up2) and up2[-1].get("show_closed_months") is False,
            str(up2[-1].get("show_closed_months") if up2 else None))

        rec("الحفظ لا يرمي خطأً", not errs, "; ".join(errs[:2]))
        await pg.screenshot(path=f"{_H.SHOTS}/34-shut-settings.png", full_page=True)
        await ctx.close()

        # ── صفحة العميلة بالصيغة الثانية
        MOCK2 = MOCK.replace("closed_month_word:'غير مفتوحة'", "closed_month_word:'غير متاحة'")
        ctx2 = await b.new_context(viewport={"width": 390, "height": 760},
                                   has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx2.route("**/assets/vendor/supabase.js",
                         lambda r: asyncio.ensure_future(r.fulfill(
                             content_type="application/javascript", body=MOCK2)))
        pg2 = await ctx2.new_page()
        await pg2.goto(f"http://127.0.0.1:{PORT}/index.html")
        await pg2.wait_for_timeout(1500)
        await pg2.evaluate("window.__pick(0,1)"); await pg2.wait_for_timeout(300)
        await pg2.evaluate("window.__goto(2)"); await pg2.wait_for_timeout(1400)
        await pg2.click("#monthLabel"); await pg2.wait_for_timeout(400)
        await pg2.click("#yNext"); await pg2.wait_for_timeout(350)
        note = await pg2.evaluate("()=>({hid:mPickNote.hidden, txt:mPickNote.textContent})")
        rec("«غير متاحة»: سطر اللوح يتبع الاختيار",
            not note["hid"] and note["txt"].strip() == "الشهور المشطوبة غير متاحة للحجز.", note["txt"])
        await pg2.screenshot(path=f"{_H.SHOTS}/34-mpick.png")
        await pg2.evaluate("()=>document.getElementById('mPickVeil').click()")
        await pg2.wait_for_timeout(350)
        msg = await pg2.evaluate("""async()=>{const nx=document.getElementById('mNext');
          let n=0; while(!document.getElementById('cal').classList.contains('shut') && n<20){
            if(nx.disabled) break; nx.click(); n++; await new Promise(r=>setTimeout(r,180));}
          const m=document.querySelector('.shut-msg');
          return m?m.innerText.trim():null;}""")
        rec("«غير متاحة»: الرسالة مذكَّرة صحيحة",
            msg and msg.startswith("هذا الشهر غير متاح للحجز."), (msg or "")[:50])
        rec("ولا تظهر صيغة مؤنّثة مع «الشهر»",
            msg and "الشهر غير متاحة" not in msg)
        await pg2.screenshot(path=f"{_H.SHOTS}/34-shutmonth.png")
        await ctx2.close()
        await b.close()

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
