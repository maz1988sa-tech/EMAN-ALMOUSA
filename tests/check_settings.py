# الإعدادات قائمةٌ تفتح صفحات (§٧س). يقيس ما تراه صاحبة العمل وما يصل القاعدة: القائمة
# بمجموعاتها وصفوفها بترتيبها، والأيقونات والعناوين والأسهم على خطٍّ واحد، والسطر تحت كلّ صفٍّ
# من الإعدادات نفسها؛ ومفتاح «استقبال حجوزات جديدة» يُحفظ لحظة الضغط والإيقاف يسأل أوّلًا؛ وكلّ
# صفحةٍ تحفظ أعمدتها وحدها وتردّ الخطأ قبل الإرسال؛ والخروج بتغييرٍ لم يُحفظ يسأل؛ والعميلات
# والزوّار صفحةٌ بزرّين؛ واشتراطات الأحياء تحت رابط الموقع في المختبر وحده — على ٣٦٠ و٣٩٠ و٤٤٠.
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
LAB = "function renderHoods" in open(os.path.join(ROOT, "admin.html"), encoding="utf-8").read()

GROUPS = ["الحجز", "الخدمات والمال", "التواصل", "العميلات والزوّار", "البيانات"]
ROWS = [("hours", "أوقات العمل"), ("exceptions", "الإجازات والاستثناءات"), ("rules", "قواعد الحجز"),
        ("location", "الموقع والأحياء"), ("services", "الخدمات والأسعار"), ("deposit", "العربون والتحويل"),
        ("messages", "الرسائل"), ("numbers", "أرقام التواصل"), ("page", "صفحة الحجز"),
        ("clients", "العميلات"), ("visitors", "الزوّار"), ("backup", "النسخ الاحتياطي"), ("delete", "حذف الحجوزات")]
SUMS = {"hours": "4 أيام في الأسبوع", "rules": "مهلة 4 ساعات · حتى 120 يومًا",
        "location": "رابط الموقع اختياري" + (" · فحص الأحياء مطفأ" if LAB else ""),
        "services": "3 خدمات · خصم المجموعة 100", "deposit": "الراجحي · فحص الإيصال مطفأ",
        "messages": "3 رسائل · التلقائي في وضع المعاينة", "numbers": "واتساب 050 111 2222",
        "page": "إيمان آل موسى · إنستقرام وتيك توك", "backup": "لم تُؤخذ نسخةٌ بعد"}
KEYS = {"rules": {"travel_buffer_min", "slot_step_min", "min_lead_hours", "max_advance_days", "show_closed_months", "closed_month_word"},
        "deposit": {"receipt_ocr_required", "bank_name", "iban", "beneficiary_name"},
        "numbers": {"whatsapp_phone", "driver_phone"},
        "page": {"business_name", "tagline", "instagram_url", "tiktok_url"},
        "discount": {"group_discount_amount"}, "location": {"require_loc_map"}}
R = []
def rec(n, ok, note=""): R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

LIST = """()=>{const rows=[...document.querySelectorAll('.setrow')], q=(e,s)=>e.querySelector(s).getBoundingClientRect();
  const spread=(xs)=>xs.length?Math.max(...xs)-Math.min(...xs):99;
  return {head:(document.querySelector('#view .sec-head h2')||{}).textContent,
    groups:[...document.querySelectorAll('.setgroup > p.label')].map(e=>e.textContent.trim()),
    rows:rows.map(e=>[e.dataset.setpage, e.querySelector('.t').textContent.trim()]),
    sums:Object.fromEntries(rows.map(e=>[e.dataset.setpage, e.querySelector('.s').textContent.trim()])),
    badge:+spread(rows.map(e=>q(e,'.badge').right)).toFixed(2), title:+spread(rows.map(e=>q(e,'.t').right)).toFixed(2),
    go:+spread(rows.map(e=>q(e,'.go').left)).toFixed(2), minH:Math.min(...rows.map(e=>e.getBoundingClientRect().height)),
    clip:rows.filter(e=>[...e.querySelectorAll('.t,.s')].some(x=>x.scrollWidth>x.clientWidth+1)).length,
    mid:Math.max(...rows.map(e=>{const a=q(e,'.badge'),c=e.getBoundingClientRect();return Math.abs((a.top+a.bottom)/2-(c.top+c.bottom)/2);})),
    over:document.documentElement.scrollWidth-document.documentElement.clientWidth,
    arrow:getComputedStyle(document.querySelector('.setrow .go svg')).transform,
    old:document.querySelectorAll('.panebar,.panetab,#saveSettings').length}}"""
PAGE = """()=>{const b=document.getElementById('setBack'), h=document.querySelector('#view .sec-head h2');
  return {back:!!b, title:h?h.textContent.trim():'', al:b&&h?+(b.getBoundingClientRect().right-h.getBoundingClientRect().right).toFixed(2):null,
    seg:[...document.querySelectorAll('.setseg button')].map(e=>[e.dataset.setpage,e.getAttribute('aria-pressed')]),
    count:(()=>{const c=document.querySelector('#view .sec-head .count'); return c?c.hidden:null})()}}"""
UPD = "()=>(window.__UPDATES||[]).filter(x=>x.table==='settings').map(x=>x.v)"

async def page(b, vw, vh):
    ctx = await b.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=2, has_touch=True, is_mobile=True)
    await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript", body=MOCK)))
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
    await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(1700)
    return ctx, pg, errs

async def fresh(pg):
    await pg.evaluate("()=>{window.__UPDATES=[];}")

async def main():
  async with async_playwright() as p:
    b = await p.chromium.launch(**_H.CHROME, args=["--no-sandbox"])
    print(f"== {'المختبر' if LAB else 'الجذر'}")
    for vw, vh in ((360, 740), (390, 844), (440, 900)):
      T = f"[{vw}] "
      ctx, pg, errs = await page(b, vw, vh)
      tabs = await pg.eval_on_selector_all("#tabs .tab", "e=>e.map(x=>x.dataset.tab)")
      await _H.open_settings(pg)
      await pg.wait_for_timeout(500)
      m = await pg.evaluate(LIST)
      rec(T + "التبويب يفتح على قائمة «الإعدادات» ولا شريط أقسام ولا زرّ حفظٍ عامّ", m["head"] == "الإعدادات" and m["old"] == 0, f"{m['head']} old={m['old']}")
      rec(T + "الشريط الرئيسي كما هو: خمسة تبويبات", tabs == ["home", "agenda", "browse", "dues", "settings"], str(tabs))
      rec(T + "خمس مجموعات بترتيبها", m["groups"] == GROUPS, str(m["groups"]))
      rec(T + "ثلاثة عشر صفًّا بترتيبها وأسمائها", m["rows"] == [list(r) for r in ROWS], str([r[1] for r in m["rows"]]))
      rec(T + "الأيقونات والعناوين والأسهم على خطٍّ واحد", m["badge"] < .5 and m["title"] < .5 and m["go"] < .5,
          f"أيقونة {m['badge']} · عنوان {m['title']} · سهم {m['go']}")
      rec(T + "الأيقونة في منتصف صفّها، والصفّ ≥ ٥٦، ولا سطر مقصوص", m["mid"] < .6 and m["minH"] >= 56 and m["clip"] == 0,
          f"منتصف {m['mid']:.2f} · أدنى {m['minH']:.1f} · قصّ {m['clip']}")
      rec(T + "السهم يشير إلى الداخل (يسارًا) ولا سحب أفقيّ", m["arrow"].startswith("matrix(-1") and m["over"] <= 0, f"{m['arrow']} over={m['over']}")
      if vw == 390:
        await pg.wait_for_timeout(600)
        sums = (await pg.evaluate(LIST))["sums"]
        bad = {k: sums.get(k) for k, v in SUMS.items() if sums.get(k) != v}
        rec(T + "السطر تحت كلّ صفٍّ من الإعدادات نفسها", not bad, str(bad) if bad else "")
        rec(T + "الإجازات: أقرب فترةٍ قادمة", sums["exceptions"].startswith("فترتان قادمتان · أقربها "), sums["exceptions"])
        bdi = await pg.evaluate("()=>{const e=document.querySelector('[data-setsum=numbers] bdi'); return e?e.getAttribute('dir'):null}")
        rec(T + "رقم الواتساب معزولٌ من اليسار لا ينقلب", bdi == "ltr", str(bdi))
        dz = await pg.evaluate("""()=>{const t=document.querySelector('.setrow.danger .t'); const p=document.createElement('i');
            p.style.color='var(--danger)'; document.body.appendChild(p); const c=getComputedStyle(p).color; p.remove();
            return [document.querySelector('.setrow.danger').dataset.setpage, getComputedStyle(t).color===c]}""")
        rec(T + "«حذف الحجوزات» آخر القائمة بلون الخطر", dz == ["delete", True], str(dz))
        await pg.screenshot(path=f"{_H.SHOTS}/22-settings-list.png", full_page=True)

        # ── المفتاح: يُحفظ لحظة الضغط، والإيقاف يسأل ─────────────────────
        mode = {"v": "dismiss", "n": 0}
        async def on_dialog(d):
            mode["n"] += 1
            await (d.accept() if mode["v"] == "accept" else d.dismiss())
        pg.on("dialog", lambda d: asyncio.ensure_future(on_dialog(d)))
        await fresh(pg)
        await pg.click("label.toggle:has(#set-open) .sw"); await pg.wait_for_timeout(600)
        st = await pg.evaluate("()=>[document.getElementById('set-open').checked]")
        up = await pg.evaluate(UPD)
        rec(T + "إيقاف الاستقبال يسأل، والتراجع لا يرسل شيئًا ويبقيه مشتعلًا", mode["n"] == 1 and st == [True] and not up, f"أسئلة={mode['n']} {st} {up}")
        mode["v"] = "accept"
        await pg.click("label.toggle:has(#set-open) .sw"); await pg.wait_for_timeout(700)
        up = await pg.evaluate(UPD)
        line = await pg.inner_text("#set-open-s")
        rec(T + "وبالموافقة يُحفظ وحده لحظتها: accepting_bookings=false", len(up) == 1 and set(up[0]) - {"updated_at"} == {"accepting_bookings"}
            and up[0]["accepting_bookings"] is False and line.startswith("موقوفة الآن"), f"{up} · {line}")
        n0 = mode["n"]; await fresh(pg)
        await pg.click("label.toggle:has(#set-open) .sw"); await pg.wait_for_timeout(700)
        up = await pg.evaluate(UPD)
        rec(T + "وإعادة التشغيل تُحفظ بلا سؤال", mode["n"] == n0 and len(up) == 1 and up[0]["accepting_bookings"] is True, f"{up}")
        mode["v"] = "accept"

        # ── كلّ صفٍّ يفتح صفحته، وزرّ الرجوع على خطّ عنوانها ─────────────
        bad, mis = [], []
        for k, t in ROWS:
          await _H.open_settings(pg, k, 700)
          s = await pg.evaluate(PAGE)
          want = "العميلات والزوّار" if k in ("clients", "visitors") else t
          if not (s["back"] and s["title"] == want): bad.append((k, s["title"]))
          elif abs(s["al"]) > .6: mis.append((k, s["al"]))
        rec(T + "كلّ صفٍّ يفتح صفحته بزرّ رجوعٍ وعنوانٍ باسمه", not bad, str(bad))
        rec(T + "زرّ «الإعدادات» للرجوع على خطّ عنوان الصفحة", not mis, str(mis) if mis else "فرق ≤ ٠٫٦")
        await pg.click("#setBack"); await pg.wait_for_timeout(600)
        rec(T + "والرجوع يعيد القائمة", await pg.evaluate("()=>document.querySelectorAll('.setrow').length") == 13)
        await _H.open_settings(pg, "rules", 700)
        await pg.click("[data-tab=settings]"); await pg.wait_for_timeout(700)
        rec(T + "و«الإعدادات» في الشريط وهي مفتوحة تعيد القائمة", await pg.evaluate("()=>!document.getElementById('setBack') && document.querySelectorAll('.setrow').length===13"))

        # ── العميلات والزوّار: صفحةٌ بزرّين ───────────────────────────────
        await _H.open_settings(pg, "clients", 900)
        s = await pg.evaluate(PAGE)
        has = await pg.evaluate("()=>[!!document.getElementById('clQ'), !!document.getElementById('visRange')]")
        rec(T + "«العميلات» تفتح على زرّها، والعدد لا يزاحم العنوان", s["seg"] == [["clients", "true"], ["visitors", "false"]] and has == [True, False] and s["count"] is True, f"{s['seg']} {has} count_hidden={s['count']}")
        await pg.click(".setseg [data-setpage=visitors]"); await pg.wait_for_timeout(900)
        s = await pg.evaluate(PAGE)
        has = await pg.evaluate("()=>[!!document.getElementById('clQ'), !!document.getElementById('visRange')]")
        rec(T + "وزرّ «الزوّار» يبدّل إليها في الصفحة نفسها", s["seg"] == [["clients", "false"], ["visitors", "true"]] and has == [False, True] and s["title"] == "العميلات والزوّار", f"{s['seg']} {has}")

        # ── كلّ صفحةٍ تحفظ أعمدتها وحدها، وتردّ الخطأ قبل الإرسال ──────────
        # الخطأ يبقي الصفحة «غير محفوظة»، فلا تُغادَر بلا سؤال: تُصحَّح الخانة وتُحفظ في مكانها.
        async def fill_save(fill, button):
          await fresh(pg)
          for sel, val in fill:
            if isinstance(val, bool):
              await pg.evaluate("([s,v])=>{const e=document.querySelector(s); e.checked=v; e.dispatchEvent(new Event('change',{bubbles:true}));}", [sel, val])
            else:
              await pg.fill(sel, val)
          await pg.click(button); await pg.wait_for_timeout(700)
          up = await pg.evaluate(UPD)
          err = await pg.evaluate("()=>(document.getElementById('set-err')||{}).innerText||''")
          return up, err.strip()
        await _H.open_settings(pg, "rules", 800)
        up, err = await fill_save([("#set-lead", "6")], "#saveRules")
        rec(T + "«قواعد الحجز» تحفظ حقولها الستّة وحدها", len(up) == 1 and set(up[0]) - {"updated_at"} == KEYS["rules"] and up[0]["min_lead_hours"] == 6, str(up and sorted(up[0])))
        await _H.open_settings(pg, None, 700)
        rec(T + "والقائمة تقرأ ما حُفظ", (await pg.inner_text("[data-setsum=rules]")).startswith("مهلة 6 ساعات"), await pg.inner_text("[data-setsum=rules]"))
        await _H.open_settings(pg, "deposit", 800)
        up, err = await fill_save([("#set-iban", "SA12")], "#saveDeposit")
        rec(T + "آيبانٌ ناقص يُردّ هنا ولا يُرسل", not up and "الآيبان غير صحيح" in err, err)
        up, err = await fill_save([("#set-iban", "SA03 8000 0000 6080 1016 7519")], "#saveDeposit")
        rec(T + "وبعد تصحيحه تحفظ «العربون والتحويل» أعمدتها الأربعة والآيبان بلا مسافات", len(up) == 1 and set(up[0]) - {"updated_at"} == KEYS["deposit"] and up[0]["iban"] == "SA0380000000608010167519", str(up))
        await _H.open_settings(pg, "numbers", 800)
        up, err = await fill_save([("#set-wa", "123")], "#saveNumbers")
        rec(T + "رقمٌ ناقص يُردّ هنا ولا يُرسل", not up and "رقم واتساب غير صحيح" in err, err)
        up, err = await fill_save([("#set-wa", "0551234567")], "#saveNumbers")
        rec(T + "«أرقام التواصل» تحفظ الرقمين وحدهما بصيغتهما", len(up) == 1 and set(up[0]) - {"updated_at"} == KEYS["numbers"] and up[0]["whatsapp_phone"] == "966551234567", str(up))
        await _H.open_settings(pg, "page", 800)
        up, err = await fill_save([("#set-ig", "http://instagram.com/x")], "#savePage")
        rec(T + "رابطٌ بلا https يُردّ هنا ولا يُرسل", not up and "https://" in err, err)
        up, err = await fill_save([("#set-ig", "https://instagram.com/x"), ("#set-tag", "ميك اب وتسريحات")], "#savePage")
        rec(T + "«صفحة الحجز» تحفظ الاسم والوصف والروابط وحدها", len(up) == 1 and set(up[0]) - {"updated_at"} == KEYS["page"] and up[0]["tagline"] == "ميك اب وتسريحات", str(up and sorted(up[0])))
        await _H.open_settings(pg, "services", 800)
        up, err = await fill_save([("#set-grp", "-5")], "#saveGrp")
        rec(T + "خصمٌ سالب يُردّ هنا ولا يُرسل", not up and "غير صحيح" in err, err)
        up, err = await fill_save([("#set-grp", "150")], "#saveGrp")
        rec(T + "خصم المجموعة في صفحة الخدمات ويُحفظ وحده", len(up) == 1 and set(up[0]) - {"updated_at"} == KEYS["discount"] and up[0]["group_discount_amount"] == 150, str(up))
        await _H.open_settings(pg, "location", 800)
        up, err = await fill_save([("#set-reqmap", True)], "#saveLoc")
        rec(T + "«الموقع والأحياء» يحفظ رابط الموقع وحده", len(up) == 1 and set(up[0]) - {"updated_at"} == KEYS["location"] and up[0]["require_loc_map"] is True, str(up))

        # ── تغييرٌ لم يُحفظ لا يضيع صامتًا ─────────────────────────────────
        await _H.open_settings(pg, "rules", 800); await fresh(pg)
        await pg.fill("#set-adv", "90")
        await pg.click("#btnRefresh"); await pg.wait_for_timeout(1200)
        rec(T + "إعادة القراءة في الخلفية لا تمسح ما يُكتب", await pg.input_value("#set-adv") == "90", await pg.input_value("#set-adv"))
        await pg.click("#setBack"); await pg.wait_for_timeout(600)
        sh = await pg.evaluate("()=>({open:!document.getElementById('sheet').hidden, t:document.getElementById('sheetTitle').textContent, b:['lvSave','lvDrop','lvStay'].map(i=>!!document.getElementById(i))})")
        rec(T + "الرجوع بتغييرٍ لم يُحفظ يسأل «تحفظين التغييرات؟» بثلاثة أزرار", sh["open"] and sh["t"] == "تحفظين التغييرات؟" and all(sh["b"]), str(sh))
        await pg.click("#lvStay"); await pg.wait_for_timeout(500)
        rec(T + "«ابقي» يبقي الصفحة وما كُتب فيها", await pg.evaluate("()=>!!document.getElementById('saveRules')") and await pg.input_value("#set-adv") == "90")
        await pg.click("[data-tab=agenda]"); await pg.wait_for_timeout(600)
        await pg.click("#lvDrop"); await pg.wait_for_timeout(800)
        tab = await pg.evaluate("()=>document.querySelector('#tabs .tab[aria-current=page]').dataset.tab")
        rec(T + "وتبويبٌ آخر يسأل كذلك، و«اخرجي بلا حفظ» تخرج ولا ترسل", tab == "agenda" and not await pg.evaluate(UPD), f"{tab} {await pg.evaluate(UPD)}")
        await _H.open_settings(pg, "rules", 800); await fresh(pg)
        await pg.fill("#set-adv", "90")
        await pg.click("#setBack"); await pg.wait_for_timeout(600)
        await pg.click("#lvSave"); await pg.wait_for_timeout(1000)
        up = await pg.evaluate(UPD)
        rec(T + "و«احفظي واخرجي» تحفظ ثمّ تعود للقائمة", len(up) == 1 and up[0]["max_advance_days"] == 90
            and await pg.evaluate("()=>document.querySelectorAll('.setrow').length") == 13, str(up))

        # ── المختبر وحده: اشتراطات الأحياء تحت رابط الموقع ───────────────
        await _H.open_settings(pg, "location", 1000)
        order = await pg.evaluate("""()=>{const r=document.getElementById('set-reqmap'), h=document.getElementById('h-on');
            return [!!r, !!h, r&&h ? !!(r.compareDocumentPosition(h) & Node.DOCUMENT_POSITION_FOLLOWING) : null]}""")
        if LAB:
          rec(T + "المختبر: اشتراطات الأحياء في صفحة الموقع بعد رابط الموقع", order == [True, True, True], str(order))
        else:
          rec(T + "الجذر: صفحة الموقع فيها رابط الموقع وحده (الأحياء لم تُرقَّ)", order[:2] == [True, False], str(order))
        await _H.open_settings(pg, "rules", 800)
        await pg.screenshot(path=f"{_H.SHOTS}/23-settings-rules.png", full_page=True)
      rec(T + "لا خطأ في الصفحة", not errs, "; ".join(errs[:2]))
      await ctx.close()
    await b.close()
  ok = sum(1 for _, x in R if x)
  print(f"=== {ok}/{len(R)} passed ===")
  sys.exit(0 if ok == len(R) else 1)

asyncio.run(main())
