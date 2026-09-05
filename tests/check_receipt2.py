# -*- coding: utf-8 -*-
"""حارس الإيصال بعد الثغرة — ما تراه العميلة وما لا تُخبَر به.

المنطق يُفحص في القاعدة (0019). وهنا الواجهة: نافذةُ الفحص في منتصف
الشاشة، والرفضُ بكلمةٍ واحدة لا سبب معها، وأنّ الصورة المرفوضة تُزال
فلا يُفتح الإرسال عليها.
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

# صورة صغيرة صالحة تقوم مقام الإيصال
PNG = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
       "IQAAAABJRU5ErkJggg==")

async def to_pay(pg):
    """نفس المسار الذي يسلكه check_form: خدمة ← يوم ← وقت ← بيانات ← دفع."""
    await pg.evaluate("()=>{window.__pick(1,3); window.__goto(2);}")
    await pg.wait_for_timeout(1200)
    await pg.evaluate("()=>{const b=[...document.querySelectorAll('#week button.day:not([disabled])')];"
                      " if(b.length) b[b.length>2?2:0].click();}")
    await pg.wait_for_timeout(900)
    await pg.evaluate("()=>{const t=[...document.querySelectorAll('#times [data-slot]')];"
                      " if(t.length) t[0].click();}")
    await pg.wait_for_timeout(600)
    await pg.click("#confirmBtn"); await pg.wait_for_timeout(900)
    await pg.evaluate("""()=>{
      const set=(id,v)=>{const e=document.getElementById(id); if(e){e.value=v;
        e.dispatchEvent(new Event('input',{bubbles:true}));
        e.dispatchEvent(new Event('blur',{bubbles:true}));}};
      set('nm','عميلة تجربة'); set('ph','0501234567');
      set('locTxt','حي النخيل'); set('loc','https://maps.app.goo.gl/abc');}""")
    await pg.wait_for_timeout(500)
    await pg.evaluate("()=>{const b=document.getElementById('toPay'); if(b && !b.disabled) b.click();}")
    await pg.wait_for_timeout(800)

async def attach(pg):
    await pg.set_input_files("#rcptFile", {
        "name": "receipt.png", "mimeType": "image/png",
        "buffer": __import__("base64").b64decode(PNG)})

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(
            **_H.CHROME,
            args=["--no-sandbox"])

        async def fresh(verdict, delay=0):
            ctx = await b.new_context(viewport={"width": 390, "height": 800},
                                      has_touch=True, is_mobile=True, device_scale_factor=2)
            await ctx.route("**/assets/vendor/supabase.js",
                            lambda r: asyncio.ensure_future(r.fulfill(
                                content_type="application/javascript", body=MOCK)))
            pg = await ctx.new_page()
            errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.add_init_script(
                f"window.__RECEIPT__={verdict!r}; window.__ocrReply={{ok:true,textLen:120}};"
                f"window.__RECEIPT_DELAY__={delay};")
            await pg.goto(f"http://127.0.0.1:{PORT}/index.html")
            await pg.wait_for_timeout(1600)
            return ctx, pg, errs

        # ── ١) نافذة الفحص تظهر في المنتصف أثناء الفحص
        ctx, pg, errs = await fresh("ok", delay=1200)
        await to_pay(pg)
        rec("وصلنا لوحة الدفع",
            await pg.evaluate("()=>!document.querySelector('.pane[data-pane=\"pay\"]').hidden"
                              " || document.querySelector('.pane[data-pane=\"pay\"]').classList.contains('on')"))
        # الفحص مؤخَّرٌ في المحاكي ١٢٠٠ مللي كما يستغرق الحقيقيّ ثوانيَ،
        # فتُقرأ الحال وهي قائمة لا بعد انصرافها.
        await attach(pg)
        await pg.wait_for_timeout(450)
        mid = await pg.evaluate("""()=>{const m=document.getElementById('rcptModal');
          const cs=getComputedStyle(m); const box=m.querySelector('.box').getBoundingClientRect();
          const app=document.getElementById('app').getBoundingClientRect();
          return {open:m.classList.contains('open'), vis:cs.visibility, op:Number(cs.opacity),
                  title:document.getElementById('rcptModalTitle').textContent.trim(),
                  spin:!document.getElementById('rcptSpin').hidden,
                  okBtn:!document.getElementById('rcptModalOk').hidden,
                  cx:Math.round(box.left+box.width/2), cy:Math.round(box.top+box.height/2),
                  ax:Math.round(app.left+app.width/2), ay:Math.round(app.top+app.height/2),
                  z:cs.zIndex};}""")
        rec("نافذة «جارٍ فحص الإيصال» تُرى أثناء الفحص",
            mid["open"] and mid["vis"] == "visible" and mid["op"] > .9
            and "جارٍ فحص" in mid["title"], f'{mid["title"]} / {mid["vis"]} / {mid["op"]}')
        rec("وهي في منتصف الشاشة",
            abs(mid["cx"] - mid["ax"]) <= 2 and abs(mid["cy"] - mid["ay"]) <= 24,
            f'({mid["cx"]},{mid["cy"]}) مقابل ({mid["ax"]},{mid["ay"]})')
        rec("ومعها حركةٌ تدلّ على العمل، بلا زرٍّ يُضغط", mid["spin"] and not mid["okBtn"])
        rec("وفوق كل شيء", int(mid["z"]) >= 60, mid["z"])
        await pg.screenshot(path=f"{_H.SHOTS}/40-checking.png")

        await pg.wait_for_timeout(1600)
        after = await pg.evaluate("""()=>({open:document.getElementById('rcptModal').classList.contains('open'),
          send:document.getElementById('sendBooking').disabled,
          path:true})""")
        rec("وبعد القبول تنصرف النافذة", not after["open"])
        rec("والإرسال مفتوح", not after["send"])
        rec("[قبول] بلا أخطاء", not errs, "; ".join(errs[:2]))
        await ctx.close()

        # ── ٢) الرفض: كلمة واحدة، بلا سبب
        ctx, pg, errs = await fresh("bad")
        await to_pay(pg)
        await attach(pg)
        await pg.wait_for_timeout(2600)
        bad = await pg.evaluate("""()=>{const m=document.getElementById('rcptModal');
          return {open:m.classList.contains('open'),
                  title:document.getElementById('rcptModalTitle').textContent.trim(),
                  note:document.getElementById('rcptModalNote').textContent.trim(),
                  all:m.innerText,
                  okBtn:!document.getElementById('rcptModalOk').hidden,
                  mark:!document.getElementById('rcptBad').hidden,
                  send:document.getElementById('sendBooking').disabled,
                  prev:document.getElementById('rcptPrev').hidden,
                  wa:!document.getElementById('rcptModalWa').hidden};}""")
        rec("الرفض يظهر بنافذة في المنتصف", bad["open"] and bad["mark"])
        rec("ونصّها «الإيصال غير صحيح»", bad["title"] == "الإيصال غير صحيح", bad["title"])
        LEAK = ["عربون", "مبلغ", "آيبان", "ايبان", "IBAN", "الحساب", "رقم", "ريال", "﷼", "لم نجد"]
        leaked = [w for w in LEAK if w in bad["all"]]
        rec("ولا تُفصح عن السبب", not leaked, "تسرّب: " + str(leaked))
        rec("وفيها زرّ «حسنًا»", bad["okBtn"])
        rec("والصورة المرفوضة تُزال", bad["prev"])
        rec("والإرسال مقفل", bad["send"])
        rec("ولا يُعرض واتساب من أوّل مرّة", not bad["wa"])
        await pg.screenshot(path=f"{_H.SHOTS}/40-bad.png")

        await pg.evaluate("()=>document.getElementById('rcptModalOk').click()")
        await pg.wait_for_timeout(400)
        rec("«حسنًا» تُغلق النافذة",
            not await pg.evaluate("()=>document.getElementById('rcptModal').classList.contains('open')"))

        # محاولة ثانية فاشلة ⇒ يُعرض التواصل، وما زال بلا سبب
        await attach(pg)
        await pg.wait_for_timeout(2600)
        two = await pg.evaluate("""()=>({wa:!document.getElementById('rcptModalWa').hidden,
          href:document.getElementById('rcptModalWa').getAttribute('href')||'',
          all:document.getElementById('rcptModal').innerText})""")
        rec("بعد محاولتين يُعرض التواصل", two["wa"] and "wa.me" in two["href"], two["href"][:34])
        # التصادم الذي وقع: ‎.wa‎ صنفٌ مأخوذ لبطاقةٍ طينية، فورثت الوصلةُ
        # خلفيّتَها وبقي نصُّها طينيًّا فاختفى. يُقاس اللونان لا الصنف.
        ink = await pg.evaluate("""()=>{const a=document.getElementById('rcptModalWa');
          const cs=getComputedStyle(a); const b=document.getElementById('rcptModalOk');
          const px=(c)=>c.replace(/[^\\d.,]/g,'').split(',').map(Number).slice(0,3);
          const lum=(c)=>{const [r,g,bl]=px(c).map(v=>{v/=255;
            return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4);});
            return .2126*r+.7152*g+.0722*bl;};
          const box=a.getBoundingClientRect();
          return {fg:cs.color, bg:cs.backgroundColor,
                  ratio:(()=>{const bgc = cs.backgroundColor==='rgba(0, 0, 0, 0)'
                      ? getComputedStyle(a.closest('.box')).backgroundColor : cs.backgroundColor;
                    const l1=lum(cs.color), l2=lum(bgc);
                    return Math.round(((Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05))*100)/100;})(),
                  h:Math.round(box.height), w:Math.round(box.width),
                  belowOk: box.top >= b.getBoundingClientRect().bottom - 1,
                  okFilled: getComputedStyle(b).backgroundColor};}""")
        rec("ونصّها يُقرأ — تباين ٤٫٥ فأعلى", ink["ratio"] >= 4.5,
            f'{ink["ratio"]}:1 — {ink["fg"]} على {ink["bg"]}')
        rec("ولا ترث خلفيّة بطاقة التواصل",
            ink["bg"] in ("rgba(0, 0, 0, 0)", "transparent"), ink["bg"])
        rec("وهي دون «حسنًا» رتبةً وموضعًا",
            ink["belowOk"] and ink["okFilled"] != ink["bg"], f'below={ink["belowOk"]}')
        rec("ومساحتها تكفي للضغط", ink["h"] >= 44 and ink["w"] >= 120, f'{ink["w"]}×{ink["h"]}')
        await pg.screenshot(path=f"{_H.SHOTS}/41-wa.png")
        rec("وما زال بلا سبب", not [w for w in LEAK if w in two["all"]])
        rec("[رفض] بلا أخطاء", not errs, "; ".join(errs[:2]))
        await ctx.close()

        # ── ٣) الانتظار ليس رفضًا
        ctx, pg, errs = await fresh("wait")
        await to_pay(pg)
        await attach(pg)
        await pg.wait_for_timeout(2600)
        w = await pg.evaluate("""()=>({open:document.getElementById('rcptModal').classList.contains('open'),
          send:document.getElementById('sendBooking').disabled,
          chk:document.getElementById('rcptChk').textContent.trim(),
          prev:document.getElementById('rcptPrev').hidden})""")
        rec("تعذّر الفحص لا يُتّهم صاحبته", not w["open"] and not w["prev"], w["chk"])
        rec("ولا يُقفل الإرسال — الخادم يحكم عند الإرسال", not w["send"])
        rec("[انتظار] بلا أخطاء", not errs, "; ".join(errs[:2]))
        await ctx.close()

        # ── ٤) الحكم يُطلب من القاعدة لا يُحسب في المتصفّح
        ctx, pg, errs = await fresh("ok")
        await to_pay(pg)
        await attach(pg)
        await pg.wait_for_timeout(2400)
        calls = await pg.evaluate("()=>(window.__CHECKS||[])")
        rec("المتصفّح يسأل القاعدة عن الحكم", len(calls) >= 1, f"{len(calls)} نداءً")
        rec("ويرسل الخدمات لا المبلغ",
            bool(calls) and 'p_service_ids' in calls[-1] and 'p_need' not in calls[-1]
            and 'amount' not in str(calls[-1]),
            str(list(calls[-1].keys()) if calls else []))
        await ctx.close()
        await b.close()

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
