# -*- coding: utf-8 -*-
"""قاعدة العميلات — «الإعدادات ← العميلات».

ما يُقاس هو ما تحتاجه صاحبة العمل فعلًا: كلُّ عميلةٍ صفٌّ واحد مهما
تكرّرت حجوزاتها، والعدد والمبلغ صحيحان والملغى خارجهما، والترتيب ينقلب
بزرّ، والبحث يجد بالاسم وبالجوال، والصفّ يُفتح على تفاصيله — والأرقام
مصطفّة تحت بعضها. والتصدير ملفُّ Excel حقيقيّ يُفتح ويُقرأ: الجوال نصٌّ
بصفره، والتاريخ تاريخ، والورقة من اليمين.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, io, base64, http.server, socketserver, threading, functools, datetime
from playwright.async_api import async_playwright
import openpyxl

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

# سجلٌّ إضافيّ: نورة (من المحاكي) حجزت قبل شهور مرّتين — واحدةٌ ملغاة —
# وحجزٌ لعميلةٍ حُذفت حجوزاتها جماعيًّا فبقيت في السجلّ وحده.
OLD = "2025-11-02T10:00:00Z"
HIST = f"""window.__CLIENT_HISTORY__ = [
  {{ phone:'966501234567', name:'نورة', loc_text:'حي الشفا', loc_map:null, the_date:'2025-11-20',
     booked_at:'{OLD}', price:800, status:'done' }},
  {{ phone:'966501234567', name:'نورة', loc_text:null, loc_map:null, the_date:'2025-12-01',
     booked_at:'2025-11-15T10:00:00Z', price:5000, status:'cancelled' }},
  {{ phone:'966577770000', name:'جود (أرشيف)', loc_text:'حي العقيق', loc_map:'https://maps.app.goo.gl/q',
     the_date:'2025-06-01', booked_at:'2025-05-01T09:00:00Z', price:2000, status:'done' }},
];"""

async def open_pane(pg):
    await pg.evaluate("()=>{const t=[...document.querySelectorAll('[data-tab]')].find(e=>/الإعدادات/.test(e.textContent)); t&&t.click();}")
    await pg.wait_for_timeout(700)
    await pg.evaluate("()=>{const t=[...document.querySelectorAll('[data-pane]')].find(e=>e.dataset.pane==='clients'); t&&t.click();}")
    await pg.wait_for_timeout(900)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**_H.CHROME, args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                  accept_downloads=True)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;" + HIST)
        await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(1700)
        await open_pane(pg)

        # ── القسم في شريط الإعدادات ──────────────────────────────────
        t = await pg.evaluate("""()=>({pane:!!document.querySelector('[data-pane="clients"][aria-current="true"]'),
            head:(document.querySelector('.sec-head h2')||{}).textContent||''})""")
        rec("قسم «العميلات» في الإعدادات ويفتح «قاعدة العميلات»",
            t["pane"] and "قاعدة العميلات" in t["head"], t["head"])

        rows = await pg.evaluate("""()=>[...document.querySelectorAll('.cl-row')].map(r=>({
            name:r.querySelector('.cl-who b').textContent.trim(),
            sub:[...r.querySelectorAll('.cl-who .s')].map(e=>e.textContent.trim()).join(' · '),
            n:r.querySelector('.cl-n').textContent.trim(),
            t:r.querySelector('.cl-t').textContent.trim().replace(/,/g,'')}))""")
        # المحاكي فيه خمس عميلات بجوالاتٍ مختلفة، والسجلّ يضيف «جود» — ونورة واحدة.
        rec("صفٌّ لكلّ جوال — المكرّرة لا تتكرّر", len(rows) == 6, f"{len(rows)} صفوف")
        nora = next((r for r in rows if "966501234567"[3:] in r["sub"].replace(" ", "") or "نورة" in r["name"]), None)
        rec("واسمُها من أحدث حجز", nora and nora["name"] == "نورة العتيبي", str(nora))
        # حجزها في المحاكي ١٥٠٠ + حجزٌ قديم ٨٠٠ = ٢٣٠٠ على حجزين؛ والملغى (٥٠٠٠) خارج العدّ والجمع.
        rec("والعددُ والمبلغ يجمعان حجوزاتها، والملغى خارجهما",
            nora and nora["n"] == "2" and nora["t"] == "2300", str(nora))
        jood = next((r for r in rows if "جود" in r["name"]), None)
        rec("وعميلةُ الحذف الجماعيّ باقيةٌ من السجلّ", bool(jood) and jood["n"] == "1", str(jood))

        # ── الترتيب: الأحدث أوّلًا ثمّ ينقلب ──────────────────────────
        first_new = rows[0]["name"] if rows else ""
        await pg.click('[data-cs="old"]'); await pg.wait_for_timeout(300)
        order_old = await pg.evaluate("()=>[...document.querySelectorAll('.cl-row .cl-who b')].map(e=>e.textContent.trim())")
        rec("«الأقدم أوّلًا» يبدأ بأقدم تسجيل", order_old[:1] == ["جود (أرشيف)"], str(order_old[:2]))
        rec("و«الأحدث أوّلًا» عكسُه تمامًا", order_old and list(reversed(order_old))[0] == first_new
            and order_old[-1] == first_new, f"{first_new} ⇄ {order_old[-1] if order_old else ''}")
        pressed = await pg.evaluate("()=>document.querySelector('[data-cs=\"old\"]').getAttribute('aria-pressed')")
        rec("والزرّ المختار معلَّم", pressed == "true")

        # ── البحث ──────────────────────────────────────────────────
        await pg.fill("#clQ", "ريم"); await pg.wait_for_timeout(250)
        n1 = await pg.evaluate("()=>[...document.querySelectorAll('.cl-row .cl-who b')].map(e=>e.textContent)")
        rec("البحث بالاسم", n1 == ["ريم القحطاني"], str(n1))
        await pg.fill("#clQ", "٠٥٥٥٥٥"); await pg.wait_for_timeout(250)
        n2 = await pg.evaluate("()=>[...document.querySelectorAll('.cl-row .cl-who b')].map(e=>e.textContent)")
        rec("والبحث بالجوال بأرقامٍ عربية وصفرٍ أوّل", n2 == ["ريم القحطاني"], str(n2))
        lbl = await pg.evaluate("()=>document.getElementById('clXlsx').textContent.trim()")
        rec("وزرّ التصدير يقول كم سيُصدّر حين يُرشَّح", "(1)" in lbl, lbl)
        await pg.fill("#clQ", ""); await pg.wait_for_timeout(250)

        # ── الصفّ يُفتح ─────────────────────────────────────────────
        await pg.evaluate("()=>{const r=[...document.querySelectorAll('.cl-row')].find(x=>x.textContent.includes('جود')); r.querySelector('summary').click();}")
        await pg.wait_for_timeout(300)
        more = await pg.evaluate("""()=>{const r=[...document.querySelectorAll('.cl-row')].find(x=>x.textContent.includes('جود'));
            return {open:r.open, txt:r.querySelector('.cl-more').innerText,
                    map:(r.querySelector('.cl-more a[href*="maps"]')||{}).href||'',
                    wa:(r.querySelector('.cl-acts a[href*="wa.me"]')||{}).href||''};}""")
        rec("الصفّ يُفتح على الحيّ وأوّل تسجيل وآخر موعد",
            more["open"] and "حي العقيق" in more["txt"] and "أوّل تسجيل" in more["txt"]
            and "آخر موعد" in more["txt"], more["txt"].replace("\n", " ")[:90])
        rec("ومعه رابط الخريطة وواتساب", "maps.app.goo.gl" in more["map"] and "wa.me/966577770000" in more["wa"],
            f'{more["map"]} · {more["wa"]}')

        # ── الأعمدة العدديّة مصطفّة تحت بعضها، وتحت ترويستها ─────────
        al = await pg.evaluate("""()=>{const xs=(sel)=>[...document.querySelectorAll(sel)].map(e=>{const b=e.getBoundingClientRect();return [Math.round(b.left),Math.round(b.right)];});
            return {hn:xs('.cl-head span:nth-child(2)'), n:xs('.cl-row .cl-n'),
                    ht:xs('.cl-head span:nth-child(3)'), t:xs('.cl-row .cl-t'),
                    over:document.documentElement.scrollWidth - innerWidth};}""")
        same = lambda col, head: bool(col) and all(c == head[0] for c in col)
        rec("عمودُ الحجوزات مصطفٌّ في كلّ صفّ وتحت ترويسته", same(al["n"], al["hn"]), f'{al["hn"]} / {al["n"][:3]}')
        rec("وعمودُ الإجمالي كذلك", same(al["t"], al["ht"]), f'{al["ht"]} / {al["t"][:3]}')
        rec("ولا سحبَ أفقيّ على ٣٩٠", al["over"] <= 0, f'زيادة={al["over"]}')
        # الجوال والتاريخ لا يُقصّان: كانا في سطرٍ واحد فقُطع التاريخ بنقاط.
        cut = await pg.evaluate("()=>[...document.querySelectorAll('.cl-who .s')].filter(e=>e.scrollWidth>e.clientWidth+1).length")
        rec("وسطرا الجوال والتاريخ لا يُقصّان", cut == 0, f"مقصوص={cut}")
        tabv = await pg.evaluate("""()=>{const t=document.querySelector('.panetab[aria-current="true"]').getBoundingClientRect();
            const bar=document.querySelector('.panebar').getBoundingClientRect();
            return t.left >= bar.left - 1 && t.right <= bar.right + 1;}""")
        rec("والقسم المفتوح يُرى كاملًا في شريط الأقسام", tabv)

        await pg.screenshot(path=f"{_H.SHOTS}/40-clients.png", full_page=True)

        # ── التصدير: ملفُّ Excel يُقرأ ───────────────────────────────
        await pg.click('[data-cs="new"]'); await pg.wait_for_timeout(200)
        async with pg.expect_download() as dl:
            await pg.click("#clXlsx")
        d = await dl.value
        # مسارُ التنزيل بلا امتداد، وopenpyxl يحكم بالامتداد — فيُحفظ باسمه.
        path = f"{_H.SHOTS}/clients-export.xlsx"
        await d.save_as(path)
        rec("اسمُ الملفّ بالعربية وامتداده xlsx",
            d.suggested_filename.startswith("قاعدة-العميلات-") and d.suggested_filename.endswith(".xlsx"),
            d.suggested_filename)
        wb = openpyxl.load_workbook(path)
        ws = wb.active
        vals = list(ws.iter_rows(values_only=True))
        head = vals[0] if vals else ()
        rec("الورقة «العميلات» من اليمين، وترويستُها مثبّتة ومرشِّحة",
            ws.title == "العميلات" and ws.sheet_view.rightToLeft and ws.freeze_panes == "A2"
            and bool(ws.auto_filter.ref), f'{ws.title} rtl={ws.sheet_view.rightToLeft} {ws.freeze_panes} {ws.auto_filter.ref}')
        want = ("الاسم", "الجوال", "الحي", "رابط الموقع", "عدد الحجوزات", "إجمالي المبلغ (ر.س)", "أوّل تسجيل", "آخر موعد")
        rec("الأعمدة الثمانية بأسمائها", tuple(head) == want, str(head))
        rec("صفٌّ لكلّ عميلة", len(vals) - 1 == 6, f"{len(vals) - 1}")
        rows_x = {r[0]: r for r in vals[1:]}
        nx = rows_x.get("نورة العتيبي")
        rec("الجوال نصٌّ بصفره لا عددٌ علميّ",
            nx and isinstance(nx[1], str) and nx[1] == "0501234567", repr(nx[1] if nx else None))
        rec("والعدد والمبلغ أرقامٌ تُجمع", nx and nx[4] == 2 and nx[5] == 2300, f"{nx[4] if nx else ''} · {nx[5] if nx else ''}")
        rec("والتاريخ تاريخٌ يُرتَّب لا نصّ", nx and isinstance(nx[6], datetime.datetime)
            and nx[6].date() == datetime.date(2025, 11, 2), repr(nx[6] if nx else None))
        order_x = [r[0] for r in vals[1:]]
        order_ui = await pg.evaluate("()=>[...document.querySelectorAll('.cl-row .cl-who b')].map(e=>e.textContent.trim())")
        rec("والملفّ بترتيب الشاشة", order_x == order_ui, f"{order_x[:2]} / {order_ui[:2]}")

        toast = await pg.evaluate("()=>[...document.querySelectorAll('.toast,[role=status]')].map(e=>e.textContent).join(' ')")
        rec("ورسالةُ النجاح بعددٍ ومعدودٍ صحيحين", "6 عميلات" in toast, toast.strip()[:60])
        rec("بلا أخطاء في الصفحة", not errs, "; ".join(errs[:2]))
        await ctx.close()

        # ── قاعدةٌ فارغة ──────────────────────────────────────────────
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript",
                      body=MOCK.replace("if (fn === 'admin_clients') {", "if (fn === 'admin_clients') { if (window.__EMPTY__) return ok([]);"))))
        pg = await ctx.new_page()
        await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true; window.__EMPTY__ = true;")
        await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(1500)
        await open_pane(pg)
        e = await pg.evaluate("()=>({t:(document.getElementById('clBody')||{}).innerText||'', x:document.getElementById('clXlsx').disabled})")
        rec("بلا عميلات: حالٌ فارغة تقول ما سيحدث، والتصدير معطّل",
            "لا عميلات بعد" in e["t"] and e["x"], e["t"].replace("\n", " ")[:60])
        await ctx.close()
        await b.close()

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
