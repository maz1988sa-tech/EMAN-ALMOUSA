# -*- coding: utf-8 -*-
"""الفراشة زرًّا، وحجز المجموعة ببطاقةٍ كاملة لكلِّ عميلة.

المطلوب صريحٌ: نفس حقول الحجز الفردي — بما فيها العربون — لكلِّ واحدة،
وورقةٌ لا تُغلَق بينهنّ، وحفظٌ واحد يوزّعهنّ.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright

ROOT = str(_H.ROOT)
OUT  = f"{_H.SHOTS}"
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
MOCK = open(os.path.join(ROOT, "dev/mock-supabase.js"), encoding="utf-8").read()

ok = fail = 0
def rec(n, c, x=""):
    global ok, fail
    if c: ok += 1;   print(f"PASS {n}" + (f" — {x}" if x else ""))
    else: fail += 1; print(f"FAIL {n} — {x}")

# حقول الحجز الفردي التي يجب أن تتكرّر في كلِّ بطاقة
FIELDS = ["اسم العميلة", "رقم الجوال", "الخدمات والأشخاص", "التاريخ", "الوقت",
          "الحي والمدينة", "رابط خرائط قوقل", "العربون المستلَم", "المتبقّي"]

async def main():
  async with async_playwright() as p:
    b = await p.chromium.launch(
        **_H.CHROME,
        args=["--no-sandbox"])
    ctx = await b.new_context(viewport={"width": 430, "height": 932}, device_scale_factor=2)
    await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
        r.fulfill(content_type="application/javascript", body=MOCK)))
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "404" not in m.text else None)
    await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
    await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(2000)

    # ── الفراشة زرًّا في سطر التحيّة ──────────────────────────────
    fab = await pg.evaluate("""()=>{const e=document.getElementById('addFab');
      if(!e) return null; const r=e.getBoundingClientRect(); const cs=getComputedStyle(e);
      const h1=document.querySelector('.greet h1'); const hr=h1.getBoundingClientRect();
      const gr=document.querySelector('.greet').getBoundingClientRect();
      const cp=document.getElementById('baytCopy')?.getBoundingClientRect();
      const hits=(a,b)=>!!b && !(a.bottom<=b.top||a.top>=b.bottom||a.right<=b.left||a.left>=b.right);
      return {tag:e.tagName, pos:cs.position, w:Math.round(r.width), h:Math.round(r.height),
              aria:e.getAttribute('aria-label'),
              inGreet: r.top>=gr.top-1 && r.bottom<=gr.bottom+1,
              besideName: r.right <= hr.left + 1,
              centred: (()=>{const a=document.querySelector('.greet-act');
                if(!a) return null; const ar=a.getBoundingClientRect();
                return {dx: Math.abs((r.left+r.right)/2 - (ar.left+ar.right)/2),
                        dy: Math.abs((r.top+r.bottom)/2 - (ar.top+ar.bottom)/2)};})(),
              overlapsName: hits(r, hr), overlapsCopy: hits(r, cp),
              wings:e.querySelectorAll('.w').length,
              anim:getComputedStyle(e.querySelector('.wl')).animationName,
              mark: !!document.querySelector('.bmark')};}""")
    rec("الفراشة زرٌّ لا زينة", fab and fab["tag"] == "BUTTON", str(fab and fab["tag"]))
    rec("تحمل اسمًا لقارئ الشاشة", fab and fab["aria"] == "إضافة حجز", str(fab and fab["aria"]))
    rec("مساحة لمسٍ كافية", fab and fab["w"] >= 46 and fab["h"] >= 46,
        f'{fab and fab["w"]}×{fab and fab["h"]}')
    rec("داخل بطاقة التحيّة", fab and fab["inGreet"], "")
    rec("بجانب الاسم لا فوقه", fab and fab["besideName"], "")
    rec("متوسّطًا الفراغ الباقي طولًا وعرضًا",
        fab and fab["centred"] and fab["centred"]["dx"] <= 1 and fab["centred"]["dy"] <= 1,
        str(fab and fab["centred"]))
    rec("لا تغطّي الاسم ولا زرّ نسخ البيت",
        fab and not fab["overlapsName"] and not fab["overlapsCopy"], "")
    rec("ليست قرصًا عائمًا", fab and fab["pos"] != "fixed", str(fab and fab["pos"]))
    rec("ولا شعار مكرَّر بجانب الاسم", fab and not fab["mark"], "")
    rec("لها جناحان يتنفّسان", fab and fab["wings"] == 2 and "breathe" in (fab["anim"] or ""),
        str(fab and fab["anim"]))

    # تمضي مع الصفحة: في آخرها زرُّ إضافةٍ آخر يغني عن تتبّعها
    t0 = await pg.evaluate("()=>document.getElementById('addFab').getBoundingClientRect().top")
    await pg.evaluate("()=>scrollTo(0, 500)"); await pg.wait_for_timeout(800)
    t1 = await pg.evaluate("()=>document.getElementById('addFab').getBoundingClientRect().top")
    rec("تمضي مع الصفحة ولا تتبع العين", t1 < t0 - 100, f"{round(t0)} → {round(t1)}")
    rec("وفي آخر الصفحة زرُّ إضافةٍ آخر",
        await pg.evaluate("()=>!!document.getElementById('btnNew')"), "")
    await pg.evaluate("()=>scrollTo(0, 0)"); await pg.wait_for_timeout(500)

    # ── الاختيار ─────────────────────────────────────────────────
    await pg.click("#addFab"); await pg.wait_for_timeout(700)
    k = await pg.evaluate("""()=>({t:document.getElementById('sheetTitle')?.textContent.trim(),
      one:document.getElementById('k-one')?.innerText.trim(),
      many:document.getElementById('k-many')?.innerText.trim(),
      fab:getComputedStyle(document.getElementById('addFab')).opacity})""")
    rec("الضغطة تفتح الاختيار", k["t"] == "حجز جديد", str(k["t"]))
    rec("حجزٌ واحد أو عدّة حجوزات",
        "واحد" in (k["one"] or "") and "عدّة حجوزات" in (k["many"] or ""),
        f'{k["one"]!r} / {k["many"]!r}')
    rec("والورقة تعلو الزرّ فلا يزاحمها",
        await pg.evaluate("()=>{const s=document.getElementById('sheet');"
                          "const f=document.getElementById('addFab');"
                          "if(s.hidden) return false;"
                          "return +getComputedStyle(s).zIndex > (+getComputedStyle(f).zIndex||0);}"),
        "")

    # ── ورقة المجموعة ────────────────────────────────────────────
    await pg.click("#k-many"); await pg.wait_for_timeout(700)
    st = await pg.evaluate("""()=>({t:document.getElementById('sheetTitle')?.textContent.trim(),
      cards:document.querySelectorAll('.pcard').length,
      labels:[...document.querySelectorAll('.pcard.open .label')].map(x=>x.textContent.trim()),
      steppers:document.querySelectorAll('.pcard.open .stepper').length,
      occ:!!document.getElementById('g-label')})""")
    rec("ورقة الإدخال المتعدّد تفتح", st["t"] == "عدّة حجوزات", str(st["t"]))
    rec("تبدأ ببطاقةٍ واحدة مفتوحة", st["cards"] == 1, str(st["cards"]))
    # ليست مناسبةً واحدة: لا اسم لها ولا يجمعها عنوان.
    rec("بلا اسم مناسبة", not st["occ"], "")
    got = [l.split(" (")[0] for l in st["labels"]]
    missing = [f for f in FIELDS if f not in got]
    rec("البطاقة فيها كلُّ حقول الحجز الفردي", not missing, "ناقص: " + "، ".join(missing) if missing else "")
    rec("وعدّادٌ لكلِّ خدمة", st["steppers"] == 3, str(st["steppers"]))

    # العدّاد والسعر والعربون
    # الخدمة المؤهَّلة للخصم لا الأولى: العروس خارج الخصم عمدًا.
    svc = await pg.evaluate("""()=>{const s=(window.__S&&window.__S.services)||null; return 's2';}""")
    i = "0"
    await pg.click(f'[data-gq="{i}:{svc}:1"]'); await pg.wait_for_timeout(300)
    v1 = await pg.evaluate("()=>document.querySelector('.pcard.open .leader .v').textContent.trim()")
    rec("العدّاد يبني الإجمالي", v1.startswith("600"), v1)
    await pg.click(f'[data-gq="{i}:{svc}:1"]'); await pg.wait_for_timeout(300)
    v2 = await pg.evaluate("""()=>({sum:document.querySelector('.pcard.open .leader .v').textContent.trim(),
      disc:[...document.querySelectorAll('.pcard.open .hint')].map(x=>x.textContent.trim())})""")
    rec("وخصم المجموعة يظهر من شخصين — ٦٠٠×٢−٢٠٠",
        v2["sum"].startswith("1,000") and any("خصم المجموعة" in d for d in v2["disc"]), str(v2))

    await pg.fill(f'[data-gf="{i}:dep"]', "400"); await pg.wait_for_timeout(350)
    rest = await pg.evaluate("""()=>document.querySelector('.pcard.open [id^="gp-rest-"]')?.textContent.trim()""")
    rec("والمتبقّي يُحسب في البطاقة — ١٠٠٠−٤٠٠", (rest or "").startswith("600"), str(rest))

    # ── عميلةٌ ثانية: المتكرّر يُنسَخ ─────────────────────────────
    await pg.fill(f'[data-gf="{i}:nm"]', "رانيا العتيبي")
    await pg.fill(f'[data-gf="{i}:ph"]', "0501234567")
    await pg.fill(f'[data-gf="{i}:loc"]', "قاعة غرناطة")
    await pg.fill(f'[data-gf="{i}:map"]', "https://maps.app.goo.gl/x")
    await pg.wait_for_timeout(300)
    await pg.click("#g-add"); await pg.wait_for_timeout(700)
    two = await pg.evaluate("""()=>{const o=document.querySelector('.pcard.open');
      const g=s=>o.querySelector(s)?.value;
      return {cards:document.querySelectorAll('.pcard').length,
              open:document.querySelectorAll('.pcard.open').length,
              nm:g('[data-gf$=":nm"]'), ph:g('[data-gf$=":ph"]'),
              loc:g('[data-gf$=":loc"]'), map:g('[data-gf$=":map"]'),
              date:g('[data-gf$=":date"]'), time:g('[data-gf$=":time"]'),
              dep:g('[data-gf$=":dep"]'),
              folded:document.querySelector('.pcard:not(.open) .pt')?.textContent.trim()};}""")
    rec("البطاقة الثانية تُفتح والأولى تنطوي", two["cards"] == 2 and two["open"] == 1, str(two["cards"]))
    rec("والمطويّة تُظهر الاسم", two["folded"] == "رانيا العتيبي", str(two["folded"]))
    rec("الحيّ يبدأ خاليًا لا منسوخًا", two["loc"] == "", repr(two["loc"]))
    rec("ورابط الخريطة كذلك", two["map"] == "", repr(two["map"]))
    rec("والاسم والجوال يبدآن فارغين", two["nm"] == "" and two["ph"] == "", f'{two["nm"]!r}/{two["ph"]!r}')
    rec("والعربون يبدأ فارغًا", two["dep"] in ("", "0"), str(two["dep"]))
    rec("والوقت يبدأ من الافتراضي لا من انتهاء السابقة", two["time"] == "16:00", str(two["time"]))

    # النسخ صار طلبًا صريحًا لا افتراضًا صامتًا
    j0 = await pg.evaluate("""()=>document.querySelector('.pcard.open [data-gcp]')?.dataset.gcp""")
    rec("وفيها زرُّ نسخٍ صريح من السابقة", j0 is not None, str(j0))
    if j0 is not None:
        await pg.click(f'[data-gcp="{j0}"]'); await pg.wait_for_timeout(500)
        cp = await pg.evaluate("""()=>{const o=document.querySelector('.pcard.open');
          const g=s=>o.querySelector(s)?.value;
          return {loc:g('[data-gf$=":loc"]'), map:g('[data-gf$=":map"]'),
                  nm:g('[data-gf$=":nm"]'), date:g('[data-gf$=":date"]')};}""")
        rec("يملأ التاريخ والموقع عند الطلب",
            cp["loc"] == "قاعة غرناطة" and cp["map"] == "https://maps.app.goo.gl/x", str(cp["loc"]))
        rec("ولا يمسّ الاسم", cp["nm"] == "", repr(cp["nm"]))

    # ── الحفظ ────────────────────────────────────────────────────
    j = await pg.evaluate("""()=>document.querySelector('.pcard.open [data-gf$=":nm"]').dataset.gf.split(':')[0]""")
    await pg.click(f'[data-gq="{j}:s2:1"]'); await pg.wait_for_timeout(300)
    await pg.fill(f'[data-gf="{j}:nm"]', "لمياء المجاهد")
    await pg.fill(f'[data-gf="{j}:ph"]', "0533221100")
    await pg.wait_for_timeout(300)

    sums = await pg.evaluate("""()=>[...document.querySelectorAll('#g-sum .v')].map(x=>x.textContent.trim())""")
    rec("المجموع أسفل الورقة يجمع البطاقتين", sums[0] == "2" and sums[1].startswith("1,600"), str(sums))
    rec("ومجموع العرابين", sums[2].startswith("400"), str(sums[2]))
    rec("والمتبقّي", sums[3].startswith("1,200"), str(sums[3]))
    rec("وزرّ الحفظ يقول كم حجزًا", "2" in (await pg.inner_text("#g-save")),
        await pg.inner_text("#g-save"))

    # المجموع لا يطفو فوق ما تكتبه: كان لاصقًا بأسفل الشاشة فيغطّي الحقول.
    JSOVER = """()=>{const g=document.getElementById('g-sum');
      const cs=getComputedStyle(g), gr=g.getBoundingClientRect();
      const hit=[...document.querySelectorAll('.pcard.open .input, .pcard.open .rowline, .pcard.open .label')]
        .filter(e=>{const r=e.getBoundingClientRect();
          return r.height>0 && !(r.bottom<=gr.top+1 || r.top>=gr.bottom-1
                                 || r.right<=gr.left+1 || r.left>=gr.right-1);})
        .map(e=>(e.textContent||'').trim().slice(0,16));
      return {pos:cs.position, overlaps:hit, bottom:Math.round(gr.bottom)};}"""
    over = []
    for pos in (0, -1, 99999):
        if pos == -1:
            await pg.evaluate("()=>{const b=document.querySelector('.sheet-body');"
                              "b.scrollTo(0,(b.scrollHeight-b.clientHeight)/2);}")
        else:
            await pg.evaluate(f"()=>document.querySelector('.sheet-body').scrollTo(0,{pos})")
        await pg.wait_for_timeout(350)
        over.append(await pg.evaluate(JSOVER))
    rec("المجموع ليس لاصقًا", all(o["pos"] == "static" for o in over),
        str(over[0]["pos"]))
    rec("ولا يغطّي حقلًا في أيّ موضعٍ من التمرير",
        all(not o["overlaps"] for o in over),
        " · ".join(", ".join(o["overlaps"][:2]) for o in over if o["overlaps"]))
    rec("ويُرى حين يُنزَل إلى آخر الورقة",
        over[-1]["bottom"] <= 932 + 4, f'أسفله عند {over[-1]["bottom"]}')
    await pg.screenshot(path=f"{OUT}/group-sheet.png", full_page=True)

    await pg.evaluate("()=>{window.__RPC=[];}")
    await pg.click("#g-save"); await pg.wait_for_timeout(1200)
    call = await pg.evaluate("""()=>{const r=(window.__RPC||[]).find(x=>x.name==='admin_create_group');
      return r ? r.args : null;}""")
    rec("الحفظ نداءٌ ذرّيٌّ واحد", call is not None,
        str([r for r in (await pg.evaluate("()=>(window.__RPC||[]).map(r=>r.name)"))]))
    if call:
        ppl = call.get("p_people") or []
        rec("يحمل العميلتين معًا", len(ppl) == 2, str(len(ppl)))
        rec("لكلٍّ بنودُها", all(len(x.get("items") or []) for x in ppl),
            str([len(x.get("items") or []) for x in ppl]))
        rec("ولكلٍّ عربونُها", [float(x.get("deposit") or 0) for x in ppl] == [400.0, 0.0],
            str([x.get("deposit") for x in ppl]))
        rec("والجوال موحَّد", ppl[0].get("client_phone") == "966501234567",
            str(ppl[0].get("client_phone")))
        rec("ولا يُرسَل اسم مناسبة", call.get("p_label") in (None, ""), str(call.get("p_label")))
        rec("ومفتاحٌ يمنع التكرار", bool(call.get("p_idem")) and len(str(call.get("p_idem"))) >= 32, "")
    ins = await pg.evaluate("()=>(window.__INS||[]).map(r=>r.t)")
    rec("لا كتابة مباشرة في الجداول", not any(t in ("bookings", "booking_items") for t in ins), str(ins))
    closed = await pg.evaluate("()=>document.getElementById('sheet').hidden")
    rec("والورقة تُغلق بعد الحفظ", closed, "")

    rec("بلا أخطاء", len(errs) == 0, "; ".join(errs[:3]))
    await ctx.close(); await b.close()

asyncio.run(main())
print(f"\n=== {ok}/{ok+fail} passed ===")

# طقمٌ لا يُخرج رمز فشل يمرّ في المُشغِّل وهو ساقط — وهذا أخطر من
# السقوط نفسه، إذ يُطمئن كذبًا.
sys.exit(1 if fail else 0)
