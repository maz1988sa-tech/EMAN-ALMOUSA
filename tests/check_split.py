"""الشاشة المقسومة (خدمتان): الخطّ الفاصل يُسحب، والخدمتان على اصطفافٍ واحد.

المحاكي فيه ثلاث خدمات، فتُقطع هنا إلى اثنتين كما في المنصّة الحيّة، ويُلصق
بالثانية قوسُ الملاحظة الذي تحمله في القاعدة. ويُجرَّب الحال العاديّ (ثلاث
خدمات) في آخر الطقم لئلّا ينكسر الشريط القديم.
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

MOCK_FULL = open(os.path.join(ROOT, "dev/mock-supabase.js"), encoding="utf-8").read()
DROP = "    dep(svc('s3', 'تسريحة شعر', 'mirror', 400, 40, 'تسريحة مناسبات'), 100),\n"
assert DROP in MOCK_FULL, "المحاكي تغيّر: حدّث هذا الطقم"
MOCK2 = MOCK_FULL.replace(DROP, "").replace(
    "svc('s2', 'ميك اب سهرة',", "svc('s2', 'ميك اب سهرة (يطبق خصم للمجموعات)',")
assert "(يطبق خصم للمجموعات)" in MOCK2

R = []
def rec(n, ok, note=""):
    R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

GEO = """()=>{
  const rail=document.getElementById('svcRail'),cs=[...rail.querySelectorAll('.svc')];
  const rr=rail.getBoundingClientRect(),h=rail.querySelector('.svc-hdl');
  const r=e=>e?e.getBoundingClientRect():null;
  return {split:rail.classList.contains('split'),n:cs.length,railW:rr.width,
    w:cs.map(c=>r(c).width),h:cs.map(c=>r(c).height),x:cs.map(c=>r(c).x),
    cls:cs.map(c=>c.className),
    hdl:h?{cx:r(h).x+r(h).width/2,cy:r(h).y+r(h).height/2}:null,
    lblY:cs.map(c=>{const b=c.querySelector('.svc-lbl b');return b?Math.round(r(b).bottom):null}),
    pmY:cs.map(c=>{const b=c.querySelector('.svc-lbl .pm');return b?Math.round(r(b).bottom):null}),
    names:cs.map(c=>{const b=c.querySelector('.svc-lbl b');return b?b.textContent:null}),
    h2:cs.map(c=>c.querySelector('h2')?.textContent),
    tags:cs.map(c=>c.querySelector('.svc-lbl .offtag')?.textContent||''),
    nums:cs.map(c=>c.querySelector('.svc-num')?.textContent),
    arrowShown:[...document.querySelectorAll('.arrow')].some(a=>getComputedStyle(a).display!=='none'),
    progShown:getComputedStyle(document.getElementById('svcProgress')).display!=='none',
    headShown:getComputedStyle(document.getElementById('svcHead')).display!=='none',
    rate:cs.map(c=>c.querySelector('video')?.playbackRate),
    tap:cs.map(c=>c.querySelector('.svc-tap span')?.textContent)};}"""

def frac(g, i=0): return g["w"][i] / (g["w"][0] + g["w"][1])

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**_H.CHROME, args=["--no-sandbox"])
        errs = []
        for vw, vh in ((360, 640), (390, 700), (430, 932)):
            ctx = await b.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=2)
            await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
                r.fulfill(content_type="application/javascript", body=MOCK2)))
            pg = await ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1600)
            await pg.evaluate("window.__goto(1)"); await pg.wait_for_timeout(1000)
            T = f"[{vw}x{vh}] "
            g = await pg.evaluate(GEO)

            rec(T + "خدمتان ⇒ الشاشة المقسومة والخطّ الفاصل موجود", g["split"] and g["n"] == 2 and g["hdl"] is not None)
            rec(T + "لا أسهم ولا شريط تقدّم، والرأس ظاهر", not g["arrowShown"] and not g["progShown"] and g["headShown"])
            rec(T + "النصفان متساويان عرضًا وارتفاعًا في البداية",
                abs(g["w"][0] - g["w"][1]) <= 1.5 and abs(g["h"][0] - g["h"][1]) <= 1, f"{g['w']} {g['h']}")
            rec(T + "الخدمة ١ يسارًا و٢ يمينًا", g["x"][0] < g["x"][1] and g["nums"] == ["01", "02"], f"{g['nums']}")
            rec(T + "الاسمان والسعران على خطٍّ أفقيّ واحد",
                g["lblY"][0] == g["lblY"][1] and g["pmY"][0] == g["pmY"][1], f"{g['lblY']} {g['pmY']}")
            rec(T + "الاسم يُعرض بلا قوس الملاحظة، ووسم الخصم على السهرة وحدها",
                g["names"] == ["ميك اب عروس", "ميك اب سهرة"] and g["tags"] == ["", "يُطبَّق خصم المجموعات"], f"{g['names']} {g['tags']}")
            rec(T + "الفيديوان بنصف السرعة", g["rate"] == [0.5, 0.5], f"{g['rate']}")

            async def drag_to(f_, release=True):
                gg = await pg.evaluate(GEO); rail_x = gg["hdl"]["cx"] - gg["w"][0] - 1.5
                await pg.mouse.move(gg["hdl"]["cx"], gg["hdl"]["cy"]); await pg.mouse.down()
                await pg.mouse.move(rail_x + gg["railW"] * f_, gg["hdl"]["cy"], steps=24)
                await pg.wait_for_timeout(80)
                mid = await pg.evaluate(GEO)
                if release:
                    await pg.mouse.up(); await pg.wait_for_timeout(1000)
                return mid, await pg.evaluate(GEO)

            mid, after = await drag_to(.65)
            rec(T + "السحب إلى ٦٥٪ يتبع الإصبع", abs(frac(mid) - .65) < .03, f"{frac(mid):.2f}")
            rec(T + "الترك بعيدًا عن الحافة يوقفه مكانه", abs(frac(after) - .65) < .03 and "sel" in after["cls"][0], f"{frac(after):.2f}")
            mid, after = await drag_to(.88)
            rec(T + "الترك قريبًا من الحافة يُكمل وحده", frac(after) > .895, f"{frac(after):.2f}")
            mid, after = await drag_to(.30)
            rec(T + "السحب للجهة الأخرى ثم الترك بعيدًا يوقفه", abs(frac(after) - .30) < .03 and "sel" in after["cls"][1], f"{frac(after):.2f}")
            mid, after = await drag_to(.08)
            rec(T + "ويُكمل نحو الخدمة الثانية قرب الحافة", frac(after, 1) > .895, f"{frac(after,1):.2f}")

            # الضغط: المكبَّر يعيد الاثنين، والصغير يكبّره
            await pg.click("#svcRail .svc.sel", position={"x": 60, "y": 200}); await pg.wait_for_timeout(1000)
            g = await pg.evaluate(GEO)
            rec(T + "الضغط على المكبَّر يعيد الفيديوين", abs(g["w"][0] - g["w"][1]) <= 1.5, f"{g['w']}")
            await pg.click("#svcRail .svc >> nth=1", position={"x": 60, "y": 200}); await pg.wait_for_timeout(1000)
            g = await pg.evaluate(GEO)
            rec(T + "الضغط على الصغير يكبّره", frac(g, 1) > .895, f"{frac(g,1):.2f}")

            # الاختيار والسلّة والتفاصيل
            ov = await pg.evaluate("""()=>{const c=document.querySelector('#svcRail .svc.sel'),b=c.querySelector('.svc-body'),
              cr=c.getBoundingClientRect();const kids=[...b.children].filter(e=>e.offsetParent!==null);
              return {over:Math.round(Math.max(...kids.map(e=>e.getBoundingClientRect().bottom))-cr.bottom),
                      clip:b.scrollHeight-b.clientHeight,vis:getComputedStyle(b).visibility,
                      side:Math.round(b.getBoundingClientRect().right-cr.right),
                      sideL:Math.round(cr.left-b.getBoundingClientRect().left)}}""")
            rec(T + "تفاصيل الخدمة المكبَّرة ظاهرة ولا تفيض", ov["vis"] == "visible" and ov["over"] <= 0 and ov["clip"] <= 0, f"{ov}")
            await pg.click("#svcRail .svc.sel [data-pick]"); await pg.wait_for_timeout(700)
            cart = await pg.evaluate("""()=>{const c=document.querySelector('#svcRail .svc.sel'),cb=document.getElementById('svcCart'),
              body=c.querySelector('.svc-body'),kids=[...body.children].filter(e=>e.offsetParent!==null);
              return {on:cb.classList.contains('on'),total:document.getElementById('cartTotal').textContent,
                      gap:Math.round(cb.getBoundingClientRect().top-Math.max(...kids.map(e=>e.getBoundingClientRect().bottom))),
                      picked:c.classList.contains('picked'),
                      tap:[...document.querySelectorAll('#svcRail .svc-tap span')].map(s=>s.textContent)}}""")
            rec(T + "الاختيار يظهر في الشريط والإجمالي صحيح (٦٠٠ لخدمةٍ واحدة)",
                cart["on"] and cart["total"].replace(",", "") == "600", f"{cart}")
            rec(T + "التفاصيل لا يغطّيها شريط السلّة", cart["gap"] >= 0, f"gap={cart['gap']}")
            rec(T + "الشريحة المختارة تقول «تمت الإضافة» وهي مصغّرة", cart["tap"][1].startswith("تمت الإضافة"), f"{cart['tap']}")
            await pg.click("#svcRail .svc.sel .q-plus"); await pg.wait_for_timeout(300)
            tot = await pg.evaluate("document.getElementById('cartTotal').textContent")
            rec(T + "زرّ + يزيد العدد ويتبعه الإجمالي (٢ × ٨٠٠ − خصم المجموعات)", tot.replace(",", "") == "1000", tot)
            # الفيديو والسحب الأفقي على مستوى الشاشة لا يخلطان
            before = (await pg.evaluate(GEO))["w"]
            await pg.evaluate("""()=>{const mk=(x,y)=>new Touch({identifier:1,target:document.body,clientX:x,clientY:y});
              document.dispatchEvent(new TouchEvent('touchstart',{touches:[mk(250,300)],changedTouches:[mk(250,300)],bubbles:true}));
              document.dispatchEvent(new TouchEvent('touchend',{touches:[],changedTouches:[mk(60,305)],bubbles:true}));}""")
            await pg.wait_for_timeout(900)
            after = (await pg.evaluate(GEO))["w"]
            rec(T + "سحبة الشاشة الأفقيّة العامّة لا تبدّل الخدمة في الشاشة المقسومة",
                all(abs(a - b_) < 1 for a, b_ in zip(before, after)), f"{before} {after}")
            # لوحة المفاتيح
            await pg.focus("#svcRail .svc-hdl"); w0 = (await pg.evaluate(GEO))["w"][0]
            await pg.keyboard.press("ArrowRight"); await pg.wait_for_timeout(900)
            w1 = (await pg.evaluate(GEO))["w"][0]
            rec(T + "مفتاح السهم يحرّك الفاصل", w1 > w0 + 5, f"{w0:.0f}→{w1:.0f}")
            if (vw, vh) == (390, 700):
                await pg.evaluate("window.__pick(0,0);window.__pick(1,0)"); await pg.wait_for_timeout(500)
                await pg.click("#svcRail .svc.sel", position={"x": 60, "y": 200}); await pg.wait_for_timeout(900)
                await pg.screenshot(path=f"{_H.SHOTS}/split-mid.png")
                await pg.mouse.move(vw / 2, 320); await pg.mouse.down(); await pg.mouse.move(vw * .66, 320, steps=12); await pg.mouse.up()
                await pg.wait_for_timeout(900)
                await pg.screenshot(path=f"{_H.SHOTS}/split-partial.png")
            await ctx.close()

        # الحال العاديّ: ثلاث خدمات ⇒ الشريط القديم كما كان
        ctx = await b.new_context(viewport={"width": 390, "height": 700}, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK_FULL)))
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1600)
        await pg.evaluate("window.__goto(1)"); await pg.wait_for_timeout(900)
        g = await pg.evaluate(GEO)
        rec("[٣ خدمات] لا شاشة مقسومة: الشريط القديم والأسهم والتقدّم", not g["split"] and g["n"] == 3 and g["arrowShown"] and g["progShown"] and not g["headShown"])
        await pg.evaluate("window.__svc(1)"); await pg.wait_for_timeout(800)
        tx = await pg.evaluate("getComputedStyle(document.getElementById('svcRail')).transform")
        rec("[٣ خدمات] التنقّل بين الخدمات يعمل كما كان", tx != "none" and "-" in tx, tx)
        await ctx.close()
        await b.close()
        rec("بلا أخطاء في وحدة التحكّم", not errs, "; ".join(errs[:3]))

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
