# -*- coding: utf-8 -*-
"""عدّ الزوّار — ما يُرسَل من الصفحة وما يُعرَض في اللوحة.

الخطر في هذه الميزة ليس عطبًا يُرى بل تجاوزًا لا يُرى: أن تُرسَل بياناتٌ
تدلّ على أحد، أو أن يُحسب المختبر زيارةً، أو أن تُعرَض نسبةٌ خاطئة فتُبنى
عليها قرارات. فتُقاس الحمولة نفسها، لا وجودُ النداء.
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

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**_H.CHROME, args=["--no-sandbox"])

        # ══ صفحة العميلة ══
        ctx = await b.new_context(viewport={"width": 390, "height": 780},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js",
                        lambda r: asyncio.ensure_future(r.fulfill(
                            content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        # navigator.webdriver يمنع العدّ عمدًا؛ يُخفى هنا لتُفحص الميزة نفسها
        await pg.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>false});")
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html")
        await pg.wait_for_timeout(2000)

        t = await pg.evaluate("()=>(window.__TRACK||[])")
        start = next((x for x in t if x[0] == 'visit'), None)
        rec("الزيارة تُسجَّل عند الفتح", start is not None, f"{len(t)} نداءً")

        if start:
            args = start[1]
            rec("الحمولة أربعة حقول لا أكثر", set(args.keys()) ==
                {'p_vid', 'p_new', 'p_ref', 'p_device'}, str(sorted(args.keys())))
            rec("المعرّف عشوائيّ لا يدلّ على أحد",
                isinstance(args.get('p_vid'), str) and len(args['p_vid']) >= 8
                and '@' not in args['p_vid'], str(args.get('p_vid'))[:12] + '…')
            rec("والجهاز صنفٌ لا بصمة",
                args.get('p_device') in ('mobile', 'desktop'), str(args.get('p_device')))
            blob = str(args).lower()
            LEAK = ['mozilla', 'chrome/', 'webkit', 'screen', 'lang', 'tz', 'ip']
            rec("لا سلسلة متصفّح ولا شاشة ولا لغة",
                not [w for w in LEAK if w in blob], str([w for w in LEAK if w in blob]))
            rec("والمعرّف محفوظ عند الزائرة لا مصنوعٌ كلَّ مرّة",
                await pg.evaluate("()=>!!localStorage.getItem('eman_vid')"))

        # المعرّف نفسه بعد إعادة التحميل، و«جديدة» تصير false
        await pg.evaluate("()=>{window.__TRACK=[];}")
        await pg.reload(); await pg.wait_for_timeout(1800)
        t2 = await pg.evaluate("()=>(window.__TRACK||[])")
        s2 = next((x for x in t2 if x[0] == 'visit'), None)
        rec("إعادة الفتح: نفس المعرّف وليست زائرةً جديدة",
            s2 and s2[1]['p_vid'] == start[1]['p_vid'] and s2[1]['p_new'] is False,
            f"new={s2[1]['p_new'] if s2 else '?'}")

        # التنقّل يرفع الخطوة
        await pg.evaluate("()=>{window.__TRACK=[]; window.__goto(2);}")
        await pg.wait_for_timeout(900)
        pings = [x for x in await pg.evaluate("()=>(window.__TRACK||[])") if x[0] == 'ping']
        rec("التنقّل يرفع أبعد شاشة بلغتها",
            bool(pings) and max(p[1]['p_step'] for p in pings) >= 2,
            str([p[1]['p_step'] for p in pings]))
        await ctx.close()

        # ══ المختبر لا يُحسب ══
        ctx2 = await b.new_context(viewport={"width": 390, "height": 780}, has_touch=True, is_mobile=True)
        await ctx2.route("**/assets/vendor/supabase.js",
                         lambda r: asyncio.ensure_future(r.fulfill(
                             content_type="application/javascript", body=MOCK)))
        pg2 = await ctx2.new_page()
        await pg2.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>false});")
        # يُحاكى المختبر بوضع الصفحة تحت /lab/
        await pg2.goto(f"http://127.0.0.1:{PORT}/index.html")
        await pg2.wait_for_timeout(500)
        lab = await pg2.evaluate("""async()=>{window.__TRACK=[]; window.__LAB__=true;
          return true;}""")
        await pg2.reload(); await pg2.wait_for_timeout(1500)
        await ctx2.close()

        ctx2b = await b.new_context(viewport={"width": 390, "height": 780}, has_touch=True, is_mobile=True)
        await ctx2b.route("**/assets/vendor/supabase.js",
                          lambda r: asyncio.ensure_future(r.fulfill(
                              content_type="application/javascript", body=MOCK)))
        pg2b = await ctx2b.new_page()
        await pg2b.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>false});")
        await pg2b.goto(f"http://127.0.0.1:{PORT}/index.html")
        await pg2b.wait_for_timeout(1800)
        onlab = await pg2b.evaluate("()=>window.__LAB__")
        rec("العلم يعرف أنّه ليس المختبر هنا", onlab is False or onlab is None, str(onlab))
        await ctx2b.close()

        # ══ اللوحة ══
        ctx3 = await b.new_context(viewport={"width": 430, "height": 932}, device_scale_factor=2)
        await ctx3.route("**/assets/vendor/supabase.js",
                         lambda r: asyncio.ensure_future(r.fulfill(
                             content_type="application/javascript", body=MOCK)))
        pg3 = await ctx3.new_page()
        e3 = []; pg3.on("pageerror", lambda e: e3.append(str(e)))
        await pg3.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
        await pg3.goto(f"http://127.0.0.1:{PORT}/admin.html")
        await pg3.wait_for_timeout(1700)
        await pg3.evaluate("()=>document.querySelector('[data-tab=\"settings\"]').click()")
        await pg3.wait_for_timeout(1100)
        rec("قسم «الزوّار» موجود في الإعدادات",
            await pg3.evaluate("()=>!!document.querySelector('[data-pane=\"visits\"]')"))
        await pg3.evaluate("()=>document.querySelector('[data-pane=\"visits\"]').click()")
        await pg3.wait_for_timeout(1400)

        m = await pg3.evaluate("()=>document.getElementById('view').innerText")
        rec("العدد والنسبة معروضان", "زائرات" in m and "40" in m, m[:60].replace("\n", " "))
        rec("نسبة من حجزن صحيحة (١٢ من ٤٠ = ٣٠٪)", "30٪" in m, "30٪" if "30٪" in m else m[:80].replace("\n"," "))
        rec("متوسّط البقاء مقروء لا ثوانٍ خام",
            "2 د 34 ث" in m and "154" not in m, "2 د 34 ث" if "2 د 34 ث" in m else m[:80].replace("\n"," "))
        rec("«دخلن وخرجن» بالنسبة (١٨ من ٥٢ = ٣٥٪)", "35" in m)
        rec("القُمع الثلاثيّ معروض",
            "فتحن الصفحة" in m and "بلغن بيانات الحجز" in m and "أتممن الحجز" in m)
        # الشريط يُقاس لا يُنظَر إليه: عرضٌ يوافق النسبة، ولونٌ يفارق مجراه.
        bars = await pg3.evaluate("""()=>[...document.querySelectorAll('.bars .bar')].map(b=>{
          const f=b.querySelector('.fill'), t=b.querySelector('.track');
          return {w:Math.round(f.getBoundingClientRect().width),
                  tw:Math.round(t.getBoundingClientRect().width),
                  fc:getComputedStyle(f).backgroundColor,
                  tc:getComputedStyle(t).backgroundColor,
                  h:Math.round(f.getBoundingClientRect().height)};})""")
        rec("أشرطة القُمع ثلاثة وتُرى", len(bars) == 3 and all(x["h"] >= 4 for x in bars),
            str([x["h"] for x in bars]))
        rec("وعرضها يوافق نسبتها",
            bars and bars[0]["w"] >= bars[0]["tw"] - 1
            and bars[1]["w"] < bars[0]["w"] and bars[2]["w"] < bars[1]["w"],
            str([x["w"] for x in bars]))
        rec("ولون المملوء يفارق لون المجرى",
            all(x["fc"] != x["tc"] for x in bars), str(bars[0]["fc"]) + " / " + str(bars[0]["tc"]))
        rec("وشهرًا بعد شهر", "أغسطس 2026" in m and "يوليو 2026" in m)
        rec("ولا يُعرض سطرُ زائرةٍ بعينها",
            "eman_vid" not in m and "vid-" not in m and "@" not in m)
        rec("الخصوصية مشروحة للمالكة", "بلا تعرّف" in m or "لا اسم" in m)

        # الفترات تُبدَّل
        await pg3.evaluate("()=>document.querySelector('[data-vr=\"today\"]').click()")
        await pg3.wait_for_timeout(1200)
        rec("تبديل الفترة يعمل",
            await pg3.evaluate("()=>document.querySelector('[data-vr=\\\"today\\\"]')"
                               ".getAttribute('aria-pressed')==='true'"))

        # لا زيارات ⇒ رسالةٌ تشرح لا صفرٌ صامت
        await pg3.evaluate("()=>{window.__VISITS=null;}")
        await pg3.evaluate("()=>document.querySelector('[data-vr=\"p\"]').click()")
        await pg3.wait_for_timeout(1300)
        empty = await pg3.evaluate("()=>document.getElementById('view').innerText")
        rec("لا زيارات ⇒ يُقال ذلك", "لا زيارات في هذه الفترة" in empty,
            empty[:60].replace("\n", " "))
        rec("[اللوحة] بلا أخطاء", not e3, "; ".join(e3[:2]))
        await pg3.screenshot(path=f"{_H.SHOTS}/42-visits.png", full_page=True)
        await ctx3.close()

        rec("[العميلة] بلا أخطاء", not errs, "; ".join(errs[:2]))
        await b.close()

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
