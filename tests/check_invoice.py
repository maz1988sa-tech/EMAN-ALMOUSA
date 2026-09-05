# -*- coding: utf-8 -*-
"""بنود الحجز تُقرأ فاتورةً لا قائمةَ تكرار.

أربع سهراتٍ كانت أربعة صفوف متطابقة. الآن سطرٌ واحد بعدده وسعرِ وحدته
ومجموعه — في اللوحة، وفي صفحة العميلة، وفي التصدير.
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

ok = fail = 0
def rec(n, c, x=""):
    global ok, fail
    if c: ok += 1;   print(f"PASS {n}" + (f" — {x}" if x else ""))
    else: fail += 1; print(f"FAIL {n} — {x}")

async def main():
  async with async_playwright() as p:
    b = await p.chromium.launch(
        **_H.CHROME,
        args=["--no-sandbox"])

    # ══ الدالّة نفسها: تُفحص مباشرةً ═══════════════════════════════
    ctx = await b.new_context()
    pg = await ctx.new_page()
    await pg.goto(f"http://127.0.0.1:{PORT}/index.html")
    await pg.wait_for_timeout(900)
    g = await pg.evaluate("""async ()=>{
      const v = (document.querySelector('script[type=module]')?.textContent || '')
                  .match(/db\.js\?v=(\d+)/)?.[1] || '';
      const m = await import(`./assets/db.js?v=${v}`);
      const one = m.groupItems([{service_name:'سهرة', price:600},
                                {service_name:'سهرة', price:600},
                                {service_name:'سهرة', price:600},
                                {service_name:'عروس', price:1500}]);
      const split = m.groupItems([{service_name:'سهرة', price:600},
                                  {service_name:'سهرة', price:500}]);
      const named = m.groupItems([{service_name:'سهرة', price:600, person_name:'لمى'},
                                  {service_name:'سهرة', price:600, person_name:'هند'}]);
      return {one, split, named, empty:m.groupItems([]), nul:m.groupItems(null)};}""")
    rec("المتطابقة تُجمَع في سطر", len(g["one"]) == 2, f'{len(g["one"])} سطرًا')
    rec("والعدد صحيح", g["one"][0]["n"] == 3, str(g["one"][0]["n"]))
    rec("والمجموع حاصلُ الضرب — ٣×٦٠٠", g["one"][0]["total"] == 1800, str(g["one"][0]["total"]))
    rec("وسعر الوحدة محفوظ", g["one"][0]["unit"] == 600, str(g["one"][0]["unit"]))
    rec("والترتيب كما وردت", g["one"][0]["name"] == "سهرة" and g["one"][1]["name"] == "عروس",
        str([x["name"] for x in g["one"]]))
    rec("سعرٌ خاصٌّ يفتح سطرًا مستقلًّا — وإلّا كذب الضرب",
        len(g["split"]) == 2, f'{len(g["split"])} سطرًا')
    rec("وأسماء الأشخاص تُجمَع مع سطرها",
        g["named"][0]["people"] == ["لمى", "هند"], str(g["named"][0]["people"]))
    rec("ولا تنكسر على قائمةٍ فارغة أو معدومة",
        g["empty"] == [] and g["nul"] == [], "")
    await ctx.close()

    # ══ اللوحة ════════════════════════════════════════════════════
    ctx = await b.new_context(viewport={"width": 430, "height": 932}, device_scale_factor=2)
    await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
        r.fulfill(content_type="application/javascript", body=MOCK)))
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
    await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(2000)
    await pg.evaluate("""()=>[...document.querySelectorAll('.tab')]
        .find(t=>t.textContent.includes('الحجوزات')).click()""")
    await pg.wait_for_timeout(900)
    await pg.evaluate("""()=>{const b=document.querySelector('[data-st="all"]'); b && b.click();}""")
    await pg.wait_for_timeout(700)
    await pg.evaluate("""()=>{const r=[...document.querySelectorAll('[data-open]')]
        .find(e=>e.innerText.includes('سارة')); r && r.click();}""")
    await pg.wait_for_timeout(900)
    rows = await pg.evaluate("""()=>{const c=[...document.querySelectorAll('#sheetContent .card')]
        .find(x=>x.textContent.includes('الخدمات'));
      return [...c.querySelectorAll('.leader')].map(l=>l.innerText.replace(/\\s+/g,' ').trim());}""")
    svc = [r for r in rows if "ميك اب" in r]
    rec("اللوحة: سطران لا أربعة", len(svc) == 2, str(len(svc)))
    line = next((r for r in svc if "سهرة" in r), "")
    rec("والسطر يحمل العدد وسعر الوحدة", "2 × 600" in line, line)
    rec("ومجموعه لا سعر الوحدة", "1,200" in line, line)
    rec("وأسماء من طلبنها", "لمى" in line and "هند" in line, line)
    rec("ولا يتكرّر اسم الخدمة", line.count("ميك اب سهرة") == 1, line)
    await pg.screenshot(path=f"{_H.SHOTS}/invoice-panel.png", full_page=True)
    rec("بلا أخطاء في اللوحة", len(errs) == 0, "; ".join(errs[:2]))
    await ctx.close()

    # ══ صفحة العميلة ══════════════════════════════════════════════
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                              has_touch=True, is_mobile=True)
    await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
        r.fulfill(content_type="application/javascript", body=MOCK)))
    pg = await ctx.new_page(); errs2 = []
    pg.on("pageerror", lambda e: errs2.append(str(e)))
    await pg.goto(f"http://127.0.0.1:{PORT}/index.html?t=tok-3"); await pg.wait_for_timeout(2200)
    trows = await pg.evaluate("""()=>[...document.getElementById('trackView').querySelectorAll('.row')]
        .map(r=>r.innerText.replace(/\\s+/g,' ').trim())""")
    tsvc = [r for r in trows if "ميك اب" in r]
    rec("صفحة العميلة: سطران كذلك", len(tsvc) == 2, str(len(tsvc)))
    tline = next((r for r in tsvc if "سهرة" in r), "")
    rec("بالعدد وسعر الوحدة والمجموع",
        "2 × 600" in tline and "1,200" in tline, tline)
    rec("بلا أخطاء في صفحة العميلة", len(errs2) == 0, "; ".join(errs2[:2]))
    await pg.screenshot(path=f"{_H.SHOTS}/invoice-track.png", full_page=True)
    await ctx.close(); await b.close()

asyncio.run(main())
print(f"\n=== {ok}/{ok+fail} passed ===")

# طقمٌ لا يُخرج رمز فشل يمرّ في المُشغِّل وهو ساقط — وهذا أخطر من
# السقوط نفسه، إذ يُطمئن كذبًا.
sys.exit(1 if fail else 0)
