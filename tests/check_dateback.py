# -*- coding: utf-8 -*-
"""زرّ «عودة» في خطوة الموعد (المقترح «أ» المعتمد، ١١ نوفمبر ٢٠٢٦).

كان الرجوع إلى الخدمات كلمة «تغيير» الصغيرة في البطاقة أو السحب للأسفل،
فطلب صاحب المشروع زرًّا في الشريط بين الإجمالي و«متابعة». يحرس هذا الطقم:
موضعَه وترتيبه، وارتفاعَه وحوافَّه المشتركة مع جاريه، وأنّ الإجمالي لا يضيق
عن رقمه حتى بخمس خانات، وأنّ شكله شكلُ «تعديل» في خطوة التأكيد، وأنّ الرجوع
لا يمسح الموعد المختار.
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
PORT = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start()
MOCK = open(os.path.join(ROOT, "dev/mock-supabase.js"), encoding="utf-8").read()

R = []
def rec(n, ok, note=""):
    R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

GEOM = r"""()=>{
  const r=(e)=>{const b=e.getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height};};
  const scr=document.querySelectorAll('#deck .screen')[2], fb=scr.querySelector('.footbar');
  const total=fb.querySelector('.total'), tb=total.querySelector('b');
  const back=document.getElementById('dateBack'), cta=document.getElementById('toConfirm');
  const rg=document.createRange(); rg.selectNodeContents(tb);
  return {order:[...fb.children].map(k=>k.id||k.className),
    total:r(total), num:r({getBoundingClientRect:()=>rg.getBoundingClientRect()}),
    back:r(back), cta:r(cta), span:r(cta.querySelector('span')), svg:r(cta.querySelector('svg')),
    over:fb.scrollWidth-fb.clientWidth, backDisabled:back.disabled, ctaDisabled:cta.disabled,
    label:back.getAttribute('aria-label'), text:back.innerText.trim()};}"""

LONG = r"""(t)=>{const b=document.getElementById('total1'); b.firstChild.textContent=t;}"""

async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(**_H.CHROME, args=["--no-sandbox"])
        for w, h in ((360, 640), (393, 760), (440, 794)):
            ctx = await b.new_context(viewport={"width": w, "height": h}, has_touch=True, is_mobile=True, device_scale_factor=2)
            await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
                r.fulfill(content_type="application/javascript", body=MOCK)))
            pg = await ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1600)
            await pg.evaluate("()=>window.__pick(1,2)"); await pg.wait_for_timeout(300)
            await pg.evaluate("()=>window.__goto(2)"); await pg.wait_for_timeout(1300)
            g = await pg.evaluate(GEOM)
            T = f"[{w}] "
            rec(T + "الزرّ في شريط الموعد بين الإجمالي و«متابعة»", g["order"] == ["total", "dateBack", "toConfirm"], str(g["order"]))
            rec(T + "على الشاشة: الإجمالي يمينًا ثمّ «عودة» ثمّ «متابعة»",
                g["total"]["x"] >= g["back"]["x"] + g["back"]["w"] + 9 and g["back"]["x"] >= g["cta"]["x"] + g["cta"]["w"] + 9,
                f"total.x={g['total']['x']:.1f} back={g['back']['x']:.1f}+{g['back']['w']:.1f} cta={g['cta']['x']:.1f}+{g['cta']['w']:.1f}")
            same = (abs(g["back"]["h"] - 54) < .5 and abs(g["cta"]["h"] - 54) < .5 and abs(g["total"]["h"] - 54) < .5
                    and abs(g["back"]["y"] - g["cta"]["y"]) < .5 and abs(g["total"]["y"] - g["cta"]["y"]) < .5)
            rec(T + "الارتفاع ٥٤ للثلاثة، والحافّتان العليا والسفلى مشتركتان", same,
                f"h={g['total']['h']:.1f}/{g['back']['h']:.1f}/{g['cta']['h']:.1f} y={g['total']['y']:.1f}/{g['back']['y']:.1f}/{g['cta']['y']:.1f}")
            rec(T + "عرض «عودة» ٨٤", abs(g["back"]["w"] - 84) < .5, f"{g['back']['w']:.2f}")
            rec(T + "«متابعة» يسع كلمته وسهمه", g["cta"]["w"] >= 120 and g["span"]["x"] >= g["svg"]["x"] + g["svg"]["w"] + 8,
                f"cta={g['cta']['w']:.1f} span.x={g['span']['x']:.1f} svg.right={g['svg']['x'] + g['svg']['w']:.1f}")
            rec(T + "الرقم لا يلامس «عودة»", g["num"]["x"] >= g["back"]["x"] + g["back"]["w"] + 9,
                f"num.x={g['num']['x']:.1f} back.right={g['back']['x'] + g['back']['w']:.1f}")
            rec(T + "الشريط لا يفيض أفقيًّا", g["over"] <= 0, f"over={g['over']}")
            keep = await pg.evaluate("()=>document.getElementById('total1').firstChild.textContent")
            await pg.evaluate(LONG, "10,500"); await pg.wait_for_timeout(100)
            g5 = await pg.evaluate(GEOM)
            await pg.evaluate(LONG, keep)
            rec(T + "وبخمس خانات (10,500) لا يضيق عمود الإجمالي عن رقمه",
                g5["num"]["x"] >= g5["back"]["x"] + g5["back"]["w"] + 9 and g5["over"] <= 0 and g5["cta"]["w"] >= 110,
                f"num.x={g5['num']['x']:.1f} back.right={g5['back']['x'] + g5['back']['w']:.1f} cta={g5['cta']['w']:.1f}")
            if w == 440:
                rec("قبل اختيار الموعد: «عودة» يعمل و«متابعة» معطّل", not g["backDisabled"] and g["ctaDisabled"], "")
                rec("اسمه لقارئ الشاشة يحوي كلمته الظاهرة", g["text"] == "عودة" and g["label"] == "عودة إلى الخدمات",
                    f"{g['text']!r} / {g['label']!r}")
                st = await pg.evaluate("""()=>{const pick=(e)=>{const c=getComputedStyle(e);return [c.height,c.borderTopWidth,
                    c.borderTopStyle,c.borderTopColor,c.backgroundColor,c.borderRadius,c.fontSize,c.color,c.columnGap].join('|');};
                    return [pick(document.getElementById('dateBack')),pick(document.getElementById('editBack'))];}""")
                rec("شكله شكلُ «تعديل» في خطوة التأكيد", st[0] == st[1], st[0])
                await pg.screenshot(path=f"{_H.SHOTS}/dateback-{w}.png")
                # الرجوع لا يمسح الموعد: يوم ووقت، ثمّ «عودة»، ثمّ «متابعة» من السلّة
                await pg.eval_on_selector("#week .day:not(.blank):not([disabled])", "e=>e.click()"); await pg.wait_for_timeout(1000)
                await pg.eval_on_selector("#times button:not([disabled])", "e=>e.click()"); await pg.wait_for_timeout(400)
                chosen = await pg.evaluate("()=>document.getElementById('dateChipLabel').textContent")
                totalBefore = await pg.evaluate("()=>document.getElementById('total1').innerText")
                await pg.click("#dateBack"); await pg.wait_for_timeout(900)
                at = await pg.evaluate("()=>({screen:document.getElementById('app').dataset.screen,cart:document.getElementById('cartTotal').innerText})")
                rec("«عودة» ينقل إلى شاشة الخدمات والسلّة كما هي", at["screen"] == "1" and at["cart"] in totalBefore, f"{at} / {totalBefore!r}")
                await pg.click("#cartGo"); await pg.wait_for_timeout(900)
                kept = await pg.evaluate("""()=>({screen:document.getElementById('app').dataset.screen,
                    chip:document.getElementById('dateChipLabel').textContent, chipShown:!document.getElementById('dateChip').hidden,
                    cta:document.getElementById('toConfirm').disabled})""")
                rec("والموعد المختار باقٍ بعد الرجوع، و«متابعة» يعمل",
                    kept["screen"] == "2" and kept["chipShown"] and kept["chip"] == chosen and not kept["cta"], f"{kept} / {chosen!r}")
                await pg.focus("#dateBack"); await pg.keyboard.press("Enter"); await pg.wait_for_timeout(900)
                kb = await pg.evaluate("()=>document.getElementById('app').dataset.screen")
                rec("ويعمل من لوحة المفاتيح", kb == "1", f"screen={kb}")
            await ctx.close()
        await b.close()
    rec("لا أخطاء في الصفحة", not errs, "; ".join(errs[:2]))

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
