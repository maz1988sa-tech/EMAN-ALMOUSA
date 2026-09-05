# التصميم الجديد: مشهد اليوم، الزجاج، شارات الخدمات، أفعال البطاقة،
# ورسائل التواصل التي تكتبها إيمان بنفسها.
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, sys, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright
ROOT=str(_H.ROOT); OUT=f"{_H.SHOTS}"
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=socketserver.TCPServer(("127.0.0.1",0),functools.partial(H,directory=ROOT))
PORT=srv.server_address[1]; threading.Thread(target=srv.serve_forever,daemon=True).start()
MOCK=open(os.path.join(ROOT,"dev/mock-supabase.js"),encoding="utf-8").read()
R=[]
def rec(n,ok,note=""): R.append((n,ok)); print(("PASS " if ok else "FAIL ")+n+((" — "+note) if note else ""))

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
        errs=[]
        async def page(hour):
            ctx=await b.new_context(viewport={"width":430,"height":900},device_scale_factor=2,locale="ar-SA")
            await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
                r.fulfill(content_type="application/javascript",body=MOCK)))
            pg=await ctx.new_page()
            await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
            # نثبّت الساعة لنرى كل نطاق
            await pg.add_init_script(f"""
                const R = Date; const H = {hour};
                Date = class extends R {{
                  constructor(...a) {{ super(...(a.length?a:[2026,7,27,H,0,0])); }}
                  static now() {{ return new R(2026,7,27,H,0,0).getTime(); }}
                }};""")
            pg.on("pageerror",lambda e:errs.append(str(e)))
            pg.on("console",lambda m:errs.append(m.text) if m.type=="error" and "404" not in m.text else None)
            await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(2200)
            return ctx, pg

        # ── مشهد اليوم يتبع الساعة بلا تدخّل ──────────────────────────
        for hour, band, label in ((8,'dawn','الصباح'), (13,'noon','الظهيرة'), (17,'dusk','المغرب'), (22,'night','الليل')):
            ctx, pg = await page(hour)
            st = await pg.evaluate("""()=>({
                band:document.documentElement.getAttribute('data-time'),
                on:[...document.querySelectorAll('.scene .layer.on')].map(l=>l.id),
                sky:getComputedStyle(document.querySelector('.scene .sky')).backgroundImage.slice(0,20)})""")
            rec(f"{label}: المشهد يُشتقّ من الساعة", st["band"]==band and st["on"]==[f"sc-{band}"], str(st["band"])+" "+str(st["on"]))
            if band=='dawn':
                await pg.screenshot(path=f"{OUT}/look-dawn.png", full_page=True)
            if band=='night':
                await pg.screenshot(path=f"{OUT}/look-night.png", full_page=True)
                ink = await pg.evaluate("()=>getComputedStyle(document.body).color")
                rec("الليل يقلب الحبر إلى فاتح", "243" in ink or "240" in ink, ink)
            await ctx.close()

        # ── الباقي على مشهد الصباح ────────────────────────────────────
        ctx, pg = await page(8)

        rec("الشعار هو المونوغرام", "mark_sm" in (await pg.get_attribute(".brandmark","src") or ""),
            await pg.get_attribute(".brandmark","src"))
        rec("اسم النشاط في الشريط", (await pg.inner_text("#bizName")).strip() != "",
            await pg.inner_text("#bizName"))

        glass = await pg.evaluate("""()=>{const c=document.querySelector('.bk');
            const s=getComputedStyle(c); return {bd:s.backdropFilter||s.webkitBackdropFilter, r:s.borderRadius};}""")
        rec("البطاقات زجاجية ومستديرة", "blur" in (glass["bd"] or "") and glass["r"].startswith("26"), str(glass))

        font = await pg.evaluate("()=>getComputedStyle(document.body).fontFamily")
        rec("خطّ الواجهة هو المعتمد", "Plex" in font, font[:46])
        fd = await pg.evaluate("()=>getComputedStyle(document.querySelector('.bk .who b')).fontFamily")
        rec("خطّ الأسماء هو خطّ الواجهة", "Plex" in fd, fd[:40])

        # ── شارات الخدمات ─────────────────────────────────────────────
        sv = await pg.eval_on_selector_all(".bk .svcb","e=>e.map(x=>x.innerText.replace(/\\s+/g,' ').trim())")
        rec("كل خدمة بشارتها وعددها", any("×" in x for x in sv) and len(sv)>0, str(sv[:3]))
        icons = await pg.eval_on_selector_all(".bk .svcb svg","e=>e.length")
        rec("لكل شارة أيقونتها", icons>=len(sv), f"أيقونات={icons} شارات={len(sv)}")

        # ── أفعال البطاقة ─────────────────────────────────────────────
        acts = await pg.evaluate("""()=>[...document.querySelectorAll('.bk')][0]
            .querySelectorAll('.qact').length""")
        rec("ثلاثة أفعال على كل بطاقة", acts==3, f"على الأولى={acts}")
        every = await pg.evaluate("""()=>[...document.querySelectorAll('.bk')]
            .every(c=>c.querySelectorAll('.qact').length===3)""")
        rec("ولا بطاقة بلا أفعالها", every is True)
        empt = await pg.eval_on_selector_all(".qact.empty","e=>e.map(x=>x.innerText.trim())")
        rec("الموقع الناقص بإطار مقطّع", len(empt)>0 and "بلا موقع" in empt[0], str(empt[:2]))
        style = await pg.evaluate("()=>{const e=document.querySelector('.qact.empty');return e?getComputedStyle(e).borderStyle:'';}")
        rec("الإطار المقطّع فعلًا مقطّع", style=="dashed", style)
        tel = await pg.get_attribute(".bk .qact[href^='tel']","href")
        rec("زرّ الاتصال يحمل الرقم", tel and tel.startswith("tel:+966"), str(tel))

        # ── قائمة التواصل ─────────────────────────────────────────────
        await pg.evaluate("()=>document.querySelector('.bk [data-msg]').click()")
        await pg.wait_for_timeout(800)
        menu = await pg.evaluate("""()=>{const s=document.querySelector('#sheet.open');
            return s?{t:document.getElementById('sheetTitle').textContent,
                      rows:[...s.querySelectorAll('.rowline .t')].map(x=>x.textContent),
                      wa:[...s.querySelectorAll('[data-send]')].map(x=>x.getAttribute('href'))}:null;}""")
        rec("قائمة التواصل تفتح باسم العميلة", menu and "تواصل مع" in menu["t"], str(menu and menu["t"]))
        rec("الرسائل الثلاث معروضة", menu and len(menu["rows"])==3, str(menu and menu["rows"]))
        rec("الرابط يفتح واتساب بالنصّ", menu and menu["wa"] and "wa.me" in menu["wa"][0], str(menu and menu["wa"][0][:44]))
        rec("الحقول استُبدلت بالبيانات لا بقيت أقواسًا",
            menu and not any("{" in r for r in (menu["wa"] or [])), "")
        await pg.screenshot(path=f"{OUT}/look-msgmenu.png")
        await pg.evaluate("()=>document.querySelector('#sheet .iconbtn')?.click()")
        await pg.wait_for_timeout(500)

        # ── إعدادات الرسائل ومحرّرها ──────────────────────────────────
        await pg.click('[data-tab="settings"]'); await pg.wait_for_timeout(700)
        await pg.click('[data-pane="msgs"]'); await pg.wait_for_timeout(700)
        lst = await pg.eval_on_selector_all("#tplList .rowline .t","e=>e.map(x=>x.textContent)")
        rec("قائمة الرسائل في الإعدادات", len(lst)==3, str(lst))
        kinds = await pg.eval_on_selector_all("#tplList .pill","e=>e.map(x=>x.textContent.trim())")
        rec("تمييز المدمجة عن الخاصة", "خاصة بكِ" in kinds and "مدمجة" in kinds, str(sorted(set(kinds))))

        await pg.click("#tplNew"); await pg.wait_for_timeout(700)
        rec("محرّر رسالة جديدة يفتح", await pg.evaluate("()=>!!document.getElementById('t-body')"))
        fields = await pg.eval_on_selector_all("#t-fields .chip","e=>e.length")
        rec("حقول الاستبدال معروضة", fields>=9, f"حقول={fields}")
        await pg.fill("#t-title","طلب تعديل الموعد")
        await pg.fill("#t-body","أهلاً ")
        await pg.evaluate("""()=>document.querySelector('#t-fields [data-f="{الاسم}"]').click()""")
        await pg.wait_for_timeout(300)
        body = await pg.input_value("#t-body")
        rec("الضغط على حقل يُدرجه في النصّ", "{الاسم}" in body, body)
        prev = await pg.inner_text("#t-prev")
        rec("المعاينة تُبدّل الحقل باسم حقيقي", "{" not in prev and len(prev)>6, prev[:40])
        await pg.screenshot(path=f"{OUT}/look-tpl.png")

        # ── ما سقط في الجولة الأولى: أسطحُ الحالة الفارغة وبطاقة التحيّة ──
        await pg.evaluate("()=>document.querySelector('#sheet.open .iconbtn')?.click()")
        await pg.wait_for_timeout(500)
        await pg.evaluate("""()=>[...document.querySelectorAll('.tab')]
            .find(t=>t.textContent.includes('الرئيسية'))?.click()""")
        await pg.wait_for_timeout(900)
        gr = await pg.evaluate("""()=>{const g=document.querySelector('.greet');
            return g?{h1:g.querySelector('h1').textContent,
                      p:g.querySelector('p').innerText,
                      bg:getComputedStyle(g).backgroundColor}:null;}""")
        rec("بطاقة التحيّة موجودة", gr is not None and "،" in gr["h1"], str(gr and gr["h1"]))
        rec("التحيّة تقول حالة اليوم لا ترحيبًا فارغًا",
            gr and any(k in gr["p"] for k in ("موعد","مواعيد","طلب","طلبات","مكتملة","مفتوحة")), str(gr and gr["p"])[:50])

        surf = await pg.evaluate("""()=>['.arch','.empty:not(.qact)','.appbar .bar','.appbar .tabs'].map(sel=>{
            const e=document.querySelector(sel); if(!e) return {sel,miss:true};
            const s=getComputedStyle(e);
            const a=+(s.backgroundColor.match(/[\d.]+\)$/)||[1])[0].replace(')','');
            return {sel, alpha:a, blur:(s.backdropFilter||s.webkitBackdropFilter||'').includes('blur')};})""")
        for x in surf:
            if x.get("miss"): continue
            rec(f"{x['sel']} سطحٌ يُرى لا فجوة", x["alpha"]>=.15 and x["blur"], str(x))

        rec("بلا أخطاء", len(errs)==0, "; ".join(errs[:3]))
        await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
