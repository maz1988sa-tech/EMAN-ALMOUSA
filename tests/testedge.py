import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, json, os, re, sys, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright
ROOT=str(_H.ROOT); OUT=f"{_H.SHOTS}"
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
    def send_head(self):
        rng=self.headers.get('Range')
        if not rng: return super().send_head()
        path=self.translate_path(self.path)
        try: f=open(path,'rb')
        except OSError: self.send_error(404); return None
        size=os.fstat(f.fileno()).st_size
        m=re.match(r'bytes=(\d*)-(\d*)',rng)
        a=int(m.group(1)) if m.group(1) else 0
        b=int(m.group(2)) if m.group(2) else size-1
        b=min(b,size-1); ln=b-a+1
        self.send_response(206); self.send_header('Content-Type',self.guess_type(path))
        self.send_header('Content-Range',f'bytes {a}-{b}/{size}'); self.send_header('Content-Length',str(ln))
        self.end_headers(); f.seek(a); self.wfile.write(f.read(ln)); f.close(); return None
srv=socketserver.TCPServer(("127.0.0.1",0),functools.partial(H,directory=ROOT))
PORT=srv.server_address[1]; threading.Thread(target=srv.serve_forever,daemon=True).start()
BASE=f"http://127.0.0.1:{PORT}/"
MOCK=open(os.path.join(ROOT,"dev/mock-supabase.js"),encoding="utf-8").read()
R=[]
def rec(n,ok,note=""): R.append((n,ok)); print(("PASS " if ok else "FAIL ")+n+((" — "+note) if note else ""))

# variants of the mock
CLOSED = MOCK.replace("accepting_bookings:true","accepting_bookings:false")
BOOM   = MOCK.replace("const ok = (data) => Promise.resolve({ data, error: null });",
                      "const ok = (data) => Promise.resolve({ data, error: null });\n  const boom = () => Promise.resolve({ data:null, error:{message:'network down'} });")
BOOM   = BOOM.replace("        from: table,", "        from: () => ({ select(){return this;}, eq(){return this;}, order(){return this;}, then(r){return r({data:null,error:{message:'network down'}});} }),")
BOOM   = BOOM.replace("        rpc(fn, args) {", "        rpc(fn, args) {\n          return Promise.resolve({data:null,error:{message:'network down'}});")
SLOTGONE = MOCK.replace(
    """            return ok([{ ref:'EA-20260805', public_token:'tok-demo', the_date:args.p_date,
                         start_time:args.p_time, price:1500 }]);""",
    """            return Promise.resolve({data:null,error:{message:'هذا الموعد لم يعد متاحًا، اختاري وقتًا آخر'}});""")
assert SLOTGONE != MOCK, 'slot-gone variant did not apply'

# فشل عام من الخادم: اللوحة تبقى مفتوحة والرسالة داخلها.
GENERICFAIL = MOCK.replace(
    """            return ok([{ ref:'EA-20260805', public_token:'tok-demo', the_date:args.p_date,
                         start_time:args.p_time, price:1500 }]);""",
    """            return Promise.resolve({data:null,error:{message:'تعذّر الاتصال بالخادم'}});""")
assert GENERICFAIL != MOCK, 'generic-fail variant did not apply'

async def newpage(ctx, mock, url="index.html"):
    await ctx.unroute("**/assets/vendor/supabase.js")
    await ctx.route("**/assets/vendor/supabase.js",
        lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript", body=mock)))
    pg=await ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
    await pg.goto(BASE+url); await pg.wait_for_timeout(1700)
    return pg, errs

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(**_H.CHROME,
                                  args=["--no-sandbox","--autoplay-policy=no-user-gesture-required"])
        ctx=await b.new_context(viewport={"width":430,"height":700},device_scale_factor=2,
                                locale="ar-SA",has_touch=True,is_mobile=True)

        # 1) browsing with no service picked
        pg,e = await newpage(ctx, MOCK)
        await pg.evaluate("window.__goto(4)"); await pg.wait_for_timeout(900)
        bk = await pg.evaluate("()=>{const b=document.getElementById('booked');return !b.hidden;}")
        hasCls = await pg.evaluate("()=>document.querySelector('.contact').classList.contains('has-booking')")
        wa = await pg.evaluate("()=>!!document.querySelector('.wa')")
        rec("no service picked → plain contact screen", (not bk) and (not hasCls) and wa, f"booked={bk} cls={hasCls}")
        over = await pg.evaluate("()=>{const p=document.querySelector('#deck .screen:nth-child(5) .pad');return p.scrollHeight-p.clientHeight;}")
        rec("plain contact fits at 700", over<=0, f"over={over}")
        await pg.screenshot(path=f"{OUT}/edge-contact-plain.png")
        await pg.evaluate("window.__goto(1)"); await pg.wait_for_timeout(800)
        cartVisible = await pg.evaluate("""()=>{const c=document.getElementById('svcCart');
          const r=c.getBoundingClientRect();
          return c.classList.contains('on') || (r.bottom > 0 && r.top < window.innerHeight - 2);}""")
        rec("cart bar parked off-screen with empty cart", not cartVisible, f"onscreen={cartVisible}")
        await pg.evaluate("window.__pick(0,1)"); await pg.wait_for_timeout(700)
        cartOn = await pg.evaluate("""()=>{const c=document.getElementById('svcCart');
          return c.classList.contains('on') && c.getBoundingClientRect().bottom <= window.innerHeight + 1;}""")
        rec("cart bar slides in once a service is picked", cartOn, "")
        await pg.evaluate("window.__pick(0,0)"); await pg.wait_for_timeout(700)
        links = await pg.evaluate("""()=>{const g=k=>document.querySelector(`[data-link="${k}"]`);
          return {ig:g('instagram').getAttribute('href'), igH:g('instagram').hidden,
                  tt:g('tiktok').getAttribute('href'),    ttH:g('tiktok').hidden};}""")
        rec("social links come from settings",
            links["ig"]=="https://instagram.com/example" and links["tt"]=="https://tiktok.com/@example"
            and not links["igH"] and not links["ttH"], str(links)[:90])
        rec("no errors on plain path", len(e)==0, "; ".join(e[:3]))
        await pg.close()

        # قناة بلا رابط تُخفى بدل أن تبقى زرًّا لا يفعل شيئًا
        NOTT = MOCK.replace("tiktok_url:'https://tiktok.com/@example',", "tiktok_url:null,")
        pg,e = await newpage(ctx, NOTT)
        await pg.evaluate("window.__goto(4)"); await pg.wait_for_timeout(900)
        st = await pg.evaluate("""()=>({tt:document.querySelector('[data-link="tiktok"]').hidden,
          ig:document.querySelector('[data-link="instagram"]').hidden,
          cols:getComputedStyle(document.querySelector('.c-pair')).gridTemplateColumns})""")
        rec("channel with no link is hidden, the other fills the row",
            st["tt"] and not st["ig"] and st["cols"].count(" ")==0, str(st)[:80])
        over = await pg.evaluate("()=>{const p=document.querySelector('#deck .screen:nth-child(5) .pad');return p.scrollHeight-p.clientHeight;}")
        rec("contact still fits with one channel", over<=0, f"over={over}")
        await pg.close()

        # 2) bookings closed
        pg,e = await newpage(ctx, CLOSED)
        txt = await pg.inner_text("#svcRail")
        closed = "مغلق" in txt or "تواصلي" in txt
        rec("accepting_bookings=false → closed notice on services", closed, txt.replace("\n"," ")[:90])
        rec("no errors when closed", len(e)==0, "; ".join(e[:3]))
        await pg.screenshot(path=f"{OUT}/edge-closed.png")
        await pg.close()

        # 3) data layer down
        pg,e = await newpage(ctx, BOOM)
        txt = await pg.inner_text("#svcRail")
        shown = ("تعذّر" in txt or "خطأ" in txt or "تواصلي" in txt or "المحاولة" in txt)
        rec("data layer down → error state, not blank", shown and len(txt.strip())>0, txt.replace("\n"," ")[:90])
        blank = await pg.evaluate("()=>document.getElementById('svcRail').innerHTML.trim().length")
        rec("services rail not left empty on failure", blank>50, f"len={blank}")
        await pg.screenshot(path=f"{OUT}/edge-down.png")
        await pg.close()

        # 4) single service, qty 1 → one person field, and submit failure keeps the sheet open
        pg,e = await newpage(ctx, SLOTGONE)
        await pg.evaluate("window.__pick(1,1)"); await pg.wait_for_timeout(400)
        await pg.click("#cartGo"); await pg.wait_for_timeout(1300)
        await pg.eval_on_selector("#week .day:not(.blank):not([disabled])","e=>e.click()"); await pg.wait_for_timeout(1200)
        n = await pg.eval_on_selector_all("#times button","e=>e.length")
        rec("shorter duration → more slots offered", n>=4, f"slots={n}")
        await pg.eval_on_selector("#times button:not([disabled])","e=>e.click()"); await pg.wait_for_timeout(400)
        await pg.click("#toConfirm"); await pg.wait_for_timeout(1100)
        await pg.click("#confirmBtn"); await pg.wait_for_timeout(700)
        pf = await pg.eval_on_selector_all("#peopleFields input","e=>e.length")
        rec("single item ⇒ no extra name fields", pf==0, f"fields={pf}")
        await pg.fill("#nm","ريم"); await pg.fill("#ph","0555554444"); await pg.fill("#locTxt","حي النخيل")
        await pg.wait_for_timeout(300)
        await pg.click("#toPay"); await pg.wait_for_timeout(600)

        # صيغة غير مدعومة تُرفض قبل أن تصل الشبكة
        import tempfile, os as _os
        bad = _os.path.join(tempfile.gettempdir(), "notes.txt")
        open(bad, "w").write("not a receipt")
        await pg.set_input_files("#rcptFile", bad); await pg.wait_for_timeout(500)
        e1 = await pg.evaluate("()=>{const e=document.getElementById('payErr');return {shown:!e.hidden,txt:e.textContent.trim()};}")
        d1 = await pg.get_attribute("#sendBooking","disabled")
        rec("unsupported file rejected locally", e1["shown"] and d1 is not None, e1["txt"][:60])

        # ملف أكبر من الحد يُرفض محليًا أيضًا
        big = _os.path.join(tempfile.gettempdir(), "big.jpg")
        open(big, "wb").write(b"\xff\xd8\xff" + b"0" * (6 * 1024 * 1024))
        await pg.set_input_files("#rcptFile", big); await pg.wait_for_timeout(500)
        e2 = await pg.evaluate("()=>{const e=document.getElementById('payErr');return {shown:!e.hidden,txt:e.textContent.trim()};}")
        d2 = await pg.get_attribute("#sendBooking","disabled")
        rec("oversized file rejected locally", e2["shown"] and d2 is not None, e2["txt"][:60])

        # ملف صالح ⇒ الإرسال يسقط على القاعدة، لا على الرفع
        await pg.set_input_files("#rcptFile",f"{_H.SAMPLE}"); await pg.wait_for_timeout(600)
        await pg.wait_for_function("()=>!document.getElementById('sendBooking').disabled", timeout=8000)
        await pg.click("#sendBooking"); await pg.wait_for_timeout(2400)
        # الوقت سُبق إليه ⇒ العودة إلى شاشة الموعد لا البقاء أمام رسالة
        back = await pg.get_attribute("#app","data-screen")
        closed = await pg.evaluate("()=>!document.getElementById('sheet').classList.contains('open')")
        rec("slot taken meanwhile → back to the date screen", back=="2" and closed, f"screen={back} closed={closed}")
        await pg.screenshot(path=f"{OUT}/edge-submit-fail.png")
        await pg.close()

        # 4a-2) فشل عام: اللوحة تبقى مفتوحة، والإعادة لا ترفع الملف مرتين
        pg,e = await newpage(ctx, GENERICFAIL)
        await pg.evaluate("window.__pick(1,1)"); await pg.wait_for_timeout(400)
        await pg.click("#cartGo"); await pg.wait_for_timeout(1300)
        await pg.eval_on_selector("#week .day:not(.blank):not([disabled])","e=>e.click()"); await pg.wait_for_timeout(1100)
        await pg.eval_on_selector("#times button:not([disabled])","e=>e.click()"); await pg.wait_for_timeout(400)
        await pg.click("#toConfirm"); await pg.wait_for_timeout(1000)
        await pg.click("#confirmBtn"); await pg.wait_for_timeout(600)
        await pg.fill("#nm","ريم"); await pg.fill("#ph","0555554444"); await pg.fill("#locTxt","حي النخيل"); await pg.wait_for_timeout(300)
        await pg.click("#toPay"); await pg.wait_for_timeout(600)
        await pg.set_input_files("#rcptFile",f"{_H.SAMPLE}"); await pg.wait_for_timeout(600)
        await pg.wait_for_function("()=>!document.getElementById('sendBooking').disabled", timeout=8000)
        await pg.click("#sendBooking"); await pg.wait_for_timeout(2200)
        err = await pg.evaluate("()=>{const e=document.getElementById('payErr');return {shown:!e.hidden&&getComputedStyle(e).display!=='none',txt:e.textContent.trim()};}")
        still = await pg.evaluate("()=>document.getElementById('sheet').classList.contains('open')")
        rec("booking failure → message in the deposit pane", err["shown"] and len(err["txt"])>0, err["txt"][:70])
        rec("booking failure → sheet stays open", still, "")
        again = await pg.get_attribute("#sendBooking","disabled")
        rec("send re-enabled after failure", again is None, f"disabled={again}")
        n1 = await pg.evaluate("()=>[...(window.__UPLOADED__||[])].length")
        await pg.click("#sendBooking"); await pg.wait_for_timeout(2200)
        n2 = await pg.evaluate("()=>[...(window.__UPLOADED__||[])].length")
        rec("retry does not re-upload the same receipt", n1==1 and n2==1, f"{n1} -> {n2}")
        await pg.close()

        # 4b) الرفع نفسه يسقط
        pg,e = await newpage(ctx, MOCK)
        await pg.evaluate("window.__UPLOAD_FAILS__ = true")
        await pg.evaluate("window.__pick(0,1)"); await pg.wait_for_timeout(400)
        await pg.click("#cartGo"); await pg.wait_for_timeout(1300)
        await pg.eval_on_selector("#week .day:not(.blank):not([disabled])","e=>e.click()"); await pg.wait_for_timeout(1100)
        await pg.eval_on_selector("#times button:not([disabled])","e=>e.click()"); await pg.wait_for_timeout(400)
        await pg.click("#toConfirm"); await pg.wait_for_timeout(1000)
        await pg.click("#confirmBtn"); await pg.wait_for_timeout(600)
        await pg.fill("#nm","هند"); await pg.fill("#ph","0533221100"); await pg.fill("#locTxt","حي النخيل"); await pg.wait_for_timeout(300)
        await pg.click("#toPay"); await pg.wait_for_timeout(600)
        # الرفع صار يبدأ لحظة اختيار الملف، فيظهر عطبه في سطر الفحص
        # ويبقى زرّ الإرسال معطّلًا — لا تُكتشف المشكلة بعد الضغط.
        await pg.set_input_files("#rcptFile",f"{_H.SAMPLE}")
        await pg.wait_for_timeout(2000)
        e3 = await pg.evaluate("()=>{const c=document.getElementById('rcptChk');"
                               "return {shown:!c.hidden, bad:c.classList.contains('bad'), txt:c.textContent.trim()};}")
        dis = await pg.get_attribute("#sendBooking","disabled")
        booked = await pg.evaluate("()=>{const b=document.getElementById('booked');return !b.hidden;}")
        rec("upload failure → message, no booking created",
            e3["shown"] and e3["bad"] and dis is not None and not booked, e3["txt"][:60])
        await pg.close()

        # 4c) لا آيبان في الإعدادات ⇒ بديل واتساب بدل صندوق بنكي فارغ
        NOIBAN = MOCK.replace("iban:'SA0380000000608010167519',", "iban:null,")
        pg,e = await newpage(ctx, NOIBAN)
        await pg.evaluate("window.__pick(0,1)"); await pg.wait_for_timeout(400)
        await pg.click("#cartGo"); await pg.wait_for_timeout(1300)
        await pg.eval_on_selector("#week .day:not(.blank):not([disabled])","e=>e.click()"); await pg.wait_for_timeout(1100)
        await pg.eval_on_selector("#times button:not([disabled])","e=>e.click()"); await pg.wait_for_timeout(400)
        await pg.click("#toConfirm"); await pg.wait_for_timeout(1000)
        await pg.click("#confirmBtn"); await pg.wait_for_timeout(600)
        await pg.fill("#nm","لمى"); await pg.fill("#ph","0512340000"); await pg.fill("#locTxt","حي النخيل"); await pg.wait_for_timeout(300)
        await pg.click("#toPay"); await pg.wait_for_timeout(600)
        st = await pg.evaluate("""()=>({bank:!document.getElementById('bankBox').hidden,
          miss:!document.getElementById('bankMissing').hidden,
          wa:document.getElementById('bankWa').getAttribute('href')||''})""")
        rec("no IBAN → bank box hidden, WhatsApp offered",
            (not st["bank"]) and st["miss"] and "wa.me" in st["wa"], str(st)[:90])
        await pg.screenshot(path=f"{OUT}/edge-no-iban.png")
        await pg.close()

        # 5) month navigation
        pg,e = await newpage(ctx, MOCK)
        await pg.evaluate("window.__pick(0,1)"); await pg.wait_for_timeout(300)
        await pg.click("#cartGo"); await pg.wait_for_timeout(1300)
        # الشريط كما في لوحة إيمان: الاسم في الوسط وسهمان حوله
        nav = await pg.evaluate("""()=>{const n=document.getElementById('calNav');
          const lab=document.getElementById('monthLabel');
          const pv=document.getElementById('mPrev'), nx=document.getElementById('mNext');
          if(!n||!lab||!pv||!nx) return null;
          const nr=n.getBoundingClientRect(), lr=lab.getBoundingClientRect();
          const pr=pv.getBoundingClientRect();
          return {label:lab.textContent.trim(),
                  font: parseFloat(getComputedStyle(lab).fontSize),
                  btn: Math.round(pr.width), btnH: Math.round(pr.height),
                  centred: Math.abs((lr.left+lr.right)/2-(nr.left+nr.right)/2) <= 2,
                  prevOnRight: pv.getBoundingClientRect().left > nx.getBoundingClientRect().left,
                  prevOff: pv.disabled, oldPicker: !!document.getElementById('mpick')};}""")
        rec("month name sits centred between two arrows", nav and nav["centred"], str(nav and nav["label"]))
        rec("previous sits on the right in RTL", nav and nav["prevOnRight"], "")
        rec("previous is barred at this month", nav and nav["prevOff"], "")
        rec("the month name is big enough to read", nav and nav["font"] >= 19,
            f'{nav and nav["font"]}px')
        rec("and each arrow is a comfortable tap target",
            nav and nav["btn"] >= 44 and nav["btnH"] >= 44,
            f'{nav and nav["btn"]}×{nav and nav["btnH"]}')
        rec("the old dropdown picker is gone", nav and not nav["oldPicker"], "")
        m0 = await pg.text_content("#monthLabel")
        await pg.click("#mNext"); await pg.wait_for_timeout(1500)
        m1 = await pg.text_content("#monthLabel")
        days = await pg.eval_on_selector_all("#week .day:not(.blank)","e=>e.length")
        rec("the next arrow reloads the grid", m1!=m0 and days>=28, f"{m0} -> {m1}, days={days}")
        prevOn = await pg.evaluate("()=>!document.getElementById('mPrev').disabled")
        rec("and previous opens once past this month", prevOn, "")
        await pg.click("#mPrev"); await pg.wait_for_timeout(1400)
        m2 = await pg.text_content("#monthLabel")
        rec("stepping back returns to it", m2==m0, f"{m1} -> {m2}")
        far = await pg.evaluate("""async ()=>{const nx=document.getElementById('mNext');
          for (let i=0;i<24 && !nx.disabled;i++){ nx.click();
            await new Promise(r=>setTimeout(r,140)); }
          return {off:nx.disabled, label:document.getElementById('monthLabel').textContent.trim()};}""")
        rec("and the next arrow stops at the booking horizon", far["off"], str(far["label"]))
        rec("no errors during month navigation", len(e)==0, "; ".join(e[:3]))
        await pg.screenshot(path=f"{OUT}/edge-monthpick.png")
        await pg.close()

        # 6) changing the cart after picking a date invalidates the slot
        pg,e = await newpage(ctx, MOCK)
        await pg.evaluate("window.__pick(0,1)"); await pg.wait_for_timeout(300)
        await pg.click("#cartGo"); await pg.wait_for_timeout(1300)
        await pg.eval_on_selector("#week .day:not(.blank):not([disabled])","e=>e.click()"); await pg.wait_for_timeout(1100)
        await pg.eval_on_selector("#times button:not([disabled])","e=>e.click()"); await pg.wait_for_timeout(400)
        await pg.click("#changeSvc"); await pg.wait_for_timeout(1100)
        await pg.evaluate("window.__pick(1,1)"); await pg.wait_for_timeout(400)
        st = await pg.evaluate("()=>({d:window.__state?window.__state.date:null})")
        dis = await pg.evaluate("()=>{window.__goto(2);return null;}")
        await pg.wait_for_timeout(900)
        cta = await pg.get_attribute("#toConfirm","disabled")
        calBack = await pg.evaluate("()=>{const c=document.getElementById('cal');return !c.hidden;}")
        rec("changing the cart clears date+time", cta is not None and calBack, f"cta_disabled={cta is not None} cal_open={calBack}")
        rec("no errors on cart change", len(e)==0, "; ".join(e[:3]))
        await pg.close()
        await b.close()
asyncio.run(main())
bad=[r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R)-len(bad), len(R)))
sys.exit(1 if bad else 0)
