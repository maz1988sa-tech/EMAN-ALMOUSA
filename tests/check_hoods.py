# -*- coding: utf-8 -*-
"""اشتراطات الأحياء — الشاشة عند صاحبة العمل، والنافذة عند العميلة.

الخطر هنا ليس عطبًا يُرى بل حكمًا يُخطئ: موقعٌ مرفوض يمرّ، أو رسومٌ
تدخل العربون فيختلف المطلوب تحويله عمّا يفحصه حارس الإيصال، أو رابطٌ
مختصر يُقبل صامتًا ثمّ يُرفض الحجز في آخر خطوة بلا سبب.

فيُقاس ما تراه العميلة فعلًا: النافذة، ونصُّها، والزرّ المقفل، والسطر
الذي يظهر في الملخّص، والعربون قبل الرسوم وبعدها.
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

R = []
def rec(n, ok, note=""):
    R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

LONG = "https://www.google.com/maps/place/x/@24.5742,46.7101,15z"
SHORT = "https://maps.app.goo.gl/8kQmR3vX2ZpL9nT7A"

async def fill_form(pg, url=LONG):
    await pg.evaluate("()=>window.__pick(0,1)"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>window.__sheet()"); await pg.wait_for_timeout(600)
    await pg.fill("#nm", "نورة التجربة")
    await pg.fill("#ph", "0501234567")
    await pg.fill("#locTxt", "حي الشفا، الرياض")
    await pg.fill("#loc", url)
    await pg.wait_for_timeout(1400)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**_H.CHROME, args=["--no-sandbox"])

        # ══ صفحة العميلة ══════════════════════════════════════════════
        for kind, loc, want in (
            ('ok',        {"state": "ok", "checked": True, "district": "حي العليا"}, 'open=False'),
            ('condition', {"state": "condition", "checked": True, "district": "حي المروج",
                           "fee": 150, "message": "رسوم مواصلات لهذا الحي."}, 'open=True'),
            ('reject',    {"state": "reject", "checked": True, "district": "حي عكاظ",
                           "message": "لا نستقبل حجوزات في هذا الحي."}, 'open=True'),
            ('blocked',   {"state": "blocked", "checked": True, "district": "حي الشفا",
                           "min_people": 2, "message": "يتطلّب شخصين فأكثر."}, 'open=True'),
        ):
            ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                      has_touch=True, is_mobile=True, device_scale_factor=2)
            await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
                r.fulfill(content_type="application/javascript", body=MOCK)))
            pg = await ctx.new_page()
            await pg.add_init_script(
                "window.__SETTINGS_PATCH__={loc_check_enabled:true};"
                "window.__LOC__=" + str(loc).replace("'", '"').replace("True", "true") + ";")
            await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
            await pg.evaluate("()=>{window.__state().settings.loc_check_enabled=true;}")
            await fill_form(pg)

            st = await pg.evaluate("""()=>{
              const m=document.getElementById('locModal');
              return {open:m.classList.contains('open'),
                      title:(document.getElementById('locModalTitle').textContent||'').trim(),
                      note:(document.getElementById('locModalNote').textContent||'').trim(),
                      blocked:document.getElementById('toPay').disabled,
                      fee:(window.__state().loc||{}).fee||0,
                      feeRow:!document.getElementById('rcFeeRow').hidden,
                      total:(document.getElementById('rcDep').textContent||'').trim(),
                      sent:(window.__LOCCHK||[]).length};}""")

            if kind == 'ok':
                rec("موقعٌ بلا شرط: لا نافذة ولا تنبيه", not st["open"], str(st["open"]))
                rec("ولا يُقفل الزرّ", not st["blocked"])
                rec("ولا يظهر سطر رسوم", not st["feeRow"])
            elif kind == 'condition':
                rec("شرطٌ برسوم: تظهر النافذة بنصّها", st["open"] and "مواصلات" in st["note"],
                    st["note"][:60])
                rec("والرسوم تدخل الإجمالي سطرًا مستقلًّا", st["feeRow"] and st["fee"] == 150,
                    f"سطر={st['feeRow']} رسوم={st['fee']}")
                rec("ولا يُقفل الزرّ — شرطٌ لا رفض", not st["blocked"])
            elif kind == 'reject':
                rec("موقعٌ مرفوض: النافذة تقول السبب",
                    st["open"] and "لا نستقبل" in st["note"], st["note"][:60])
                rec("والزرّ يُقفل قبل ذكر أيّ مبلغ", st["blocked"])
            else:
                rec("عددٌ أقلّ من الحدّ: يُمنع ويُقال السبب",
                    st["open"] and st["blocked"] and "شخصين" in st["note"], st["note"][:60])

            rec(f"[{kind}] الإحداثيّتان أُرسلتا للقاعدة", st["sent"] >= 1, f"نداءات={st['sent']}")
            await ctx.close()

        # ══ الرابط المختصر يُردّ مبكّرًا ═══════════════════════════════
        ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
        await pg.evaluate("()=>{window.__state().settings.loc_check_enabled=true;}")
        await fill_form(pg, SHORT)
        st = await pg.evaluate("""()=>({blocked:document.getElementById('toPay').disabled,
            msg:(document.getElementById('locErr').textContent||'').trim(),
            sent:(window.__LOCCHK||[]).length})""")
        rec("الرابط المختصر يُردّ عند الحقل لا عند الإرسال",
            st["blocked"] and "مختصر" in st["msg"], st["msg"][:70])
        rec("ولا يُتعب الخادم بنداءٍ بلا إحداثيات", st["sent"] == 0, f"نداءات={st['sent']}")
        await ctx.close()

        # ══ الفحص مُطفأ: لا شيء يتغيّر ═════════════════════════════════
        ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
        await fill_form(pg, SHORT)
        st = await pg.evaluate("""()=>({blocked:document.getElementById('toPay').disabled,
            sent:(window.__LOCCHK||[]).length,
            open:document.getElementById('locModal').classList.contains('open')})""")
        rec("والفحص مُطفأ: لا نداء ولا نافذة ولا منع",
            st["sent"] == 0 and not st["open"] and not st["blocked"],
            f"نداءات={st['sent']} نافذة={st['open']} مقفل={st['blocked']}")
        await ctx.close()

        # ══ لوحة صاحبة العمل ══════════════════════════════════════════
        ctx = await b.new_context(viewport={"width": 430, "height": 950},
                                  device_scale_factor=2, locale="ar-SA")
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
        await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(2000)
        await pg.evaluate("""()=>{const t=[...document.querySelectorAll('.tab')]
            .find(e=>e.textContent.includes('الإعدادات')); t && t.click();}""")
        await pg.wait_for_timeout(800)
        tabs = await pg.eval_on_selector_all(".panetab", "e=>e.map(x=>x.textContent.trim())")
        rec("تبويب «الأحياء» في الإعدادات", "الأحياء" in tabs, str(tabs))

        await pg.evaluate("""()=>{const b=[...document.querySelectorAll('[data-pane]')]
            .find(x=>x.dataset.pane==='hoods'); b && b.click();}""")
        await pg.wait_for_timeout(1200)
        m = await pg.evaluate("""()=>({dots:document.querySelectorAll('#h-map circle').length,
            rows:document.querySelectorAll('[data-hood]').length,
            hasOn:!!document.getElementById('h-on'),
            hasOut:!!document.getElementById('o-reject'),
            hasImport:!!document.getElementById('h-import'),
            saveOff:document.getElementById('h-save').disabled})""")
        rec("الخريطة تُرسم بكلّ حيّ", m["dots"] == 4, f"نقاط={m['dots']}")
        rec("والقائمة كذلك", m["rows"] == 4, f"صفوف={m['rows']}")
        rec("ومفتاح الفحص وحكم الخارج والاستيراد",
            m["hasOn"] and m["hasOut"] and m["hasImport"])
        rec("والحفظ مقفل قبل اختيار حيّ", m["saveOff"])

        # لون الحيّ يقول شرطه — ولا يُخلط الموقوف بالمُفعّل
        cols = await pg.evaluate("""()=>[...document.querySelectorAll('#h-map circle')]
            .map(c=>c.getAttribute('fill'))""")
        rec("المرفوض والمشروط والموقوف بألوانٍ مختلفة",
            len(set(cols)) >= 3, str(cols))

        # اختيار حيّين وحفظ شرطٍ واحد عليهما
        await pg.evaluate("""()=>{const r=[...document.querySelectorAll('[data-hood]')];
            r[0].click(); r[2].click();}""")
        await pg.wait_for_timeout(400)
        await pg.evaluate("""()=>{
            document.getElementById('r-fee').value = '200';
            const c = document.getElementById('r-reject');
            c.checked = true; c.dispatchEvent(new Event('change', {bubbles:true}));
        }""")
        await pg.evaluate("()=>document.getElementById('h-save').click()")
        await pg.wait_for_timeout(900)
        call = await pg.evaluate("()=>(window.__HOODRULE||[])[0] || null")
        rec("شرطٌ واحد يُحفظ على حيّين دفعةً واحدة",
            call is not None and len(call.get("p_ids") or []) == 2, str(call and call.get("p_ids")))
        rec("والتفعيل يُرسل مع الشرط لا يُفترض",
            call is not None and call.get("p_active") is True, str(call and call.get("p_active")))

        await pg.screenshot(path=f"{_H.SHOTS}/36-hoods.png", full_page=True)
        await ctx.close()
        await b.close()

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
