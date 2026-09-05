# -*- coding: utf-8 -*-
"""العربون في الحجز اليدوي، والفترة الاستثنائية نطاقًا لا يومًا.

الاختباران هنا يقابلان طلبين صريحين: أن ترى زوجتك كم دفعت العميلة وهي
تُسجّل الحجز، وأن تُغلق أسبوعًا بصفٍّ واحد بدل سبعة.
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
def rec(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1;   print(f"PASS {name}" + (f" — {extra}" if extra else ""))
    else:    fail += 1; print(f"FAIL {name} — {extra}")

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
    await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(1900)

    # ══ أوّلًا: العربون في ورقة الحجز اليدوي ═══════════════════════════
    await pg.eval_on_selector_all("button, a",
        "els=>{const t=els.find(e=>/حجز يدوي|إضافة حجز/.test(e.textContent)); t && t.click();}")
    await pg.wait_for_timeout(600)
    # صار الزرّ يسأل: فردٌ أم مجموعة؟ فنمضي إلى الفرديّة.
    if await pg.evaluate("()=>!!document.getElementById('k-one')"):
        await pg.click("#k-one")
    await pg.wait_for_timeout(800)
    rec("ورقة الحجز اليدوي تفتح", await pg.evaluate("()=>!!document.getElementById('n-save')"))

    dep = await pg.evaluate("""()=>{const e=document.getElementById('n-dep');
      if(!e) return null; const l=document.querySelector('label[for="n-dep"]');
      return {type:e.type, val:e.value, ph:e.placeholder, label:l?l.textContent.trim():''};}""")
    rec("خانة العربون موجودة", dep is not None, str(dep and dep["label"]))
    rec("رقميّة وفارغة ابتداءً", dep and dep["type"] == "number" and dep["val"] == "",
        f'type={dep and dep["type"]} value={dep and dep["val"]!r}')
    rec("مكتوبٌ أنّها اختيارية", dep and "اختياري" in dep["label"], str(dep and dep["label"]))

    # موضعها: بعد كتلة الخدمات، قبل التاريخ — كما طلب.
    order = await pg.evaluate("""()=>{const y=id=>{const e=document.getElementById(id);
      return e? e.getBoundingClientRect().top : null;};
      return {sum:y('n-sum'), dep:y('n-dep'), date:y('n-date')};}""")
    rec("موضعها بعد الخدمات وقبل التاريخ",
        order["sum"] < order["dep"] < order["date"], str(order))

    # شخصان من الخدمة الثانية: ٦٠٠×٢ − خصم ١٠٠×٢ = ١٠٠٠
    sid = await pg.evaluate("()=>document.querySelectorAll('[data-nd=\"+\"]')[1].dataset.sid")
    plus = f'[data-nd="+"][data-sid="{sid}"]'
    await pg.click(plus); await pg.click(plus); await pg.wait_for_timeout(300)
    st0 = await pg.evaluate("""()=>({sum:document.getElementById('n-sum').textContent.trim(),
      rest:document.getElementById('n-rest').textContent.trim()})""")
    rec("المتبقّي يساوي الإجمالي قبل أي عربون",
        st0["sum"].startswith("1,000") and st0["rest"].startswith("1,000"), str(st0))

    await pg.fill("#n-dep", "400"); await pg.wait_for_timeout(300)
    st1 = await pg.evaluate("""()=>({rest:document.getElementById('n-rest').textContent.trim(),
      hint:document.getElementById('n-dephint').textContent.trim()})""")
    rec("المتبقّي ينقص بالعربون — ١٠٠٠−٤٠٠", st1["rest"].startswith("600"), str(st1["rest"]))
    rec("والتلميح يذكر رسالة التأكيد", "التأكيد" in st1["hint"], st1["hint"])

    await pg.fill("#n-dep", "1000"); await pg.wait_for_timeout(300)
    st2 = await pg.evaluate("""()=>({rest:document.getElementById('n-rest').textContent.trim(),
      hint:document.getElementById('n-dephint').textContent.trim()})""")
    rec("السداد الكامل يُقال صراحةً", st2["rest"].startswith("0") and "بالكامل" in st2["hint"], str(st2))

    await pg.fill("#n-dep", "5000"); await pg.wait_for_timeout(300)
    st3 = await pg.evaluate("""()=>{const h=document.getElementById('n-dephint');
      return {hint:h.textContent.trim(), warn:getComputedStyle(h).color};}""")
    rec("العربون الأكبر من الإجمالي يُنبَّه عليه قبل الحفظ",
        "أكبر من الإجمالي" in st3["hint"], st3["hint"])

    # ما يصل القاعدة فعلًا
    await pg.fill("#n-dep", "400")
    await pg.fill("#n-name", "تجربة العربون")
    await pg.fill("#n-phone", "0501234567")
    await pg.evaluate("()=>{window.__RPC=[];}")
    await pg.click("#n-save"); await pg.wait_for_timeout(900)
    call = await pg.evaluate("""()=>{const r=(window.__RPC||[])
      .find(x=>x.name==='admin_create_booking'); return r?r.args.p_booking:null;}""")
    rec("العربون يُرسَل مع الحجز", call and Number(call.get("deposit")) == 400,
        str(call and call.get("deposit")))

    # ══ ثانيًا: الفترة الاستثنائية نطاق ════════════════════════════════
    await pg.evaluate("""()=>[...document.querySelectorAll('.tab')]
        .find(t=>t.textContent.includes('الإعدادات')).click()""")
    await pg.wait_for_timeout(900)
    await pg.evaluate("""()=>{const t=[...document.querySelectorAll('.panetab')]
        .find(x=>/أوقات|العمل/.test(x.textContent)); t && t.click();}""")
    await pg.wait_for_timeout(900)

    rows = await pg.evaluate("""()=>[...document.querySelectorAll('.rowline')]
      .filter(r=>r.querySelector('[data-delov]'))
      .map(r=>({t:r.querySelector('.t')?.textContent.trim(),
                s:r.querySelector('.s')?.textContent.trim()}))""")
    rec("الفترات معروضة", len(rows) >= 2, str(len(rows)))
    span = next((r for r in rows if "—" in (r["t"] or "")), None)
    rec("الفترة الممتدّة تُعرض بطرفيها", span is not None, str(span and span["t"]))
    rec("وتقول كم يومًا هي", span and "أيام" in (span["s"] or ""), str(span and span["s"]))
    one = next((r for r in rows if "—" not in (r["t"] or "")), None)
    rec("واليوم الواحد يبقى تاريخًا واحدًا بلا عدّة",
        one and "أيام" not in (one["s"] or "") and "يومان" not in (one["s"] or ""),
        str(one and one["s"]))

    await pg.evaluate("""()=>{const b=document.getElementById('addOverride'); b && b.click();}""")
    await pg.wait_for_timeout(800)
    sheet = await pg.evaluate("""()=>{const g=id=>document.getElementById(id);
      return {title:document.getElementById('sheetTitle')?.textContent.trim(),
              from:!!g('o-date'), to:!!g('o-end'),
              same:g('o-date')?.value === g('o-end')?.value,
              span:g('o-span')?.textContent.trim()};}""")
    rec("الورقة صارت فترة لا يومًا", sheet["title"] == "فترة استثنائية", str(sheet["title"]))
    rec("طرفان: من وإلى", sheet["from"] and sheet["to"], "")
    rec("يبدآن على اليوم نفسه", sheet["same"], "")
    rec("ويُقرأ ذلك: يوم واحد", "يوم واحد" in (sheet["span"] or ""), str(sheet["span"]))

    # من ٧ إلى ٩ = ثلاثة أيام (النطاق مغلق الطرفين)
    await pg.evaluate("""()=>{const f=document.getElementById('o-date'),t=document.getElementById('o-end');
      const d=new Date(); d.setDate(d.getDate()+7);
      const p=n=>String(n).padStart(2,'0');
      const iso=x=>`${x.getFullYear()}-${p(x.getMonth()+1)}-${p(x.getDate())}`;
      f.value=iso(d); f.dispatchEvent(new Event('input'));
      const e=new Date(d); e.setDate(e.getDate()+2);
      t.value=iso(e); t.dispatchEvent(new Event('input'));}""")
    await pg.wait_for_timeout(300)
    rec("من السابع إلى التاسع ثلاثة أيام",
        "3 أيام" in (await pg.evaluate("()=>document.getElementById('o-span').textContent")),
        await pg.evaluate("()=>document.getElementById('o-span').textContent.trim()"))

    # نهاية قبل بداية: تُجَرّ ولا تُرفض
    await pg.evaluate("""()=>{const f=document.getElementById('o-date'),t=document.getElementById('o-end');
      const d=new Date(); d.setDate(d.getDate()+20);
      const p=n=>String(n).padStart(2,'0');
      f.value=`${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`;
      f.dispatchEvent(new Event('input'));}""")
    await pg.wait_for_timeout(300)
    pulled = await pg.evaluate("""()=>{const f=document.getElementById('o-date'),t=document.getElementById('o-end');
      return {f:f.value, t:t.value, min:t.min, span:document.getElementById('o-span').textContent.trim()};}""")
    rec("تقديم البداية يجرّ النهاية معها", pulled["t"] >= pulled["f"], str(pulled))
    rec("والحدّ الأدنى للنهاية هو البداية", pulled["min"] == pulled["f"], str(pulled["min"]))

    # ما يصل القاعدة
    await pg.evaluate("()=>{window.__UPS=[];}")
    await pg.evaluate("""()=>{const t=document.getElementById('o-end');
      const d=new Date(t.value); d.setDate(d.getDate()+4);
      const p=n=>String(n).padStart(2,'0');
      t.value=`${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`;
      t.dispatchEvent(new Event('input'));}""")
    saved = await pg.evaluate("""()=>{const f=document.getElementById('o-date').value,
      t=document.getElementById('o-end').value; return {f,t};}""")
    await pg.click("#o-save"); await pg.wait_for_timeout(900)
    up = await pg.evaluate("()=>window.__UPSERT||[]")
    row = up[-1] if up else None
    rec("النطاق يُحفظ بطرفيه",
        row and row.get("the_date") == saved["f"] and row.get("end_date") == saved["t"],
        str(row and {k: row.get(k) for k in ("the_date", "end_date", "kind")}))

    rec("بلا أخطاء", len(errs) == 0, "; ".join(errs[:3]))
    await pg.screenshot(path=f"{OUT}/range-overrides.png", full_page=True)
    await ctx.close(); await b.close()

def Number(x):
    try: return float(x)
    except (TypeError, ValueError): return None

asyncio.run(main())
print(f"\n=== {ok}/{ok+fail} passed ===")

# طقمٌ لا يُخرج رمز فشل يمرّ في المُشغِّل وهو ساقط — وهذا أخطر من
# السقوط نفسه، إذ يُطمئن كذبًا.
sys.exit(1 if fail else 0)
