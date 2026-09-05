# -*- coding: utf-8 -*-
"""لوح الشهور والشهر المغلق — صفحة العميلة.

الاختبار يقيس ما تراه العميلة لا ما كُتب في المصدر: عائلة الخطّ ووزنه
مقارنةً بالعنوان، وفتحُ اللوح، وشطبُ ما لم يُفتح، وامتناعُه عن الفتح،
ودخولُ السهم إلى شهرٍ مغلق فيَرماد ويُكتب سببه.
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

R = []
def rec(n, ok, note=""):
    R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

async def to_date(pg):
    await pg.evaluate("window.__pick(0,1)"); await pg.wait_for_timeout(300)
    await pg.evaluate("window.__goto(2)"); await pg.wait_for_timeout(1400)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(
            **_H.CHROME,
            args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 390, "height": 760},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js",
                        lambda r: asyncio.ensure_future(r.fulfill(
                            content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html")
        await pg.wait_for_timeout(1500)
        await to_date(pg)

        # ── 1) الخط: عائلةً ووزنًا وتتبّعًا كعنوان «اختاري التاريخ والوقت»
        f = await pg.evaluate("""()=>{
          const t=getComputedStyle(document.querySelector('.screen[data-name="الموعد"] .title'));
          const m=getComputedStyle(document.getElementById('monthLabel'));
          return {tf:t.fontFamily, mf:m.fontFamily, tw:t.fontWeight, mw:m.fontWeight,
                  tl:t.letterSpacing, ml:m.letterSpacing, ms:m.fontSize, ts:t.fontSize};}""")
        rec("عائلة خطّ الشهر = عائلة خطّ العنوان", f["tf"] == f["mf"], f"{f['mf']}")
        rec("وزن خطّ الشهر = وزن العنوان", f["tw"] == f["mw"], f"{f['mw']} / {f['tw']}")
        em = lambda ls, fs: round(float(ls[:-2]) / float(fs[:-2]), 3)
        rec("التتبّع نفسه نسبةً للحجم",
            em(f["tl"], f["ts"]) == em(f["ml"], f["ms"]),
            f'{em(f["ml"], f["ms"])}em / {em(f["tl"], f["ts"])}em')
        rec("لا يحمل خطّ Amiri", "Amiri" not in f["mf"], f["mf"])
        rec("حجم الشهر أكبر من قبل (≥22)", float(f["ms"][:-2]) >= 22, f["ms"])

        # ── 2) دائرة السهم صارت أوسع للضغط
        a = await pg.evaluate("""()=>{const r=document.getElementById('mNext').getBoundingClientRect();
          const cs=getComputedStyle(document.getElementById('mNext'));
          return {w:Math.round(r.width), h:Math.round(r.height), br:cs.borderRadius};}""")
        rec("زرّ السهم ≥48×48 ودائريّ", a["w"] >= 48 and a["h"] >= 48 and "999" in a["br"] or a["w"] >= 48 and a["h"] >= 48 and a["br"].startswith(("24", "48")),
            f'{a["w"]}×{a["h"]} r={a["br"]}')

        # ── 3) الضغط على اسم الشهر يفتح اللوح
        vis = "()=>{const e=document.getElementById('mPick');const c=getComputedStyle(e);return c.visibility==='visible'&&Number(c.opacity)>.9;}"
        rec("اللوح مغلقٌ ابتداءً", not await pg.evaluate(vis))
        await pg.click("#monthLabel"); await pg.wait_for_timeout(450)
        rec("الضغط على اسم الشهر يفتح اللوح", await pg.evaluate(vis))
        rec("aria-expanded صار true",
            await pg.get_attribute("#monthLabel", "aria-expanded") == "true")

        g = await pg.evaluate("""()=>{
          const cells=[...document.querySelectorAll('#mPickGrid .mo')];
          return {n:cells.length, y:document.getElementById('yLabel').textContent,
                  rows:cells.map(c=>({t:c.textContent, off:c.disabled,
                    shut:c.classList.contains('shut'), gone:c.classList.contains('gone'),
                    line:getComputedStyle(c).textDecorationLine}))};}""")
        rec("اللوح فيه ١٢ شهرًا", g["n"] == 12, str(g["n"]))

        # الحدّ: max_advance_days=120 من اليوم ⇒ آخر شهر مفتوح يُحسب في الصفحة
        bnd = await pg.evaluate("""()=>{const t=new Date();
          const adv=120; const far=new Date(t.getFullYear(),t.getMonth(),t.getDate()+adv);
          return {oy:far.getFullYear(), om:far.getMonth(), ty:t.getFullYear(), tm:t.getMonth()};}""")
        cur_year = int(g["y"])
        for i, row in enumerate(g["rows"]):
            past = (cur_year, i) < (bnd["ty"], bnd["tm"])
            shut = (cur_year, i) > (bnd["oy"], bnd["om"])
            if shut:
                rec(f"«{row['t']}» غير مفتوح ⇒ مشطوب ومعطَّل",
                    row["off"] and "line-through" in row["line"], row["line"])
            elif past:
                rec(f"«{row['t']}» مضى ⇒ معطَّل بلا شطب",
                    row["off"] and "line-through" not in row["line"], row["line"])
            else:
                rec(f"«{row['t']}» مفتوح ⇒ قابل للضغط", not row["off"])

        # ── 4) الضغط على شهرٍ مشطوب لا يفتحه
        before = await pg.evaluate("()=>document.getElementById('monthLabelText').textContent")
        shut_idx = next((i for i, r in enumerate(g["rows"]) if r["shut"]), None)
        if shut_idx is None:
            # كل شهور السنة الحالية مفتوحة أو ماضية — انتقلي للسنة التالية
            await pg.click("#yNext"); await pg.wait_for_timeout(300)
            g2 = await pg.evaluate("""()=>[...document.querySelectorAll('#mPickGrid .mo')]
              .map(c=>({off:c.disabled,shut:c.classList.contains('shut'),
                        line:getComputedStyle(c).textDecorationLine}))""")
            shut_idx = next((i for i, r in enumerate(g2)
                             if r["shut"] and "line-through" in r["line"]), None)
        rec("توجد شهورٌ مشطوبة أصلًا", shut_idx is not None)
        if shut_idx is not None:
            await pg.evaluate(f"()=>document.querySelectorAll('#mPickGrid .mo')[{shut_idx}].click()")
            await pg.wait_for_timeout(400)
            rec("الضغط على المشطوب لا يغيّر الشهر",
                await pg.evaluate("()=>document.getElementById('monthLabelText').textContent") == before)
            rec("واللوح يبقى مفتوحًا", await pg.evaluate(vis))

        note = await pg.evaluate("""()=>{const n=document.getElementById('mPickNote');
          return {hid:n.hidden, txt:n.textContent};}""")
        rec("سطر التفسير ظاهر", not note["hid"], note["txt"])
        rec("ويحمل الكلمة المختارة والذيل الصحيح",
            note["txt"].strip() == "الشهور المشطوبة غير مفتوحة للحجز بعد.", note["txt"])

        # ── 5) اختيار شهرٍ مفتوح ينقل ويغلق اللوح
        await pg.evaluate("()=>{const y=Number(document.getElementById('yLabel').textContent);"
                          "const t=new Date(); if(y>t.getFullYear()) document.getElementById('yPrev').click();}")
        await pg.wait_for_timeout(300)
        pick = await pg.evaluate("""()=>{const c=[...document.querySelectorAll('#mPickGrid .mo')]
          .filter(x=>!x.disabled); const last=c[c.length-1]; last.click(); return last.textContent;}""")
        await pg.wait_for_timeout(700)
        rec("اختيار شهرٍ مفتوح يغلق اللوح", not await pg.evaluate(vis))
        rec("والاسم صار المختار",
            pick in await pg.evaluate("()=>document.getElementById('monthLabelText').textContent"), pick)

        # ── 6) السهم يدخل شهرًا مغلقًا: رماديّ + رسالة
        st = await pg.evaluate("""async()=>{
          const nx=document.getElementById('mNext'); let n=0;
          while(!document.getElementById('cal').classList.contains('shut') && n<20){
            if(nx.disabled) break; nx.click(); n++;
            await new Promise(r=>setTimeout(r,180));
          }
          const cal=document.getElementById('cal');
          const msg=cal.querySelector('.shut-msg');
          const wk=getComputedStyle(document.getElementById('week'));
          const days=[...document.querySelectorAll('#week button.day')];
          return {steps:n, shut:cal.classList.contains('shut'),
                  msg: msg ? msg.innerText.trim() : null,
                  gray: wk.filter, op: wk.opacity,
                  nDays: days.length, allOff: days.length>0 && days.every(d=>d.disabled),
                  label: document.getElementById('monthLabelText').textContent};}""")
        rec("السهم يدخل شهرًا مغلقًا", st["shut"], f'بعد {st["steps"]} ضغطة → {st["label"]}')
        rec("الشهر يُعرض كاملًا (أيامه موجودة)", st["nDays"] >= 28, str(st["nDays"]))
        rec("كل أيامه معطَّلة", st["allOff"])
        rec("ولونه رماديّ", "grayscale(1)" in st["gray"] and float(st["op"]) < .6,
            f'{st["gray"]} op={st["op"]}')
        rec("وعليه رسالةٌ فوق المربع", bool(st["msg"]), (st["msg"] or "")[:60])
        rec("الرسالة مذكَّرة صحيحة", st["msg"] and st["msg"].startswith("هذا الشهر غير مفتوح للحجز بعد."),
            (st["msg"] or "")[:40])
        rec("ولا تحمل صيغة المؤنّث الخاطئة",
            st["msg"] and "الشهر غير مفتوحة" not in st["msg"])

        box = await pg.evaluate("""()=>{const m=document.querySelector('.shut-msg i');
          const c=document.getElementById('cal').getBoundingClientRect();
          const r=m.getBoundingClientRect();
          return {inside: r.left>=c.left-1 && r.right<=c.right+1 && r.top>=c.top-1 && r.bottom<=c.bottom+1,
                  w:Math.round(r.width)};}""")
        rec("الرسالة داخل مربع التقويم", box["inside"], f'w={box["w"]}')

        # ── 7) السهم لا يمشي بلا نهاية
        far = await pg.evaluate("""async()=>{const nx=document.getElementById('mNext');
          let n=0; while(!nx.disabled && n<40){ nx.click(); n++; await new Promise(r=>setTimeout(r,60)); }
          return {n, label:document.getElementById('monthLabelText').textContent, off:nx.disabled};}""")
        rec("للسهم حدٌّ ينتهي عنده", far["off"], f'{far["label"]} بعد {far["n"]}')

        # ── 8) الرجوع لا يتجاوز الشهر الحالي
        back = await pg.evaluate("""async()=>{const pv=document.getElementById('mPrev');
          let n=0; while(!pv.disabled && n<60){ pv.click(); n++; await new Promise(r=>setTimeout(r,60)); }
          const t=new Date();
          return {label:document.getElementById('monthLabelText').textContent,
                  want:['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس',
                        'سبتمبر','أكتوبر','نوفمبر','ديسمبر'][t.getMonth()]+' '+t.getFullYear()};}""")
        rec("الرجوع يقف عند الشهر الحالي", back["label"] == back["want"],
            f'{back["label"]} ≠ {back["want"]}')
        rec("وعاد التقويم لونَه", not await pg.evaluate(
            "()=>document.getElementById('cal').classList.contains('shut')"))

        # ── 9) إطفاء الخاصية من الإعدادات يعيد الحدّ القديم
        off = await pg.evaluate("""async()=>{
          window.__st = window.__st || null; return true;}""")
        await pg.evaluate("""()=>{ /* لا مدخل عامّ للحالة؛ نعيد التحميل بإعداداتٍ مطفأة */ }""")
        await ctx.close()

        # جولة ثانية: الإعداد مطفأ
        MOCK_OFF = MOCK.replace("show_closed_months:true", "show_closed_months:false")
        ctx2 = await b.new_context(viewport={"width": 390, "height": 760},
                                   has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx2.route("**/assets/vendor/supabase.js",
                         lambda r: asyncio.ensure_future(r.fulfill(
                             content_type="application/javascript", body=MOCK_OFF)))
        pg2 = await ctx2.new_page()
        await pg2.goto(f"http://127.0.0.1:{PORT}/index.html")
        await pg2.wait_for_timeout(1500)
        await to_date(pg2)
        o = await pg2.evaluate("""async()=>{const nx=document.getElementById('mNext');
          let n=0; while(!nx.disabled && n<40){ nx.click(); n++; await new Promise(r=>setTimeout(r,80)); }
          return {label:document.getElementById('monthLabelText').textContent,
                  shut:document.getElementById('cal').classList.contains('shut'),
                  msg:!!document.querySelector('.shut-msg')};}""")
        rec("مطفأة: السهم لا يدخل شهرًا مغلقًا", not o["shut"] and not o["msg"], o["label"])
        await pg2.click("#monthLabel"); await pg2.wait_for_timeout(400)
        n2 = await pg2.evaluate("()=>document.getElementById('mPickNote').hidden")
        rec("مطفأة: لا سطر تفسير في اللوح", n2)
        await ctx2.close()
        await b.close()

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
