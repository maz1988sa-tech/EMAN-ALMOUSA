import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, json, os, re, subprocess, sys, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright

ROOT = str(_H.ROOT)
OUT  = f"{_H.SHOTS}"
os.makedirs(OUT, exist_ok=True)

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
        self.send_response(206)
        self.send_header('Content-Type',self.guess_type(path))
        self.send_header('Content-Range',f'bytes {a}-{b}/{size}')
        self.send_header('Content-Length',str(ln))
        self.send_header('Accept-Ranges','bytes')
        self.end_headers()
        f.seek(a)
        self.wfile.write(f.read(ln)); f.close(); return None
srv = socketserver.TCPServer(("127.0.0.1",0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{PORT}/"

MOCK = open(os.path.join(ROOT,"dev/mock-supabase.js"),encoding="utf-8").read()
RESULTS=[]
def rec(name, ok, note=""):
    RESULTS.append((name, ok, note))
    print(("PASS " if ok else "FAIL ")+name+(("  — "+note) if note else ""))

async def main(h):
    async with async_playwright() as p:
        b = await p.chromium.launch(**_H.CHROME,
                                    args=["--no-sandbox","--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width":430,"height":h}, device_scale_factor=2, locale="ar-SA",
                                  has_touch=True, is_mobile=True)
        await ctx.route("**/assets/vendor/supabase.js",
                        lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript", body=MOCK)))
        errs=[]
        page = await ctx.new_page()
        page.on("console", lambda m: errs.append(f"console.{m.type}: {m.text}") if m.type=="error" else None)
        page.on("pageerror", lambda e: errs.append(f"PAGEERROR: {e}"))
        await page.goto(BASE+"index.html")
        await page.wait_for_timeout(1800)

        # ---- 1. services rendered from DB
        n = await page.eval_on_selector_all("#svcRail .svc[data-svc]","els=>els.length")
        rec(f"[{h}] services rendered from getServices()", n==3, f"cards={n}")
        names = await page.eval_on_selector_all("#svcRail .svc[data-svc] .s-title, #svcRail .svc[data-svc] h2","els=>els.map(e=>e.textContent.trim())")
        print("   names:", names)

        # ---- 2. swipe = exactly one screen
        async def swipe(dy):
            await page.evaluate("""(dy)=>{const d=document.getElementById('deck');
              const t=(type,y)=>{const ev=new TouchEvent(type,{bubbles:true,cancelable:true,
                touches:type==='touchend'?[]:[new Touch({identifier:1,target:d,clientX:200,clientY:y})],
                changedTouches:[new Touch({identifier:1,target:d,clientX:200,clientY:y})]});d.dispatchEvent(ev);};
              t('touchstart',500); t('touchmove',500+dy*0.5); t('touchmove',500+dy); t('touchend',500+dy);}""", dy)
            await page.wait_for_timeout(760)
        s0 = await page.get_attribute("#app","data-screen")
        await swipe(-160)
        s1 = await page.get_attribute("#app","data-screen")
        rec(f"[{h}] one swipe = exactly one screen", int(s1)-int(s0)==1, f"{s0}->{s1}")
        await page.screenshot(path=f"{OUT}/{h}-2-services.png")

        # ---- 3. pick services (multi + qty) then continue
        await page.evaluate("window.__pick(0,2)")
        await page.wait_for_timeout(200)
        await page.evaluate("window.__pick(1,1)")
        await page.wait_for_timeout(300)
        tot = await page.text_content("#cartTotal")
        rec(f"[{h}] cart total = 2×1500 + 600", tot.replace(",","")=="3600", f"total={tot}")
        await page.click("#cartGo"); await page.wait_for_timeout(1200)
        cur = await page.get_attribute("#app","data-screen")
        rec(f"[{h}] cart CTA jumps to date screen", cur=="2", f"screen={cur}")

        # ---- 4. calendar loaded with availability
        days = await page.eval_on_selector_all("#week .day:not(.blank):not([disabled])","els=>els.length")
        rec(f"[{h}] month calendar has selectable days", days>0, f"days={days}")
        await page.screenshot(path=f"{OUT}/{h}-3-date.png")

        # ---- 5. pick a day -> calendar collapses, times show
        await page.eval_on_selector("#week .day:not(.blank):not([disabled])","e=>e.click()")
        await page.wait_for_timeout(1200)
        cal_hidden = await page.evaluate("()=>{const c=document.getElementById('cal');return c.hidden || getComputedStyle(c).display==='none';}")
        chip_shown = await page.evaluate("()=>{const c=document.getElementById('dateChip');return !c.hidden && getComputedStyle(c).display!=='none';}")
        tcount = await page.eval_on_selector_all("#times button","els=>els.length")
        rec(f"[{h}] picking a day collapses calendar", cal_hidden and chip_shown, f"calHidden={cal_hidden} chip={chip_shown}")
        rec(f"[{h}] slots loaded after day pick", tcount>0, f"slots={tcount}")
        tlabels = await page.eval_on_selector_all("#times button","els=>els.slice(0,3).map(e=>e.textContent.replace(/\\s+/g,' ').trim())")
        latin = all(("AM" in t or "PM" in t) for t in tlabels) if tlabels else False
        rec(f"[{h}] times are Latin AM/PM", latin, str(tlabels))
        await page.screenshot(path=f"{OUT}/{h}-4-times.png")

        # ---- 6. pick a time -> CTA enabled
        await page.eval_on_selector("#times button:not([disabled])","e=>e.click()")
        await page.wait_for_timeout(500)
        dis = await page.get_attribute("#toConfirm","disabled")
        rec(f"[{h}] time pick enables CTA", dis is None, f"disabled={dis}")
        await page.click("#toConfirm"); await page.wait_for_timeout(1100)
        cur = await page.get_attribute("#app","data-screen")
        rec(f"[{h}] CTA jumps to review screen", cur=="3", f"screen={cur}")
        await page.screenshot(path=f"{OUT}/{h}-5-review.png")

        # ---- 7. review fits without scrolling
        fit = await page.evaluate("""()=>{const p=document.querySelector('#deck .screen:nth-child(4) .pad')||document.querySelector('#deck .screen:nth-child(4)');
          return {sh:p.scrollHeight, ch:p.clientHeight};}""")
        rec(f"[{h}] review screen fits (no inner scroll)", fit["sh"]<=fit["ch"]+2, json.dumps(fit))
        st = await page.evaluate("()=>({d:document.getElementById('sumDate').textContent,t:document.getElementById('sumTime').textContent,dur:document.getElementById('sumDur').textContent,tot:document.getElementById('sumTotal').textContent})")
        print("   review:", st)

        # ---- 8. sheet gates gestures, form validation, submit
        await page.click("#confirmBtn"); await page.wait_for_timeout(700)
        open_ = await page.evaluate("()=>document.getElementById('app').classList.contains('sheet-open')||!document.getElementById('sheet').hidden")
        rec(f"[{h}] confirm opens the sheet", open_, "")
        before = await page.get_attribute("#app","data-screen")
        await swipe(-160)
        after = await page.get_attribute("#app","data-screen")
        rec(f"[{h}] sheet blocks deck gestures", before==after, f"{before}->{after}")
        gone = await page.evaluate("()=>!document.getElementById('peopleFields')")
        rec(f"[{h}] group-name box removed", gone, "")
        send_dis = await page.get_attribute("#toPay","disabled")
        rec(f"[{h}] next disabled before valid input", send_dis is not None, "")
        await page.fill("#nm","نورة العتيبي"); await page.fill("#ph","0501234567")
        await page.wait_for_timeout(250)
        still = await page.get_attribute("#toPay","disabled")
        rec(f"[{h}] district is required to continue", still is not None, "")
        await page.fill("#locTxt","حي النخيل، الرياض")
        await page.fill("#loc","https://example.com/x")
        await page.wait_for_timeout(400)
        badmap = await page.evaluate("()=>{const e=document.getElementById('locErr');return !e.hidden && getComputedStyle(e).display!=='none';}")
        rec(f"[{h}] non-Google-Maps URL rejected", badmap, "")
        await page.fill("#loc","https://maps.app.goo.gl/abc123")
        await page.wait_for_timeout(400)
        goodmap = await page.evaluate("()=>{const e=document.getElementById('locErr');return e.hidden || getComputedStyle(e).display==='none';}")
        rec(f"[{h}] Google-Maps URL accepted", goodmap, "")
        send_dis = await page.get_attribute("#toPay","disabled")
        rec(f"[{h}] next enabled once valid", send_dis is None, "")
        await page.screenshot(path=f"{OUT}/{h}-6-sheet.png")

        # ---- 8b. deposit pane
        await page.click("#toPay"); await page.wait_for_timeout(700)
        pay_on = await page.evaluate("()=>!!document.querySelector('.pane[data-pane=\"pay\"].on')")
        rec(f"[{h}] confirming details opens the deposit pane", pay_on, "")
        drift = await page.evaluate("""()=>{const a=document.getElementById('app');
          return {scroll:a.scrollTop, sheetTop:Math.round(document.getElementById('sheet').getBoundingClientRect().top)};}""")
        rec(f"[{h}] focusing form fields does not shove the app off-screen",
            drift["scroll"]==0 and drift["sheetTop"]==0, str(drift))
        amt = (await page.inner_text("#payAmt")).strip()
        rec(f"[{h}] deposit = fixed 375x2 + 150", amt.replace(",","").startswith("900"), f"amount={amt!r}")
        iban = (await page.inner_text("#bkIban")).strip()
        rec(f"[{h}] IBAN shown grouped in fours", iban.startswith("SA03 8000"), f"iban={iban!r}")
        send_dis = await page.get_attribute("#sendBooking","disabled")
        rec(f"[{h}] send blocked with no receipt attached", send_dis is not None, "")
        fit = await page.evaluate("()=>{const b=document.getElementById('sheetBody');return b.scrollHeight-b.clientHeight;}")
        rec(f"[{h}] deposit pane fits with no scroll", fit<=0, f"over={fit}")
        await page.screenshot(path=f"{OUT}/{h}-6b-deposit.png")

        await page.set_input_files("#rcptFile", f"{_H.SAMPLE}")
        await page.wait_for_timeout(700)
        prev = await page.evaluate("()=>{const e=document.getElementById('rcptPrev');return !e.hidden;}")
        send_dis = await page.get_attribute("#sendBooking","disabled")
        rec(f"[{h}] attaching a receipt previews it and enables send", prev and send_dis is None, f"prev={prev}")
        await page.screenshot(path=f"{OUT}/{h}-6c-attached.png")
        await page.click("#sendBooking"); await page.wait_for_timeout(2600)
        uploaded = await page.evaluate("()=>[...(window.__UPLOADED__||[])]")
        rec(f"[{h}] receipt uploaded before the booking", len(uploaded)==1 and uploaded[0].startswith("pending/"),
            f"paths={uploaded}")
        ref = await page.text_content("#refNo")
        booked = await page.evaluate("()=>{const b=document.getElementById('booked');return !b.hidden && getComputedStyle(b).display!=='none';}")
        rec(f"[{h}] submit -> createBooking -> ref shown", booked and ref.strip() not in ("","—"), f"ref={ref!r} shown={booked}")
        cur = await page.get_attribute("#app","data-screen")
        rec(f"[{h}] success lands on contact screen", cur=="4", f"screen={cur}")
        link = await page.input_value("#trackLink")
        rec(f"[{h}] tracking link built from public_token", bool(link and "t=" in link), f"link={link}")
        await page.screenshot(path=f"{OUT}/{h}-7-booked.png")

        # ---- 9. bottom gutter on contact
        gut = await page.evaluate("""()=>{const s=document.querySelector('#deck .screen:nth-child(5)');
          const pad=s.querySelector('.pad'); pad.scrollTop=0;
          const kids=[...pad.querySelectorAll('*')].filter(e=>e.offsetParent!==null
            && e.getBoundingClientRect().height>0
            && getComputedStyle(e).position!=='absolute' && !e.classList.contains('dust'));
          const bottom=Math.max(...kids.map(e=>e.getBoundingClientRect().bottom));
          return {gut:Math.round(s.getBoundingClientRect().bottom-bottom),
                  over:pad.scrollHeight-pad.clientHeight};}""")
        rec(f"[{h}] contact fits, bottom gutter >= 24px", gut["over"]<=0 and gut["gut"]>=24, f"over={gut['over']} gutter={gut['gut']}px")

        rec(f"[{h}] no console/page errors", len(errs)==0, "; ".join(errs[:6]))

        # ---- 10. tracking view
        p2 = await ctx.new_page(); e2=[]
        p2.on("pageerror", lambda e: e2.append(str(e)))
        p2.on("console", lambda m: e2.append(m.text) if m.type=="error" else None)
        await p2.goto(BASE+"index.html?t=tok-3"); await p2.wait_for_timeout(1800)
        vis = await p2.evaluate("()=>{const t=document.getElementById('trackScreen');return getComputedStyle(t).display!=='none'&&!t.hidden;}")
        txt = await p2.inner_text("#trackView")
        rec(f"[{h}] ?t= renders tracking screen", vis and "EA-20260802" in txt, f"vis={vis} hasRef={'EA-20260802' in txt}")
        rec(f"[{h}] tracking has no errors", len(e2)==0, "; ".join(e2[:4]))
        await p2.screenshot(path=f"{OUT}/{h}-8-track.png")
        await b.close()

asyncio.run(main(int(sys.argv[1]) if len(sys.argv)>1 else 700))
bad=[r for r in RESULTS if not r[1]]
print("\n=== %d/%d passed ===" % (len(RESULTS)-len(bad), len(RESULTS)))
sys.exit(1 if bad else 0)
