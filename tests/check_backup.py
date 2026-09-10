# النسخ الاحتياطي والاستعادة، ونسخةٌ تلقائية قبل كل حذف جماعي.
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import json, asyncio, os, sys, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright
ROOT=str(_H.ROOT); OUT=f"{_H.SHOTS}"
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=socketserver.TCPServer(("127.0.0.1",0),functools.partial(H,directory=ROOT))
PORT=srv.server_address[1]; threading.Thread(target=srv.serve_forever,daemon=True).start()
MOCK=open(os.path.join(ROOT,"dev/mock-supabase.js"),encoding="utf-8").read()
R=[]
def rec(n,ok,note=""): R.append((n,ok)); print(("PASS " if ok else "FAIL ")+n+((" — "+note) if note else ""))

async def settings(pg):
    await pg.evaluate("""()=>{const t=[...document.querySelectorAll('.tab')]
        .find(e=>e.textContent.includes('الإعدادات')); t && t.click();}""")
    await pg.wait_for_timeout(900)

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(**_H.CHROME,args=["--no-sandbox"])
        ctx=await b.new_context(viewport={"width":430,"height":900},device_scale_factor=2,locale="ar-SA")
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript",body=MOCK)))
        errs=[]
        pg=await ctx.new_page()
        await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
        pg.on("pageerror",lambda e:errs.append(str(e)))
        pg.on("console",lambda m:errs.append(m.text) if m.type=="error" and "404" not in m.text else None)
        await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(2000)
        await settings(pg)

        rec("قسم النسخ الاحتياطي ظاهر", await pg.evaluate("()=>!!document.getElementById('bkNew')"))
        empty = await pg.inner_text("#bkList")
        rec("يبدأ فارغًا برسالة مفهومة", "لا نسخ بعد" in empty, empty.strip()[:50])

        # ── إنشاء نسخة ───────────────────────────────────────────────────
        await pg.evaluate("()=>{window.__RPC=[];window.__COPIES=[];}")
        await pg.click("#bkNew"); await pg.wait_for_timeout(1500)
        rpc = await pg.evaluate("()=>(window.__RPC||[]).map(r=>r.name)")
        rec("اللقطة تُطلب من القاعدة", "admin_snapshot" in rpc, str(rpc))
        msg = await pg.inner_text("#bkMsg")
        rec("تقرير النسخة يذكر ما حُفظ", "حُفظت النسخة" in msg and "حجز" in msg, msg.strip()[:70])
        # ما وراء الحجوزات: كان يُحفظ ولا يُذكر، فيُظنّ بالنسخة النقص.
        rec("والتقرير يذكر ما وراء الحجوزات",
            all(w in msg for w in ("رسالة", "زيارة", "عدّاد")), msg.strip()[:110])
        rows = await pg.eval_on_selector_all("#bkList .bkrow","e=>e.length")
        rec("النسخة تظهر في القائمة", rows==1, "صفوف=%d" % rows)

        # ── ما يُنزَّل هو ما يُحفَظ: مصدرٌ واحد لكلمة «نسخة كاملة» ──────────
        blob = await pg.evaluate("""async () => {
          const saved = [];
          const realURL = URL.createObjectURL;
          URL.createObjectURL = (b) => { saved.push(b); return realURL(b); };
          document.getElementById('btnBackup').click();
          await new Promise((r) => setTimeout(r, 900));
          URL.createObjectURL = realURL;
          return saved.length ? await saved[saved.length - 1].text() : null;
        }""")
        try:
            data = json.loads(blob) if blob else {}
        except Exception:
            data = {}
        # الأحياء ومجموعاتها منها: سقطت `admin_snapshot` بعد ٠٠٢٦ لأنّها
        # بقيت تقرأ `district_rules` المحذوف، فلم تُؤخذ نسخةٌ منذ ذلك اليوم
        # — والقائمة هنا كانت أفقرَ من المخطّط فلم تقس النقص.
        WANT = ["settings", "services", "availability_rules", "date_overrides",
                "bookings", "booking_items", "message_templates", "message_outbox",
                "ref_counters", "visits", "activity_log", "receipt_scans",
                "districts", "hood_groups", "hood_group_districts", "hood_group_prices"]
        miss = [k for k in WANT if k not in data]
        rec("الملفّ المنزَّل يحمل كلَّ جدول", not miss, "ناقص: " + (", ".join(miss) or "لا شيء"))
        cnt = (data.get("counts") or {})
        nocount = [k for k in WANT if k not in ("settings", "availability_rules",
                   "date_overrides") and k not in cnt]
        rec("ولكلّ جدولٍ عدّادٌ يُعرَض — فما حُفظ ولم يُذكر لا يُفتقد",
            not nocount, "بلا عدّاد: " + (", ".join(nocount) or "لا شيء"))
        rec("ولا أثرَ لجدولٍ محذوف", "district_rules" not in (blob or ""))
        rec("ولا يحمل حسابات الدخول ولا نصّ الإيصال",
            "admins" not in data and "raw_text" not in (blob or ""),
            "admins" if "admins" in data else "raw_text" if "raw_text" in (blob or "") else "نظيف")
        rec("والملفّ من اللقطة نفسها لا من قراءةٍ ثانية",
            (await pg.evaluate("()=>(window.__RPC||[]).filter(r=>r.name==='admin_snapshot').length")) >= 2,
            "نداءات اللقطة")
        label = await pg.inner_text("#bkList .bkrow .t")
        rec("الصف يحمل تاريخًا مقروءًا", any(m in label for m in
            ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]),
            label.strip())
        acts = await pg.eval_on_selector_all("#bkList .bkacts .btn","e=>e.map(x=>x.textContent.trim())")
        rec("ثلاثة أفعال: استعادة وتنزيل وحذف", acts==["استعادة","تنزيل","حذف"], str(acts))
        copies = await pg.evaluate("()=>(window.__COPIES||[]).length")
        rec("صور الإيصالات تُنسخ إلى دلو النسخ",
            copies>0 and await pg.evaluate("()=>(window.__COPIES||[]).every(c=>c.bucket==='backups')"),
            "نسخ=%d" % copies)
        await pg.screenshot(path=f"{OUT}/backup-list.png", full_page=True)

        # ── الحذف الجماعي يأخذ نسخة تلقائية أوّلًا ────────────────────────
        await pg.evaluate("()=>{window.__RPC=[];}")
        await pg.select_option("#pg-scope","all"); await pg.wait_for_timeout(700)
        await pg.fill("#pg-word","حذف"); await pg.wait_for_timeout(300)
        pg.once("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.click("#pg-go"); await pg.wait_for_timeout(2500)
        order = await pg.evaluate("()=>(window.__RPC||[]).map(r=>r.name)")
        calls = await pg.evaluate("()=>(window.__RPC||[]).map(r=>({n:r.name,dry:r.args&&r.args.p_dry}))")
        names = [c["n"] for c in calls]
        try:
            i_snap = names.index("admin_snapshot")
            i_del  = next(i for i,c in enumerate(calls) if c["n"]=="admin_purge_bookings" and c["dry"] is False)
            good = i_snap < i_del
        except (ValueError, StopIteration):
            good = False
        rec("النسخة تُؤخذ قبل الحذف الفعلي لا بعده", good, str(names))

        await settings(pg); await pg.wait_for_timeout(700)
        rows2 = await pg.eval_on_selector_all("#bkList .bkrow","e=>e.length")
        autos = await pg.eval_on_selector_all("#bkList .bkrow .s","e=>e.filter(x=>x.textContent.includes('تلقائية')).length")
        rec("النسخة التلقائية محفوظة ومميّزة", rows2==2 and autos==1, "صفوف=%d تلقائية=%d" % (rows2, autos))

        # ── الاستعادة تُرجع ما حُذف ───────────────────────────────────────
        gone = await pg.evaluate("()=>window.__STATE_BOOKINGS__ ?? null")
        await pg.evaluate("()=>{window.__RPC=[];}")
        pg.once("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.evaluate("""()=>{const b=[...document.querySelectorAll('[data-bk-get]')]
            .find(x=>!x.dataset.bkGet.includes('-auto')); b.click();}""")
        await pg.wait_for_timeout(2500)
        rpc3 = await pg.evaluate("()=>(window.__RPC||[]).map(r=>r.name)")
        rec("الاستعادة تنادي دالّة القاعدة", "admin_restore_snapshot" in rpc3, str(rpc3))
        arg = await pg.evaluate("()=>{const c=(window.__RPC||[]).find(r=>r.name==='admin_restore_snapshot');return c?c.args:null;}")
        rec("الاستعادة لا تشمل الإعدادات افتراضيًا",
            arg is not None and arg.get("p_include_settings") is False, str(arg and arg.get("p_include_settings")))
        await pg.wait_for_timeout(1200)
        rmsg = await pg.inner_text("#bkMsg")
        rec("تقرير الاستعادة يذكر ما عاد", "عاد" in rmsg or "لا شيء ناقص" in rmsg, rmsg.strip()[:70])
        rec("وتقرير الاستعادة يشمل ما وراء الحجوزات",
            all(w in rmsg for w in ("رسالة", "زيارة")), rmsg.strip()[:120])
        await pg.screenshot(path=f"{OUT}/backup-restored.png", full_page=True)

        await pg.evaluate("""()=>{const t=[...document.querySelectorAll('.tab')]
            .find(e=>e.textContent.includes('الأجندة')); t && t.click();}""")
        await pg.wait_for_timeout(700)
        await settings(pg)
        stale = await pg.inner_text("#bkMsg")
        rec("التقرير يزول بعد مغادرة الشاشة", stale.strip()=="", stale.strip()[:40])

        rec("بلا أخطاء", len(errs)==0, "; ".join(errs[:3]))
        await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
