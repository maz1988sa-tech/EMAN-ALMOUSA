# -*- coding: utf-8 -*-
"""وقت وصول الطلب: سطرٌ في البطاقة، وصفوفٌ في التفاصيل، وترتيبٌ بأحدث وصول.

كانت البطاقة تقول متى الموعد ولا تقول متى وصل الطلب. والوقت محفوظٌ مع كلّ
حجز (`created_at`)، فالفحص يقيس العرض وحده: النصّ كما يُقرأ، والجديدُ
المنتظَر ردُّه بلون الهوية، والسطرُ لا يلتفّ على جوالٍ ضيّق، والترتيب يتبع
وقت الوصول لا الموعد، والتأكيدُ يُذكر حين يأتي بعد الوصول وحده.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, http.server, socketserver, threading, functools, datetime as dt
from playwright.async_api import async_playwright

ROOT = str(_H.ROOT)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start()
MOCK = open(os.path.join(ROOT, "dev/mock-supabase.js"), encoding="utf-8").read()
R = []
def rec(n, ok, note=""):
    R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

def lead_text(hours):
    """القاعدة نفسها التي في اللوحة: بالقطع لا بالتقريب، والساعات مع اليوم واليومين."""
    def word(n, one, two, few, many):
        return one if n == 1 else two if n == 2 else f"{n} {few if n <= 10 else many}"
    def by(n, *w):
        return ('ب' + word(n, *w)) if n <= 2 else f"بـ {word(n, *w)}"
    mins = int(hours * 60); days, hrs = mins // 1440, (mins % 1440) // 60
    D = ('يوم', 'يومين', 'أيام', 'يومًا'); H = ('ساعة', 'ساعتين', 'ساعات', 'ساعة')
    if days >= 3: return by(days, *D)
    if days >= 1: return by(days, *D) + (f" و{word(hrs, *H)}" if hrs else '')
    if mins >= 60: return by(mins // 60, *H)
    return by(mins, 'دقيقة', 'دقيقتين', 'دقائق', 'دقيقة')

async def tab(pg, name):
    await pg.evaluate(f"()=>{{const t=[...document.querySelectorAll('[data-tab]')].find(e=>e.textContent.includes('{name}')); if(t) t.click();}}")
    await pg.wait_for_timeout(1000)

async def cards(pg):
    return await pg.evaluate("""()=>[...document.querySelectorAll('.bk[data-card]')].filter(c=>c.offsetParent).map(c=>{
        const a=c.querySelector('.arrived'); return {id:c.dataset.card, txt:a?a.textContent.trim():null,
        fresh:!!(a&&a.classList.contains('fresh')), color:a?getComputedStyle(a).color:null,
        meta:getComputedStyle(c.querySelector('.meta')).color};})""")

async def sheet_rows(pg):
    return await pg.evaluate("""()=>Object.fromEntries([...document.querySelectorAll('.leader')].filter(r=>r.offsetParent)
        .map(r=>[(r.querySelector('.k')||{}).textContent?.trim()||'', (r.querySelector('.v')||{}).textContent?.trim()||'']))""")

async def open_card(pg, bid):
    await pg.evaluate(f"()=>{{const c=[...document.querySelectorAll('.bk[data-card=\"{bid}\"] .bk-main')].filter(e=>e.offsetParent).pop(); if(c) c.click();}}")
    await pg.wait_for_timeout(900)

async def close_sheet(pg):
    await pg.keyboard.press('Escape'); await pg.wait_for_timeout(500)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**_H.CHROME, args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 360, "height": 800}, device_scale_factor=2,
                                  timezone_id='Asia/Riyadh')
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
        await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(1700)

        # ── الرئيسية: الطلب المنتظَر وصل قبل دقائق، فهو بلون الهوية ──────
        home = {c['id']: c for c in await cards(pg)}
        b3 = home.get('b3') or {}
        rec("الطلب المنتظَر في الرئيسية يقول متى وصل",
            (b3.get('txt') or '').startswith('وصل الطلب قبل') and 'دقيقة' in (b3.get('txt') or ''), str(b3.get('txt')))
        rec("وهو بلون الهوية لأنه جديد وبانتظار الردّ", b3.get('fresh') and b3.get('color') != b3.get('meta'),
            f"{b3.get('color')} مقابل {b3.get('meta')}")

        # ── الحجوزات، «الكل»: كلّ بطاقة تحمل سطرها، واليدويّ بعبارته ──────
        await tab(pg, 'الحجوزات')
        await pg.evaluate("()=>document.querySelector('[data-st=\"all\"]').click()"); await pg.wait_for_timeout(500)
        cs = await cards(pg)
        by = {c['id']: c for c in cs}
        rec("كلّ بطاقة فيها سطر الوصول", cs and all(c['txt'] for c in cs), f"{sum(1 for c in cs if c['txt'])}/{len(cs)}")
        rec("اليدويّ «أُضيف يدويًا» وما جاء من الرابط «وصل الطلب»",
            all(by[i]['txt'].startswith('أُضيف يدويًا') for i in ('b2', 'b5') if i in by)
            and all(by[i]['txt'].startswith('وصل الطلب') for i in ('b1', 'b3', 'b4') if i in by),
            " | ".join(f"{k}:{v['txt']}" for k, v in by.items()))
        rec("الجديد وحده بلون الهوية", [c['id'] for c in cs if c['fresh']] == ['b3'], str([c['id'] for c in cs if c['fresh']]))
        old = by.get('b5', {}).get('txt') or ''
        rec("ما مضى عليه أسبوعٌ يُكتب بتاريخه وساعته", '·' in old and any(m in old for m in
            ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']), old)

        # السطر لا يلتفّ على جوالٍ عرضه ٣٦٠، ولا يخرج من بطاقته
        geo = await pg.evaluate("""()=>[...document.querySelectorAll('.bk[data-card]')].filter(c=>c.offsetParent).map(c=>{
            const a=c.querySelector('.arrived span'), r=a.getBoundingClientRect(), k=c.getBoundingClientRect();
            const lh=parseFloat(getComputedStyle(a).lineHeight)||16;
            return {id:c.dataset.card, lines:Math.round(r.height/lh), inside:r.left>=k.left-0.5 && r.right<=k.right+0.5};})""")
        rec("السطر سطرٌ واحد على ٣٦٠", all(g['lines'] == 1 for g in geo), str(geo))
        rec("ولا يخرج من البطاقة", all(g['inside'] for g in geo), str([g['id'] for g in geo if not g['inside']]))

        # ── الترتيب: الافتراضيّ بالموعد، و«الأحدث وصولًا» بوقت الوصول ──────
        sort_chips = await pg.evaluate("()=>[...document.querySelectorAll('[data-so]')].map(b=>[b.dataset.so,b.textContent.trim(),b.getAttribute('aria-pressed')])")
        rec("شريحتا الترتيب والافتراضيّ «حسب الموعد»",
            [s[0] for s in sort_chips] == ['date', 'arrived'] and sort_chips[0][2] == 'true', str(sort_chips))
        by_date = [c['id'] for c in cs]
        await pg.evaluate("()=>document.querySelector('[data-so=\"arrived\"]').click()"); await pg.wait_for_timeout(500)
        by_arr = [c['id'] for c in await cards(pg)]
        rec("«الأحدث وصولًا» يرتّب بوقت الوصول", by_arr == ['b3', 'b4', 'b1', 'b2', 'b5'], f"{by_arr} (بالموعد: {by_date})")
        pressed = await pg.evaluate("()=>document.querySelector('[data-so=\"arrived\"]').getAttribute('aria-pressed')")
        rec("والشريحة المختارة تُعلَّم", pressed == 'true')
        await pg.evaluate("()=>document.querySelector('[data-so=\"date\"]').click()"); await pg.wait_for_timeout(400)
        back = [c['id'] for c in await cards(pg)]
        rec("والعودة إلى «حسب الموعد» تعيد الترتيب الأوّل", back == by_date, str(back))

        # ── التفاصيل: الوصول كاملًا، وقبل الموعد بكم، والتأكيد حين يلي الوصول ──
        await open_card(pg, 'b3')
        rows = await sheet_rows(pg)
        now = dt.datetime.now(dt.timezone(dt.timedelta(hours=3)))
        appt = (now + dt.timedelta(days=2)).replace(hour=17, minute=0, second=0, microsecond=0)
        # المحاكي يحسب «قبل ٢٥ دقيقة» لحظةَ تحميل الصفحة، والفحص يحسب بعدها بثوانٍ:
        # فيُقبل الحساب عند اللحظتين كي لا يسقط على حدّ ساعةٍ بالصدفة.
        made = [now - dt.timedelta(minutes=25, seconds=s) for s in (0, 30)]
        want = {lead_text((appt - m).total_seconds() / 3600) for m in made}
        rec("«وصل الطلب» بالتاريخ والسنة والساعة", str(now.year) in rows.get('وصل الطلب', '') and '·' in rows.get('وصل الطلب', ''),
            rows.get('وصل الطلب'))
        rec("«قبل الموعد» كما تحسبه القاعدة", rows.get('قبل الموعد') in want, f"{rows.get('قبل الموعد')} ← المتوقَّع {want}")
        rec("ولا «تأكّد» لطلبٍ لم يُؤكَّد", 'تأكّد' not in rows)
        await close_sheet(pg)
        await open_card(pg, 'b1')
        r1 = await sheet_rows(pg)
        rec("المؤكَّد بعد وصوله يذكر متى تأكّد", bool(r1.get('تأكّد')) and '·' in r1.get('تأكّد', ''), str(r1.get('تأكّد')))
        await close_sheet(pg)
        await open_card(pg, 'b2')
        r2 = await sheet_rows(pg)
        rec("اليدويّ «أُضيف» بلا «تأكّد» مكرَّر", bool(r2.get('أُضيف')) and 'تأكّد' not in r2 and 'وصل الطلب' not in r2,
            str({k: v for k, v in r2.items() if k in ('أُضيف', 'تأكّد', 'وصل الطلب')}))
        await close_sheet(pg)

        # ── الأجندة: البطاقة نفسها فتحمل السطر نفسه ─────────────────────
        await tab(pg, 'الأجندة')
        ag = await cards(pg)
        rec("بطاقات الأجندة تحمل سطر الوصول أيضًا", ag and all(c['txt'] for c in ag), str([c['txt'] for c in ag][:2]))

        rec("بلا أخطاء في الصفحة", not errs, str(errs[:2]))
        await pg.screenshot(path=f"{_H.SHOTS}/arrived.png", full_page=False)
        await b.close()

    ok = sum(1 for _, s in R if s)
    print(f"\n=== {ok}/{len(R)} passed ===")
    sys.exit(0 if ok == len(R) else 1)

asyncio.run(main())
