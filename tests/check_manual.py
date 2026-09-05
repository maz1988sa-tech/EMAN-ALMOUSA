# الحجز اليدوي: السعر الخاص، خصم المجموعة، وما يُرسَل إلى القاعدة فعلًا.
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
# نسجّل كل إدراج لنقرأ ما وصل القاعدة، لا ما ظهر على الشاشة فقط.
OLD="      insert(v) { return {"
NEW="      insert(v) { (window.__INS = window.__INS || []).push({ t:name, v }); return {"
assert OLD in MOCK, "mock insert() shape changed"
MOCK=MOCK.replace(OLD,NEW,1)
OLDU = "      update(v) { return {"
NEWU = "      update(v) { (window.__UPD = window.__UPD || []).push({ t:name, v }); return {"
assert OLDU in MOCK, "mock update() shape changed"
MOCK = MOCK.replace(OLDU, NEWU, 1)
# بنود الحجز في النسخة المشتركة بلا service_id فلا تقابل عدّادًا. نُلحقها هنا
# وحدها — دون المساس بتلك النسخة — لنختبر ورقة التعديل على حجزٍ جماعي يحمل
# سعرًا خاصًّا محفوظًا.
for _a, _b in [("{id:'i3',service_name:'ميك اب عروس'", "{id:'i3',service_id:'s1',service_name:'ميك اب عروس'"),
               ("{id:'i4',service_name:'ميك اب سهرة'", "{id:'i4',service_id:'s2',service_name:'ميك اب سهرة'"),
               ("{id:'i5',service_name:'ميك اب سهرة'", "{id:'i5',service_id:'s2',service_name:'ميك اب سهرة'")]:
    assert _a in MOCK, _a
    MOCK = MOCK.replace(_a, _b, 1)
MOCK = MOCK.replace("person_name:'لمى',price:600", "person_name:'لمى',price:500", 1)
MOCK = MOCK.replace("person_name:'هند',price:600", "person_name:'هند',price:500", 1)
R=[]
def rec(n,ok,note=""): R.append((n,ok)); print(("PASS " if ok else "FAIL ")+n+((" — "+note) if note else ""))

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

        # فتح ورقة الحجز اليدوي
        await pg.eval_on_selector_all("button, a",
            "els=>{const t=els.find(e=>/حجز يدوي|إضافة حجز/.test(e.textContent)); t && t.click();}")
        await pg.wait_for_timeout(700)
        # صار الزرّ يسأل: فردٌ أم مجموعة؟ فنمضي إلى الفرديّة.
        if await pg.evaluate("()=>!!document.getElementById('k-one')"):
            await pg.click("#k-one"); await pg.wait_for_timeout(700)
        opened = await pg.evaluate("()=>!!document.getElementById('n-save')")
        rec("ورقة الحجز اليدوي تفتح", opened)
        if not opened:
            print("\n=== 0/1 passed ==="); sys.exit(1)

        # ١) حقل السعر الخاص مخفيّ ما دام العدّاد صفرًا
        vis0 = await pg.eval_on_selector_all(".priceline","e=>e.filter(x=>!x.hidden).length")
        rec("سعر خاص مخفيّ قبل اختيار الخدمة", vis0==0, f"ظاهرة={vis0}")

        sid = await pg.evaluate("()=>document.querySelectorAll('[data-nd=\"+\"]')[1].dataset.sid")
        plus = f'[data-nd="+"][data-sid="{sid}"]'
        await pg.click(plus); await pg.wait_for_timeout(250)
        vis1 = await pg.eval_on_selector_all(".priceline","e=>e.filter(x=>!x.hidden).length")
        rec("سعر خاص يظهر مع أوّل شخص", vis1==1, f"ظاهرة={vis1}")
        sum1 = await pg.inner_text("#n-sum")
        rec("الإجمالي بسعر القائمة لشخص واحد", sum1.strip().startswith("600"), sum1)

        # ٢) خصم المجموعة يظهر من شخصين
        d1 = await pg.eval_on_selector("#n-disc","e=>e.hidden")
        rec("لا خصم على شخص واحد", d1 is True)
        await pg.click(plus); await pg.wait_for_timeout(250)
        d2 = await pg.evaluate("()=>{const e=document.getElementById('n-disc');return {h:e.hidden,t:e.textContent};}")
        rec("خصم المجموعة يظهر من شخصين", d2["h"] is False and "200" in d2["t"], str(d2))
        sum2 = await pg.inner_text("#n-sum")
        rec("الإجمالي بعد الخصم ١٢٠٠−٢٠٠", sum2.strip().startswith("1,000"), sum2)

        # ٣) السعر الخاص يعلو على سعر القائمة
        await pg.fill(f'[data-nprice="{sid}"]', "1000"); await pg.wait_for_timeout(300)
        sum3 = await pg.inner_text("#n-sum")
        rec("السعر الخاص يعيد حساب الإجمالي — ٢٠٠٠−٢٠٠", sum3.strip().startswith("1,800"), sum3)
        await pg.screenshot(path=f"{OUT}/manual-custom-price.png", full_page=True)

        # ٤) ما يصل القاعدة: خصم لكل شخص + السعر المكتوب
        await pg.fill("#n-name","تجربة السعر الخاص")
        await pg.fill("#n-phone","٠٥٠١٢٣٤٥٦٧")
        await pg.evaluate("()=>{window.__INS=[];window.__RPC=[];}")
        await pg.click("#n-save"); await pg.wait_for_timeout(900)
        rpc = await pg.evaluate("()=>window.__RPC||[]")
        ins = await pg.evaluate("()=>window.__INS||[]")
        call = next((r["args"] for r in rpc if r["name"]=="admin_create_booking"), None)
        rec("الحفظ يمرّ بنداء ذرّي واحد", call is not None, "نداءات=%s" % [r["name"] for r in rpc])
        rec("لا كتابة مباشرة في الجداول",
            not any(r["t"] in ("bookings","booking_items") for r in ins),
            "إدراجات=%s" % [r["t"] for r in ins])
        if call:
            bk = call.get("p_booking") or {}
            it = call.get("p_items") or []
            rec("discount_per_person مُرسَل بقيمة الإعدادات",
                Number(bk.get("discount_per_person"))==100, str(bk.get("discount_per_person")))
            rec("الحالة مؤكّدة", bk.get("status")=="confirmed", str(bk.get("status")))
            rec("الجوال موحَّد من العربي إلى صيغة القاعدة",
                bk.get("client_phone")=="966501234567", str(bk.get("client_phone")))
            rec("مفتاح التكرار مُرسَل", bool(call.get("p_idem")) and len(str(call.get("p_idem")))>=32,
                str(call.get("p_idem")))
            prices=[Number(x.get("price")) for x in it]
            rec("السعر الخاص هو ما حُفظ في البنود", prices==[1000,1000], str(prices))
            rec("بنود مؤهَّلة للخصم", all(x.get("group_discount") for x in it),
                str([x.get("group_discount") for x in it]))

        # ── ورقة التعديل: السعر المحفوظ والخصم ──────────────────────────
        await pg.evaluate("()=>{const t=[...document.querySelectorAll('.tab')].find(e=>e.textContent.includes('الحجوزات')); t && t.click();}")
        await pg.wait_for_timeout(800)
        await pg.evaluate("()=>{const b=document.querySelector('[data-st=\"all\"]'); b && b.click();}")
        await pg.wait_for_timeout(700)
        await pg.evaluate("()=>{const rows=[...document.querySelectorAll('[data-open]')]; const t=rows.find(e=>e.innerText.includes('سارة')) || rows[0]; t.click();}")
        await pg.wait_for_timeout(900)
        await pg.click("#d-edit"); await pg.wait_for_timeout(900)

        st = await pg.evaluate("()=>({counts:[...document.querySelectorAll('[data-ev]')].map(e=>e.textContent.trim()),prices:[...document.querySelectorAll('[data-eprice]')].map(e=>e.value),shown:[...document.querySelectorAll('[data-ep]')].filter(e=>!e.hidden).length,sum:document.getElementById('e-sum').innerText,disc:{h:document.getElementById('e-disc').hidden,t:document.getElementById('e-disc').textContent}})")
        rec("عدّادات التعديل تقرأ بنود الحجز", st["counts"][:3]==["1","2","0"], str(st["counts"]))
        rec("السعر الخاص المحفوظ يعود في الحقل", st["prices"][:2]==["1500","500"], str(st["prices"]))
        rec("حقول السعر تظهر للخدمات المختارة فقط", st["shown"]==2, "ظاهرة=%s" % st["shown"])
        rec("خصم المجموعة يظهر في التعديل", st["disc"]["h"] is False and "200" in st["disc"]["t"], str(st["disc"]))
        rec("الإجمالي ١٥٠٠+٥٠٠×٢−٢٠٠", st["sum"].strip().startswith("2,300"), st["sum"])
        await pg.screenshot(path=f"{OUT}/edit-custom-price.png", full_page=True)

        # تغيير السعر وحده يستوجب إعادة بناء البنود
        esid = await pg.evaluate("()=>document.querySelectorAll('[data-eprice]')[1].dataset.eprice")
        await pg.fill(f'[data-eprice="{esid}"]', "400"); await pg.wait_for_timeout(300)
        sum4 = await pg.inner_text("#e-sum")
        rec("تغيير السعر يعيد حساب إجمالي التعديل — ١٥٠٠+٨٠٠−٢٠٠", sum4.strip().startswith("2,100"), sum4)

        await pg.evaluate("()=>{window.__INS=[];window.__UPD=[];window.__RPC=[];}")
        await pg.click("#e-save"); await pg.wait_for_timeout(1000)
        rpc2 = await pg.evaluate("()=>window.__RPC||[]")
        ins2 = await pg.evaluate("()=>window.__INS||[]")
        rep = next((r["args"] for r in rpc2 if r["name"]=="admin_replace_items"), None)
        rec("تغيير السعر وحده يعيد بناء البنود بنداء ذرّي", rep is not None,
            "نداءات=%s" % [r["name"] for r in rpc2])
        rec("لا حذف/إدراج مباشر للبنود",
            not any(r["t"]=="booking_items" for r in ins2), "إدراجات=%s" % [r["t"] for r in ins2])
        if rep:
            pr = sorted(Number(x.get("price")) for x in (rep.get("p_items") or []))
            rec("البنود حُفظت بالسعر الجديد", pr==[400,400,1500], str(pr))
            rec("خصم لكل شخص يُمرَّر مع البنود",
                Number(rep.get("p_discount_per_person"))==100,
                str(rep.get("p_discount_per_person")))

        rec("بلا أخطاء", len(errs)==0, "; ".join(errs[:3]))
        await b.close()

def Number(v):
    try: return float(v)
    except (TypeError, ValueError): return None

asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
