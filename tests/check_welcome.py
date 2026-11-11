# ترحيب العميلة العائدة (§٧ن): سطرٌ تحت خانة الجوال حين يكون الرقم لعميلةٍ خلصت خدمتها —
# «أهلًا بعودتك سارة، نوّرتينا من جديد». يقيس ما يُرى: الظهور بعد السؤال لا قبله وبالاسم الأوّل
# ممّا كُتب، والسؤال مرّةً لكلّ رقمٍ وبالرقم وحده، والاصطفاف على خطّ عنوان الخانة وعلى بُعد ٧،
# والانطواء بلا أثرٍ للعميلة الجديدة، والاختفاء حين ينقص الرقم، والصمت عند العطب، والحركة
# تتّسع بلا تعليق — على ٣٦٠ و٣٩٠ و٤٤٠.
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
BACK, NEW = "966501234567", "966559876543"     # الأولى خلصت خدمتها في المحاكي، والثانية جديدة
TEXT = "أهلًا بعودتك سارة، نوّرتينا من جديد"
R = []
def rec(n, ok, note=""): R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

async def openForm(pg):
    await pg.evaluate("()=>{window.__pick(1,3); window.__goto(2);}"); await pg.wait_for_timeout(1100)
    await pg.evaluate("()=>{const b=[...document.querySelectorAll('#week button.day:not([disabled])')]; if(b.length) b[b.length>2?2:0].click();}")
    await pg.wait_for_timeout(900)
    await pg.evaluate("()=>{const t=[...document.querySelectorAll('#times [data-slot]')]; if(t.length) t[0].click();}")
    await pg.wait_for_timeout(600)
    await pg.click("#confirmBtn"); await pg.wait_for_timeout(800)

STATE = """()=>{const h=document.getElementById('phHello'), p=h.querySelector('p'), f=document.querySelector('.field.phone'),
  lab=document.querySelector('label[for=ph]'), svg=p.querySelector('svg'), nx=document.getElementById('locTxt').closest('.field');
  const r=e=>e.getBoundingClientRect(), cs=getComputedStyle(p), b=document.getElementById('sheetBody');
  const calls=(window.__RPC||[]).filter(c=>c.name==='is_returning_client');
  return {on:h.classList.contains('on'), text:document.getElementById('phHelloTxt').textContent,
    vis:cs.visibility, op:+cs.opacity, h:+r(h).height.toFixed(2),
    dx:+(r(lab).right-r(svg).right).toFixed(2), top:+(r(p).top-r(f).bottom).toFixed(2),
    lines:Math.round(r(p).height/parseFloat(cs.lineHeight)), font:cs.fontSize, color:cs.color,
    gapNow:+(r(nx).top-r(f).bottom).toFixed(2), gap:parseFloat(getComputedStyle(document.querySelector('.fields')).rowGap),
    over:b.scrollHeight-b.clientHeight, calls:calls.map(c=>c.args.p_phone), keys:calls.map(c=>Object.keys(c.args).join(','))}}"""
GROW = """async ()=>{const h=document.getElementById('phHello'); const out=[]; const t0=performance.now();
  while(performance.now()-t0<1000){ out.push(+h.getBoundingClientRect().height.toFixed(2)); await new Promise(r=>requestAnimationFrame(r)); }
  return out;}"""
TO_END = "e=>{e.focus();e.setSelectionRange(e.value.length,e.value.length)}"

async def page(b, vw, vh, init="", **kw):
    ctx = await b.new_context(viewport={"width": vw, "height": vh}, has_touch=True, is_mobile=True, device_scale_factor=2, **kw)
    await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript", body=MOCK)))
    await ctx.add_init_script(f"window.__RETURNING__=['{BACK}'];{init}")
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1500)
    await openForm(pg)
    return ctx, pg, errs

async def main():
  async with async_playwright() as p:
    b = await p.chromium.launch(**_H.CHROME, args=["--no-sandbox"])
    for vw, vh in ((360, 620), (390, 700), (440, 794)):
      T = f"[{vw}x{vh}] "
      ctx, pg, errs = await page(b, vw, vh)
      s = await pg.evaluate(STATE)
      rec(T + "قبل الرقم: لا ترحيب ولا سؤال، ومطويًّا لا يأخذ شيئًا والفجوة كما كانت",
          not s["on"] and s["h"] == 0 and abs(s["gapNow"] - s["gap"]) < .05 and not s["calls"] and s["vis"] == "hidden",
          f"h={s['h']} gap={s['gapNow']}/{s['gap']} calls={s['calls']} vis={s['vis']}")
      await pg.fill("#nm", "سارة محمد")
      await pg.locator("#ph").press_sequentially("0501234567", delay=15)
      s = await pg.evaluate(STATE)
      rec(T + "لحظة آخر رقم: لا ترحيب قبل الجواب", not s["on"], f"calls={s['calls']}")
      hs = await pg.evaluate(GROW)
      steps = [y - x for x, y in zip(hs, hs[1:])]
      rec(T + "يتّسع بانسياب: لا ينكمش ولا يقفز", min(steps) >= -0.01 and max(steps) < 8 and hs[-1] > 15,
          f"أكبر خطوة {max(steps):.1f} والنهاية {hs[-1]}")
      s = await pg.evaluate(STATE)
      rec(T + "الرقم العائد: الترحيب بالاسم الأوّل ممّا كُتب", s["on"] and s["text"] == TEXT and s["vis"] == "visible" and s["op"] == 1, repr(s["text"]))
      rec(T + "سؤالٌ واحد بالرقم المطبَّع وحده (لا اسم)", s["calls"] == [BACK] and s["keys"] == ["p_phone"], f"{s['calls']} {s['keys']}")
      rec(T + "القلب على خطّ «رقم الجوال» نفسه، والسطر على بُعد ٧ من الخانة",
          abs(s["dx"]) < .5 and abs(s["top"] - 7) < .5, f"dx={s['dx']} top={s['top']}")
      rec(T + "سطرٌ واحد ١٢ بلون الهوية", s["lines"] == 1 and s["font"] == "12px" and s["color"] == "rgb(176, 112, 92)",
          f"{s['lines']} {s['font']} {s['color']}")
      if vw >= 390:
        rec(T + "ومعه تكتمل اللوحة بلا سحب", s["over"] <= 0, f"over={s['over']}")
      else:
        print(f"INFO {T}مع الترحيب يحتاج السحب {s['over']} (اعتمده صاحب المشروع على الجوال الصغير)")
      if vw == 440:
        await pg.screenshot(path=f"{_H.SHOTS}/19-welcome.png")
        await pg.fill("#nm", "أم فهد العتيبي"); await pg.wait_for_timeout(120)
        t1 = (await pg.evaluate(STATE))["text"]
        await pg.fill("#nm", ""); await pg.wait_for_timeout(120)
        t2 = (await pg.evaluate(STATE))["text"]
        rec("الاسم يتبع الخانة الأولى: «أم فهد» كاملًا، وبلا اسمٍ بلا فراغ",
            t1 == "أهلًا بعودتك أم فهد، نوّرتينا من جديد" and t2 == "أهلًا بعودتك، نوّرتينا من جديد", f"{t1!r} {t2!r}")
        await pg.fill("#nm", "Sara"); await pg.wait_for_timeout(120)
        bdi = await pg.evaluate("()=>{const b=document.querySelector('#phHelloTxt bdi');return b?b.textContent:null}")
        rec("اسمٌ لاتينيّ معزول الاتّجاه فلا يقلب السطر", bdi == "Sara", repr(bdi))
        await pg.fill("#nm", "سارة محمد"); await pg.wait_for_timeout(120)
        await pg.locator("#ph").evaluate(TO_END); await pg.keyboard.press("Backspace"); await pg.wait_for_timeout(650)
        s = await pg.evaluate(STATE)
        rec("ينقص رقم: ينطوي ويغيب عن قارئ الشاشة", not s["on"] and s["h"] == 0 and s["vis"] == "hidden", f"h={s['h']} vis={s['vis']}")
        await pg.keyboard.type("7"); await pg.wait_for_timeout(650)
        s = await pg.evaluate(STATE)
        rec("ويعود الرقم: يظهر من جديد بلا سؤالٍ ثانٍ", s["on"] and s["calls"] == [BACK], str(s["calls"]))
        await pg.fill("#ph", "0559876543"); await pg.wait_for_timeout(700)
        s = await pg.evaluate(STATE)
        rec("رقمٌ جديد: لا ترحيب، والفجوة كما كانت", not s["on"] and s["h"] == 0 and abs(s["gapNow"] - s["gap"]) < .05 and s["calls"] == [BACK, NEW],
            f"h={s['h']} gap={s['gapNow']}/{s['gap']} calls={s['calls']}")
        await pg.fill("#ph", "٠٥٠١٢٣٤٥٦٧"); await pg.wait_for_timeout(650)
        s = await pg.evaluate(STATE)
        rec("بالأرقام العربية: الرقم نفسه فيظهر بلا سؤالٍ ثالث", s["on"] and len(s["calls"]) == 2, str(s["calls"]))
      rec(T + "بلا أخطاء", not errs, "; ".join(errs[:2]))
      await ctx.close()

    # العطب «لا» بصمت: لا ترحيب ولا خطأ يظهر للعميلة.
    ctx, pg, errs = await page(b, 390, 700, "window.__RETURNING_FAIL__=true;")
    await pg.fill("#nm", "سارة محمد"); await pg.fill("#ph", "0501234567"); await pg.wait_for_timeout(800)
    s = await pg.evaluate(STATE)
    rec("عطب القاعدة: لا ترحيب ولا خطأ", not s["on"] and not errs and s["calls"] == [BACK], f"{s['calls']} {errs[:1]}")
    await ctx.close()

    # الجواب البطيء لا يُظهر الترحيب لرقمٍ تغيّر أثناء السؤال.
    ctx, pg, errs = await page(b, 390, 700, "window.__RETURNING_DELAY__=500;")
    await pg.fill("#ph", "0501234567"); await pg.wait_for_timeout(400)
    await pg.fill("#ph", "0559876543"); await pg.wait_for_timeout(1300)
    s = await pg.evaluate(STATE)
    rec("جوابٌ متأخّر لرقمٍ تغيّر لا يُظهر ترحيبًا", not s["on"], str(s["calls"]))
    await ctx.close()

    # من طلب تقليل الحركة: قاعدة الموقع العامّة تقصّر كلَّ انتقالٍ إلى ‎.12‎ث، والترحيب يتبعها.
    ctx, pg, errs = await page(b, 440, 794, reduced_motion="reduce")
    await pg.fill("#ph", "0501234567"); await pg.wait_for_timeout(500)
    tr = await pg.evaluate("()=>{const h=document.getElementById('phHello');return [getComputedStyle(h).transitionDuration, getComputedStyle(h.querySelector('p')).transitionDuration, h.classList.contains('on')]}")
    rec("تقليل الحركة: الانتقال القصير الذي يتبعه الموقع كلّه", tr[2] and all(set(d.split(", ")) == {"0.12s"} for d in tr[:2]), str(tr))
    await ctx.close()
    await b.close()

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
