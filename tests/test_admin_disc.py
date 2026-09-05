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
        ctx=await b.new_context(viewport={"width":430,"height":900},device_scale_factor=2,locale="ar-SA")
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript",body=MOCK)))
        errs=[]
        pg=await ctx.new_page()
        await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
        pg.on("pageerror",lambda e:errs.append(str(e)))
        pg.on("console",lambda m:errs.append(m.text) if m.type=="error" and "404" not in m.text else None)
        await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(2000)

        tabs = await pg.eval_on_selector_all("#tabs .tab","e=>e.map(x=>x.textContent.replace(/\\s+/g,' ').trim())")
        rec("خمسة تبويبات رئيسية", len(tabs) == 5 and tabs[-1]=="الإعدادات", str(tabs))
        rec("لا تبويب مستقل لأوقات العمل أو الخدمات",
            not any("أوقات" in t or "الخدمات" in t for t in tabs), str(tabs))

        await pg.click('[data-tab="settings"]'); await pg.wait_for_timeout(600)
        panes = await pg.eval_on_selector_all(".panetab","e=>e.map(x=>x.textContent.trim())")
        rec("أربعة أقسام تحت الإعدادات", panes==["عام","أوقات العمل","الخدمات","الرسائل"], str(panes))
        grp = await pg.eval_on_selector("#set-grp","e=>e.value")
        rec("حقل خصم المجموعة يقرأ الإعدادات", grp=="100", f"value={grp!r}")

        # الأقسام تتبدّل ويعمل محتواها
        await pg.click('[data-pane="hours"]'); await pg.wait_for_timeout(600)
        h = await pg.inner_text("#view")
        rec("قسم أوقات العمل يفتح", "أوقات العمل الأسبوعية" in h, h[:40].replace("\n"," "))
        await pg.click('[data-pane="services"]'); await pg.wait_for_timeout(600)
        sv = await pg.inner_text("#view")
        rec("قسم الخدمات يفتح", "الخدمات والأسعار" in sv, sv[:40].replace("\n"," "))
        await pg.screenshot(path=f"{OUT}/settings-services.png", full_page=True)

        # محرّر الخدمة يحمل خانة الخصم بحالتها الصحيحة
        rows = await pg.eval_on_selector_all("#view .rowline","e=>e.length")
        await pg.eval_on_selector_all("#view .rowline",
            "els=>{const t=els.find(e=>e.innerText.includes('سهرة')); (t.querySelector('button')||t).click();}")
        await pg.wait_for_timeout(800)
        st = await pg.evaluate("""()=>{const c=document.getElementById('s-group');
            return c?{present:true,checked:c.checked,name:document.getElementById('s-name').value}:{present:false};}""")
        rec("خانة «يشملها خصم المجموعة» في محرّر الخدمة", st.get("present") is True, str(st))
        rec("الخانة مؤشَّرة لخدمة السهرة", st.get("checked") is True, str(st))
        await pg.screenshot(path=f"{OUT}/service-editor.png", full_page=True)

        rec("بلا أخطاء", len(errs)==0, "; ".join(errs[:3]))
        await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
