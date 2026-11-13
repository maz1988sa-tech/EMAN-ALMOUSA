# -*- coding: utf-8 -*-
"""الفترة المخصّصة لخدمة (§٧ع): ما تفعله إيمان في اللوحة، وما تراه العميلة في التقويم، وما يصل القاعدة.

الميزة تُقاس بثلاثة أشياء لا بوجود الأزرار:
  ١) اللوحة: الطرق الثلاث (شهر · من—إلى · أيام بعينها) تحفظ أيامًا بعينها؛ الأخطاء تُقال قبل الحفظ؛
     الأيام المأخوذة تُعلَّم ولا تُضغط؛ التعديل والإيقاف والحذف بخطوتين تكتب ما يُنتظر منها.
  ٢) صفحة العميلة: يومٌ كان سيُفتح لولا الفترة يُرسم «مخصّصًا» (مخطّطًا) لا «مقفلًا»، ومعه رسالة إيمان؛
     والمقفل في الأساس يبقى مقفلًا؛ ومن في سلّتها الخدمة المخصّصة ترى الأيام مفتوحةً بلا شيء.
  ٣) العقد مع القاعدة: كلّ نداءٍ يحمل خدمات السلّة (`p_service_ids`) وحجزٌ يحمل مصافحة الميزات (`p_features`).

المحاكي (dev/mock-supabase.js) نسخةٌ حرفيّة من حكم القاعدة؛ وحكم القاعدة نفسه يُفحص في
supabase/tests/reserved_periods.sql. ما يُقارَن هنا يُقارَن بخطّ أساسٍ من الصفحة نفسها بلا فترات
(لا بأرقامٍ تُنسخ من المحاكي)، فلا يتعطّل الفحص كلّما تغيّر التاريخ.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, json, re, calendar, datetime, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright

ROOT = str(_H.ROOT)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
MOCK = open(os.path.join(ROOT, "dev/mock-supabase.js"), encoding="utf-8").read()
# s3 بمدّة s2 نفسها (٤٥ دقيقة): ليُقاس أنّ بصمة السلّة تحمل المعرّفات لا المدّة وحدها.
MOCK_SAME = MOCK.replace("'mirror', 400, 40,", "'mirror', 400, 45,")

AR = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
T = datetime.date.today()
def shift(y, m, k):
    t = y * 12 + (m - 1) + k
    return t // 12, t % 12 + 1
Y0, M0 = T.year, T.month
Y1, M1 = shift(Y0, M0, 1)
Y2, M2 = shift(Y0, M0, 2)
def iso(y, m, d): return f"{y:04d}-{m:02d}-{d:02d}"
def dim(y, m): return calendar.monthrange(y, m)[1]
M1_DAYS = lambda a, b: [iso(Y1, M1, d) for d in range(a, b + 1)]

R = []
def rec(n, ok, note=""):
    R.append((n, bool(ok))); print(("PASS " if ok else "FAIL ") + n + ((" — " + str(note)) if note else ""))

async def mk(b, mock, init, w=390, h=900):
    ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, has_touch=True, is_mobile=True)
    await ctx.route("**/assets/vendor/supabase.js",
                    lambda r: asyncio.ensure_future(r.fulfill(content_type="application/javascript", body=mock)))
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    await pg.add_init_script(init)
    return ctx, pg, errs

async def click(pg, sel, wait=200):
    ok = await pg.evaluate("(s)=>{const e=document.querySelector(s); if(!e) return false; e.click(); return true;}", sel)
    await pg.wait_for_timeout(wait)
    return ok

# ════════════════════════ اللوحة ════════════════════════
SHEET = """()=>{
  const r=document.getElementById('rsv-root'); if(!r) return null;
  const q=(s)=>[...r.querySelectorAll(s)];
  const g=(s)=>r.querySelector(s);
  return {
    title:(document.getElementById('sheetTitle')||{}).textContent,
    type:[...document.querySelectorAll('#sheetContent .viewseg.wide button[id^=o-]')].map(b=>b.id+':'+b.getAttribute('aria-pressed')),
    chips:q('[data-rsv=svc]').map(b=>b.dataset.v+':'+b.getAttribute('aria-pressed')),
    modes:q('[data-rsv=mode]').map(b=>b.dataset.v+':'+b.getAttribute('aria-pressed')),
    lbl:(g('.mcal-nav .lbl')||{}).textContent||'',
    hint:(g('#rsv-hint')||{}).textContent||'',
    msg:(g('#rsv-msg')||{}).value,
    prev:(g('#rsv-prev')||{}).textContent||'',
    on:(g('#rsv-on')||{}).checked,
    note:(g('#rsv-note .note')||{}).className||'',
    noteTxt:(g('#rsv-note')||{}).textContent||'',
    err:(g('#rsv-err')||{}).textContent||'',
    cal:{on:q('.mcal-grid .d.on').length, mid:q('.mcal-grid .d.mid').length, taken:q('.mcal-grid .d.taken').length,
         past:q('.mcal-grid .d.past').length, btn:q('.mcal-grid button.d').length},
  };}"""
LIST = """()=>[...document.querySelectorAll('#view .card .rowline')].map(e=>({
    t:((e.querySelector('.t')||{}).textContent||'').trim(), s:((e.querySelector('.s')||{}).textContent||'').trim(),
    pill:!!e.querySelector('.pill.quiet'), edit:e.querySelector('[data-rsv-edit]')?.dataset.rsvEdit||null,
    del:e.querySelector('[data-rsv-del]')?.dataset.rsvDel||null}))"""
WRITES = "()=>JSON.parse(JSON.stringify(window.__RESERVED_WRITES||[]))"

async def sheet(pg): return await pg.evaluate(SHEET)
async def rows(pg): return [r for r in await pg.evaluate(LIST) if 'لخدمة' in r['s'] or 'للخدمات' in r['s'] or r['t'] == 'حذف هذه الفترة؟']
async def open_new(pg):
    """الإضافة تفتح ورقة الاستثناء القديمة بمفتاح النوع؛ والثالث «مخصّصة لخدمة» يفتح ورقة الفترة."""
    await click(pg, '#addOverride', 450)
    await click(pg, '#o-rsv', 450)
async def close_sheet(pg): await click(pg, '#sheetClose', 450)
# المحتوى يبقى في الـDOM بعد الإغلاق (الورقة تُخفى فقط)؛ فالمفتوحة هي ذات الصنف open لا وجودُ جذرها.
async def sheet_open(pg): return await pg.evaluate("()=>document.getElementById('sheet').classList.contains('open')")
def day(iso_): return f"#rsv-root [data-rsv=day][data-v='{iso_}']"
async def nav(pg, k=1):
    for _ in range(k): await click(pg, "#rsv-root [data-rsv=nav][data-v='1']", 220)
async def save(pg, wait=700): return await click(pg, "#rsv-root [data-rsv=save]", wait)

HTMLISH = 'ديسمبر <b>للعرائس</b> & "فقط" <img src=x onerror="window.__xss=1">'

RES_A = [
    {"id": "rp1", "mode": "range", "dates": M1_DAYS(10, 16), "service_ids": ["s1"], "message": "هذه الفترة للعرائس", "active": True},
    {"id": "rp2", "mode": "days", "dates": [iso(Y1, M1, d) for d in (20, 22, 24)], "service_ids": ["s2", "s3"],
     "message": "للسهرة والتسريحة فقط", "active": False},
]

async def admin_part(b):
    ctx, pg, errs = await mk(b, MOCK, f"window.__MOCK_SIGNED_IN__ = true; window.__RESERVED__ = {json.dumps(RES_A)};", 430, 932)
    await pg.goto(f"http://127.0.0.1:{PORT}/admin.html")
    await pg.wait_for_timeout(1800)

    # ── الملخّص في قائمة الإعدادات: إجازتان قادمتان + فترة مفعّلة واحدة؛ الموقوفة لا تُعدّ
    await pg.evaluate("()=>document.querySelector('[data-tab=settings]').click()")
    await pg.wait_for_timeout(1100)
    await pg.evaluate("()=>{const b=document.getElementById('setBack'); if(b) b.click();}")
    await pg.wait_for_timeout(300)
    sm = await pg.evaluate("()=>{const r=document.querySelector('.setrow[data-setpage=exceptions]'); return r?r.textContent.replace(/\\s+/g,' ').trim():null;}")
    rec("ملخّص «الإجازات والاستثناءات» يعدّ الفترة المفعّلة مع الإجازات", sm and "3 فترات قادمة" in sm, sm)
    rec("والفترة الموقوفة لا تدخل العدّ", sm and "4 فترات" not in sm)

    # ── قائمة الاستثناءات: الإجازات والفترات معًا
    await _H.open_settings(pg, "exceptions", 900)
    rs = await rows(pg)
    rec("القائمة تعرض الفترتين المحفوظتين", len(rs) == 2, [r['t'] for r in rs])
    r1 = next((r for r in rs if r['edit'] == 'rp1'), {})
    rec("عنوان فترة النطاق بطرفيها", f"10 {AR[M1-1]}" in r1.get('t', '') and f"16 {AR[M1-1]}" in r1.get('t', ''), r1.get('t'))
    rec("وتحتها الخدمة وعدد الأيام", r1.get('s', '').startswith("لخدمة ميك اب عروس") and "7 أيام" in r1.get('s', ''), r1.get('s'))
    r2 = next((r for r in rs if r['edit'] == 'rp2'), {})
    rec("خدمتان: «للخدمات: …» وبلا قوسٍ في اسم الخدمة", r2.get('s', '').startswith("للخدمات: ميك اب سهرة، تسريحة شعر") and "3 أيام" in r2.get('s', ''), r2.get('s'))
    rec("والموقوفة تحمل شارة «موقوفة» والمفعّلة لا", r2.get('pill') and not r1.get('pill'))
    rec("الإجازات القديمة ما زالت في القائمة", await pg.evaluate("()=>document.querySelectorAll('#view .card [data-delov]').length") == 2)
    await pg.screenshot(path=f"{_H.SHOTS}/43-reserved-list.png", full_page=True)

    # ── الورقة: الإضافة تمرّ بمفتاح النوع
    await click(pg, '#addOverride', 450)
    seg = await pg.evaluate("()=>[...document.querySelectorAll('#sheetContent .viewseg.wide button')].map(b=>b.textContent.trim()+':'+b.getAttribute('aria-pressed'))")
    rec("ورقة الاستثناء بمفتاح ثلاثي: إجازة · ساعات خاصة · مخصّصة لخدمة", seg == ["إجازة:true", "ساعات خاصة:false", "مخصّصة لخدمة:false"], seg)
    await click(pg, '#o-rsv', 450)
    s = await sheet(pg)
    rec("«مخصّصة لخدمة» تفتح ورقة الفترة والمفتاح عليها", s and s['type'] == ['o-closed:false', 'o-custom:false', 'o-rsv:true'], s and s['type'])
    rec("الخدمة الأولى مختارةٌ مسبقًا والبقيّة لا", s['chips'] == ['s1:true', 's2:false', 's3:false'], s['chips'])
    rec("والطريقة الافتراضيّة «شهر كامل»", s['modes'] == ['month:true', 'range:false', 'days:false'], s['modes'])
    left = dim(Y0, M0) - T.day + 1
    rec("تلميح الشهر: اسمه وعدد أيامه من اليوم", AR[M0 - 1] in s['hint'] and "كاملًا" in s['hint'] and f"{left} " in s['hint'].replace('يومًا', ' ').replace('أيام', ' '), s['hint'])
    rec("الرسالة جاهزةٌ ومعها معاينة ما تقرؤه العميلة", s['msg'] == "هذا الشهر مخصّص لخدمة ميك اب عروس" and s['prev'] == f"تقرأ العميلة: «{s['msg']}»", s['msg'])
    # «شهر كامل» معاينةٌ لا اختيار: الأيام فيه بلا أزرار، والماضي منها مطفأ، والباقي كلُّه مظلَّل.
    rec("«شهر كامل»: معاينةٌ بلا أزرار، الماضي مطفأ والباقي مظلَّل", s['cal']['btn'] == 0 and s['cal']['past'] == T.day - 1 and s['cal']['mid'] == dim(Y0, M0) - T.day + 1, s['cal'])
    await pg.screenshot(path=f"{_H.SHOTS}/44-reserved-sheet.png")

    # ── الخدمات: الرسالة الجاهزة تتبعها ما لم تُمسّ
    await click(pg, "#rsv-root [data-rsv=svc][data-v=s2]")
    s = await sheet(pg)
    rec("إضافة خدمة تغيّر الصيغة الجاهزة إلى «للخدمات: …»", s['msg'] == "هذا الشهر مخصّص للخدمات: ميك اب عروس، ميك اب سهرة", s['msg'])
    await click(pg, "#rsv-root [data-rsv=svc][data-v=s1]")
    s = await sheet(pg)
    rec("وإزالة الأولى تبقي الثانية وحدها", s['chips'] == ['s1:false', 's2:true', 's3:false'] and s['msg'] == "هذا الشهر مخصّص لخدمة ميك اب سهرة", s['msg'])
    await pg.evaluate("""()=>{const i=document.getElementById('rsv-msg'); i.value='  ديسمبر لعروسنا فقط  '; i.dispatchEvent(new Event('input',{bubbles:true}));}""")
    await pg.wait_for_timeout(150)
    s = await sheet(pg)
    rec("المعاينة تتبع ما تكتبه إيمان فورًا", s['prev'] == "تقرأ العميلة: «ديسمبر لعروسنا فقط»", s['prev'])
    await click(pg, "#rsv-root [data-rsv=svc][data-v=s3]")
    s = await sheet(pg)
    rec("وإذا كتبت نصّها ثبت: تغيير الخدمة لا يمسحه", s['msg'].strip() == "ديسمبر لعروسنا فقط" and s['chips'] == ['s1:false', 's2:true', 's3:true'], s['msg'])

    # ── التحقّق قبل الحفظ: لا كتابةَ إن لم يصحّ الاختيار
    w0 = len(await pg.evaluate(WRITES))
    await click(pg, "#rsv-root [data-rsv=svc][data-v=s2]"); await click(pg, "#rsv-root [data-rsv=svc][data-v=s3]")
    await save(pg, 300)
    s = await sheet(pg)
    rec("بلا خدمة: «اختاري خدمة واحدة على الأقل.»", s['err'] == "اختاري خدمة واحدة على الأقل.", s['err'])
    await click(pg, "#rsv-root [data-rsv=svc][data-v=s1]")
    # شهرٌ فيه فترتان محفوظتان: كلّه شهرٌ كامل ← تعارض مع أيامهما العشرة
    await nav(pg, 1)
    s = await sheet(pg)
    rec("التنقّل إلى الشهر التالي يُبدّل الشهر المختار (شهر كامل)", f"{AR[M1-1]} {Y1} كاملًا" in s['hint'] and f"{dim(Y1, M1)} " in s['hint'].replace('يومًا', ' '), s['hint'])
    rec("أيام الفترات المحفوظة (الموقوفة أيضًا) معلَّمة «مأخوذة»: عشرةٌ في هذا الشهر", s['cal']['taken'] == 10, s['cal'])
    await save(pg, 300)
    s = await sheet(pg)
    rec("شهرٌ كاملٌ يقطع فترتين: يُرفض بذكر عدد الأيام المتداخلة",
        "10 أيام من اختيارك داخل فترة مخصّصة أخرى" in s['err'], s['err'])
    rec("ولا شيء كُتب في القاعدة", len(await pg.evaluate(WRITES)) == w0)
    await pg.screenshot(path=f"{_H.SHOTS}/45-reserved-overlap.png")
    # المأخوذ لا يُضغط: في «أيام بعينها» يُرسم الشهر نفسه أزرارًا إلّا العشرة المأخوذة فأقسامٌ بلا نقر.
    await click(pg, "#rsv-root [data-rsv=mode][data-v=days]")
    s = await sheet(pg)
    rec("المأخوذ لا يُضغط: الأزرار الأيامُ الحرّة وحدها", s['cal']['taken'] == 10 and s['cal']['btn'] == dim(Y1, M1) - 10, s['cal'])

    # ── النطاق: بداية ثمّ نهاية، والعكس يُرتَّب، والبداية الجديدة تبدأ نطاقًا جديدًا
    await nav(pg, 1)                              # الشهر الذي بعده: خالٍ من الفترات
    await click(pg, "#rsv-root [data-rsv=mode][data-v=range]")
    s = await sheet(pg)
    rec("«من — إلى»: تلميحٌ يطلب البداية", s['hint'] == "اضغطي يوم البداية ثم يوم النهاية.", s['hint'])
    rec("والشهر المعروض لم يتغيّر بتغيير الطريقة", f"{AR[M2-1]} {Y2}" == s['lbl'], s['lbl'])
    await click(pg, day(iso(Y2, M2, 3)))
    s = await sheet(pg)
    rec("بعد البداية: التلميح يطلب النهاية", s['hint'].startswith("البداية") and "اضغطي يوم النهاية" in s['hint'], s['hint'])
    await click(pg, day(iso(Y2, M2, 9)))
    s = await sheet(pg)
    rec("بعد النهاية: سبعة أيام، طرفان وخمسة بينهما", "7 أيام" in s['hint'] and s['cal']['on'] == 2 and s['cal']['mid'] == 5, (s['hint'], s['cal']))
    await click(pg, day(iso(Y2, M2, 20))); await click(pg, day(iso(Y2, M2, 14)))
    s = await sheet(pg)
    rec("الضغط الثالث يبدأ نطاقًا جديدًا، والنهاية الأسبق تُقلب مع البداية", "7 أيام" in s['hint'] and s['cal']['on'] == 2 and s['cal']['mid'] == 5, (s['hint'], s['cal']))
    await click(pg, day(iso(Y2, M2, 25)))
    await save(pg, 300)
    s = await sheet(pg)
    rec("نطاقٌ بلا نهاية: «اختاري يوم البداية ويوم النهاية.»", s['err'] == "اختاري يوم البداية ويوم النهاية.", s['err'])
    await click(pg, day(iso(Y2, M2, 28)))
    await save(pg)
    wr = await pg.evaluate(WRITES)
    ins = [w for w in wr if w['op'] == 'insert']
    row = ins[-1]['row'] if ins else {}
    rec("الحفظ يكتب فترةً واحدة بالأيام الأربعة من النطاق", len(ins) == 1 and row.get('dates') == [iso(Y2, M2, d) for d in range(25, 29)], row.get('dates'))
    # الرسالة هنا ما كتبته إيمان في الورقة نفسها قبل قليل (مقصوصةَ الفراغ)، فتبقى ولا تتبع الجاهزة.
    rec("بالطريقة والخدمة والتفعيل، والرسالة المكتوبة مقصوصةً لا الجاهزة",
        row.get('mode') == 'range' and row.get('service_ids') == ['s1'] and row.get('message') == "ديسمبر لعروسنا فقط" and row.get('active') is True, row)
    rec("وتُغلق الورقة وتظهر الفترة الجديدة في القائمة", not await sheet_open(pg) and len(await rows(pg)) == 3)
    rec("ويظهر تأكيد الحفظ", await pg.evaluate("()=>[...document.querySelectorAll('.toast')].some(t=>/حُفظت الفترة/.test(t.textContent))"))

    # ── أيام بعينها عبر شهرين، مع خدمتين
    await open_new(pg)
    await click(pg, "#rsv-root [data-rsv=mode][data-v=days]")
    s = await sheet(pg)
    rec("«أيام بعينها»: الرسالة الجاهزة بصيغة الفترة لا الشهر", s['msg'] == "هذه الفترة مخصّصة لخدمة ميك اب عروس", s['msg'])
    rec("والتلميح يدعو إلى الضغط على الأيام", s['hint'].startswith("اضغطي على الأيام"), s['hint'])
    rec("والماضي في الشهر الحالي لا يُضغط: أزرارٌ للأيام الباقية وحدها",
        s['cal']['past'] == T.day - 1 and s['cal']['btn'] == dim(Y0, M0) - T.day + 1, s['cal'])
    await click(pg, "#rsv-root [data-rsv=svc][data-v=s2]"); await click(pg, "#rsv-root [data-rsv=svc][data-v=s1]")
    await click(pg, "#rsv-root [data-rsv=svc][data-v=s3]")
    await nav(pg, 1)
    await click(pg, day(iso(Y1, M1, 1)))
    await click(pg, day(iso(Y1, M1, 3))); await click(pg, day(iso(Y1, M1, 3)))     # ضغطةٌ ثانية على اليوم نفسه تلغيه
    await nav(pg, 1)
    await click(pg, day(iso(Y2, M2, 5)))
    s = await sheet(pg)
    rec("الاختيار يبقى عبر الشهور، والضغط الثاني يلغي اليوم",
        "يومان" in s['hint'] and f"1 {AR[M1-1]} و 5 {AR[M2-1]}" in s['hint'], s['hint'])
    rec("الأيام المختارة معلَّمة في التقويم", s['cal']['on'] == 1)
    await save(pg)
    wr = await pg.evaluate(WRITES)
    ins = [w for w in wr if w['op'] == 'insert']
    row = ins[-1]['row'] if len(ins) >= 2 else {}
    rec("الحفظ: يومان بعينهما مرتّبان وخدمتان بترتيب القائمة",
        row.get('mode') == 'days' and row.get('dates') == [iso(Y1, M1, 1), iso(Y2, M2, 5)] and row.get('service_ids') == ['s2', 's3'], row)
    rec("والرسالة الجاهزة تذكر الخدمتين", row.get('message') == "هذه الفترة مخصّصة للخدمات: ميك اب سهرة، تسريحة شعر", row.get('message'))
    rs = await rows(pg)
    # أوّل أيّام «أيام بعينها» غرّةُ الشهر التالي، أسبقُ من بداية rp1 (١٠)، فتتقدّمها.
    rec("القائمة مرتّبةٌ بتاريخ أوّل يومٍ في كلّ فترة", [r['edit'] for r in rs] == ['rp4', 'rp1', 'rp2', 'rp3'], [r['edit'] for r in rs])

    # ── سباقٌ بين جهازين: فترةٌ كُتبت من جهازٍ آخر بعد أن رسمتُ تقويمي — القاعدة تردّها والورقة تبقى مفتوحة
    await open_new(pg)
    await click(pg, "#rsv-root [data-rsv=mode][data-v=days]")
    await nav(pg, 1)
    await click(pg, day(iso(Y1, M1, 18)))
    await pg.evaluate("""async(d)=>{const c=window.supabase.createClient('u','k');
      await c.from('reserved_periods').insert({mode:'days',dates:[d],service_ids:['s3'],message:'من جهازٍ آخر'});}""", iso(Y1, M1, 18))
    w0 = len(await pg.evaluate(WRITES))
    await save(pg)
    s = await sheet(pg)
    rec("ردّ القاعدة للتداخل يظهر للمديرة كما هو والورقة تبقى مفتوحة", await sheet_open(pg) and s and "داخل فترةٍ مخصّصة أخرى" in s['err'], s and s['err'])
    rec("ولم تُكتب فترتها", len(await pg.evaluate(WRITES)) == w0)
    await close_sheet(pg)
    await pg.evaluate("()=>document.querySelector('[data-tab=settings]').click()"); await pg.wait_for_timeout(500)

    # ── التعديل: الورقة تفتح بما حُفظ، بلا مفتاح النوع
    await _H.open_settings(pg, "exceptions", 800)
    await click(pg, "[data-rsv-edit='rp1']", 500)
    s = await sheet(pg)
    rec("التعديل: عنوان «تعديل الفترة» وبلا مفتاح النوع", s['title'] == 'تعديل الفترة' and s['type'] == [], (s['title'], s['type']))
    rec("وتفتح بطريقتها المحفوظة وخدمتها ورسالتها", s['modes'] == ['month:false', 'range:true', 'days:false'] and s['chips'] == ['s1:true', 's2:false', 's3:false'] and s['msg'] == "هذه الفترة للعرائس", (s['modes'], s['chips'], s['msg']))
    rec("والتقويم على شهرها: طرفان وخمسة أيام بينهما", s['lbl'] == f"{AR[M1-1]} {Y1}" and s['cal']['on'] == 2 and s['cal']['mid'] == 5, (s['lbl'], s['cal']))
    # المأخوذ هنا: rp2 (٣ أيام) + غرّة الشهر من فترة «الأيام» المحفوظة قبل قليل (١). أمّا الصفّ الذي كُتب من «جهازٍ آخر»
    # فلا تعرفه الصفحة قبل أن تُعيد القراءة، وهذا مقصود: سباقٌ تردّه القاعدةُ لا الواجهة. وأيّام rp1 نفسها غير مأخوذة.
    rec("وأيامها هي لا تُعلَّم مأخوذة (غيرها فقط)", s['cal']['taken'] == 4 and s['cal']['btn'] == dim(Y1, M1) - 4, s['cal'])
    await pg.evaluate("""()=>{const i=document.getElementById('rsv-msg'); i.value=%s; i.dispatchEvent(new Event('input',{bubbles:true}));}""" % json.dumps(HTMLISH))
    await save(pg)
    wr = await pg.evaluate(WRITES)
    up = [w for w in wr if w['op'] == 'update']
    row = up[-1]['row'] if up else {}
    rec("حفظ التعديل يحدّث الصفّ نفسه ولا يُنشئ غيره", len(up) == 1 and row.get('id') == 'rp1' and row.get('message') == HTMLISH and len(row.get('dates', [])) == 7, row.get('id'))
    rec("وأيامه كما كانت", row.get('dates') == M1_DAYS(10, 16))
    await click(pg, "[data-rsv-edit='rp1']", 500)
    xs = await pg.evaluate("""()=>({v:document.getElementById('rsv-msg').value, kids:document.querySelectorAll('#rsv-prev *').length,
        b:document.querySelectorAll('#rsv-root b, #rsv-root img').length, x:window.__xss||null})""")
    rec("نصٌّ فيه علامات HTML يُحفظ ويُعرض حرفًا لا شيفرة (في الحقل والمعاينة)", xs['v'] == HTMLISH and xs['kids'] == 0 and xs['b'] == 0 and not xs['x'], xs)
    await close_sheet(pg)

    # ── الإيقاف والتفعيل
    await click(pg, "[data-rsv-edit='rp2']", 500)
    s = await sheet(pg)
    rec("الفترة الموقوفة تفتح مطفأة بخدمتيها وبطريقة «أيام»", s['on'] is False and s['chips'] == ['s1:false', 's2:true', 's3:true'] and s['modes'][2] == 'days:true', (s['on'], s['chips'], s['modes']))
    await pg.evaluate("()=>{const c=document.getElementById('rsv-on'); c.checked=true; c.dispatchEvent(new Event('change',{bubbles:true}));}")
    await save(pg)
    up = [w for w in await pg.evaluate(WRITES) if w['op'] == 'update']
    rec("التفعيل يُكتب (active=true)", len(up) == 2 and up[-1]['row'].get('id') == 'rp2' and up[-1]['row'].get('active') is True)
    rs = await rows(pg)
    rec("وتزول شارة «موقوفة» من قائمتها", not next((r for r in rs if r['edit'] == 'rp2'), {}).get('pill', True))

    # ── ملاحظة الحجوزات القائمة قبل الحفظ: لا شيء يُلغى
    await open_new(pg)
    s = await sheet(pg)
    rec("شهرٌ فيه حجوزات: ملاحظة تحذيرٍ تقول إنّها تبقى ولا تُلغى", 'warn' in s['note'] and "تبقى كما هي ولا تُلغى" in s['noteTxt'], s['noteTxt'][:90])
    await nav(pg, 2)
    s = await sheet(pg)
    rec("وشهرٌ بلا حجوزات: «لا حجوزات قائمة تتأثر»", 'ok' in s['note'] and "لا حجوزات قائمة" in s['noteTxt'], s['noteTxt'][:90])
    await close_sheet(pg)

    # ── الحذف بخطوتين
    await _H.open_settings(pg, "exceptions", 800)
    w0 = len(await pg.evaluate(WRITES))
    await click(pg, "[data-rsv-del='rp1']", 300)
    rs = await rows(pg)
    rec("الضغطة الأولى تسأل ولا تحذف", any(r['t'] == 'حذف هذه الفترة؟' for r in rs) and len(await pg.evaluate(WRITES)) == w0)
    await click(pg, "[data-rsv-no]", 300)
    rs = await rows(pg)
    rec("«تراجع» يعيد الصفّ كما كان", len(rs) == 5 and not any(r['t'] == 'حذف هذه الفترة؟' for r in rs) and len(await pg.evaluate(WRITES)) == w0, len(rs))
    await click(pg, "[data-rsv-del='rp1']", 300)
    await click(pg, "[data-rsv-yes]", 700)
    wr = await pg.evaluate(WRITES)
    rec("التأكيد يحذف الصفّ المقصود وحده", wr[-1] == {'op': 'delete', 'id': 'rp1'} and len(wr) == w0 + 1, wr[-1])
    rs = await rows(pg)
    rec("ويختفي من القائمة", not any(r['edit'] == 'rp1' for r in rs) and len(rs) == 4, [r['edit'] for r in rs])
    rec("الإجازات لم تُمسّ بالحذف", await pg.evaluate("()=>document.querySelectorAll('#view .card [data-delov]').length") == 2)
    await pg.screenshot(path=f"{_H.SHOTS}/46-reserved-after.png", full_page=True)
    rec("لا خطأ في صفحة اللوحة طوال الجلسة", not errs, "; ".join(errs[:2]))
    await ctx.close()

# ════════════════════════ صفحة العميلة ════════════════════════
GRID = """()=>({
  label:(document.getElementById('monthLabelText')||{}).textContent,
  days:[...document.querySelectorAll('#week .day')].map(b=>({n:(b.textContent||'').trim(), blank:b.classList.contains('blank'),
      rsv:b.classList.contains('rsv'), dis:!!b.disabled, aria:b.getAttribute('aria-disabled'), title:b.title||'', sel:b.classList.contains('sel'),
      vis:getComputedStyle(b).visibility})),
  msg:(()=>{const m=document.getElementById('rsvMsg'); return m?{t:m.textContent.trim(), role:m.getAttribute('role'), first:document.getElementById('cal').firstElementChild===m}:null;})(),
  none:!!document.querySelector('#week .state-msg'),
  shut:document.getElementById('cal').classList.contains('shut')})"""
async def grid(pg): return await pg.evaluate(GRID)
def real(g): return [d for d in g['days'] if not d['blank']]
def open_set(g): return {int(d['n']) for d in real(g) if not d['dis'] and not d['rsv']}
def rsv_set(g): return {int(d['n']) for d in real(g) if d['rsv']}
async def rpc(pg, name): return await pg.evaluate("(n)=>(window.__RPC||[]).filter(r=>r.name===n).map(r=>r.args)", name)

async def to_cal(pg, idx, month_clicks=1):
    await pg.goto(f"http://127.0.0.1:{PORT}/index.html")
    await pg.wait_for_timeout(1600)
    await pg.evaluate("(i)=>{window.__pick(i,1); window.__goto(2);}", idx)
    await pg.wait_for_timeout(1400)
    for _ in range(month_clicks):
        await click(pg, '#mNext', 900)

def res_a(a, b, svc, msg, mode='range'):
    return [{"mode": mode, "dates": M1_DAYS(a, b), "service_ids": svc, "message": msg}]

async def client_part(b):
    MSG = "هذا الشهر للعرائس فقط"
    # ── خطّ الأساس: لا فترات
    ctx, pg, errs = await mk(b, MOCK, "window.__RESERVED__ = [];")
    await to_cal(pg, 1)
    g0 = await grid(pg); B = open_set(g0)
    rec("خطّ الأساس: أيامٌ مفتوحة في الشهر التالي ولا يومَ مخصّصًا ولا رسالة", len(B) > 5 and not rsv_set(g0) and g0['msg'] is None, len(B))
    sig0 = (await rpc(pg, 'days_with_availability'))[-1]
    rec("نداء الإتاحة يحمل خدمات السلّة (p_service_ids)", sig0.get('p_service_ids') == ['s2'] and sig0.get('p_duration_min') == 45, sig0)
    await ctx.close()

    # ── فترةٌ للعروس في الشهر التالي، والسلّة سهرة
    RS = res_a(5, 15, ["s1"], MSG)
    ctx, pg, errs = await mk(b, MOCK, f"window.__RESERVED__ = {json.dumps(RS)};")
    await to_cal(pg, 1)
    g = await grid(pg)
    inr = set(range(5, 16))
    rec("السهرة وحدها: كلُّ يومٍ كان مفتوحًا داخل الفترة يُرسم «مخصّصًا»", rsv_set(g) == (B & inr) and len(rsv_set(g)) > 3, (sorted(rsv_set(g)), sorted(B & inr)))
    rec("وما خارج الفترة يبقى مفتوحًا كما كان", open_set(g) == B - inr, (sorted(open_set(g)), sorted(B - inr)))
    rec("والمقفل في الأساس (الجمعات) داخل الفترة يبقى مقفلًا لا مخصّصًا",
        all(not d['rsv'] and d['dis'] for d in real(g) if int(d['n']) in inr and int(d['n']) not in B), [d for d in real(g) if int(d['n']) in inr and int(d['n']) not in B][:2])
    rsv_days = [d for d in real(g) if d['rsv']]
    rec("اليوم المخصّص يحمل رسالة إيمان في title وaria-disabled ولا يُعطَّل بـdisabled", all(d['title'] == MSG and d['aria'] == 'true' and not d['dis'] for d in rsv_days), rsv_days[:1])
    rec("رسالة إيمان فوق التقويم، كما كتبتها، بدور status", g['msg'] and g['msg']['t'] == MSG and g['msg']['role'] == 'status' and g['msg']['first'], g['msg'])
    rec("ولا يقال «لا أوقات متاحة» والشهر فيه أيامٌ مفتوحة", not g['none'])
    first_blank = calendar.monthrange(Y1, M1)[0] != 6      # الأحد = 6 في calendar
    blanks = [d for d in g['days'] if d['blank']]
    rec("خانات ما قبل غرّة الشهر مخفيّة لا مربّعاتٍ فارغة", (not first_blank) or (blanks and all(d['vis'] == 'hidden' for d in blanks)), len(blanks))
    await pg.screenshot(path=f"{_H.SHOTS}/47-client-reserved.png")

    n_slots = len(await rpc(pg, 'available_slots'))
    target = sorted(rsv_set(g))[0]
    await pg.evaluate("(n)=>[...document.querySelectorAll('#week .day.rsv')].find(b=>b.textContent.trim()==n).click()", str(target))
    await pg.wait_for_timeout(500)
    g2 = await grid(pg)
    rec("الضغط على اليوم المخصّص لا يختاره ولا يطلب أوقاتًا", not any(d['sel'] for d in g2['days']) and len(await rpc(pg, 'available_slots')) == n_slots)
    rec("بل يُنبّه الرسالة (pulse)", await pg.evaluate("()=>document.getElementById('rsvMsg').classList.contains('pulse')"))

    # ── نصل بالعروس إلى السلّة: كلّ شيء مفتوح
    await pg.evaluate("()=>window.__pick(0,1)")
    await pg.wait_for_timeout(1100)
    g3 = await grid(pg)
    rec("عروسٌ مع سهرة: لا يومَ مخصّصًا ولا رسالة، والأيام كلّها مفتوحةٌ كالأساس", not rsv_set(g3) and g3['msg'] is None and open_set(g3) == B, (sorted(open_set(g3)), len(B)))
    sg = (await rpc(pg, 'days_with_availability'))[-1]
    rec("وتتبع الشبكةُ السلّةَ الجديدة: خدماتٌ مرتّبة ومدّةٌ مجموعة", sg.get('p_service_ids') == ['s1', 's2'] and sg.get('p_duration_min') == 105, sg)
    await pg.evaluate("(n)=>[...document.querySelectorAll('#week .day')].find(b=>b.textContent.trim()==n && !b.disabled).click()", str(target))
    await pg.wait_for_timeout(1000)
    sl = (await rpc(pg, 'available_slots'))[-1]
    nt = await pg.evaluate("()=>document.querySelectorAll('#times button, #times .slot, #times .t').length")
    rec("وتُختار فيها الأيام المخصّصة وتُعرض أوقاتها (والنداء يحمل خدمات السلّة)", sl.get('p_service_ids') == ['s1', 's2'] and nt > 0, (sl, nt))
    await pg.evaluate("()=>window.__pick(0,0)")
    await pg.wait_for_timeout(1100)
    g4 = await grid(pg)
    rec("وإذا رجعنا إلى السهرة وحدها عادت الأيام مخصّصةً ورُدّ اختيارُ اليوم", rsv_set(g4) == rsv_set(g) and g4['msg'] is not None and not any(d['sel'] for d in g4['days']))

    # ── الشهر الحالي لا فترات فيه ولا رسالة
    await click(pg, '#mPrev', 900)
    g5 = await grid(pg)
    rec("الشهر الذي لا فترة فيه: لا رسالة ولا أيامَ مخصّصة", g5['msg'] is None and not rsv_set(g5), g5['label'])

    # ── عقد الحجز: p_features وحكم الخادم الأخير
    res = await pg.evaluate("""async(a)=>{
      const m = await import('/assets/db.js');
      const base = {name:'اختبار', phone:'966500000000', time:'16:00:00'};
      const out = {};
      try { await m.createBooking({...base, date:a.rsv, serviceIds:['s2']}); out.alone='accepted'; } catch(e){ out.alone=e.message; }
      try { const r = await m.createBooking({...base, date:a.rsv, serviceIds:['s1','s2']}); out.bride = r && r.ref; } catch(e){ out.bride='ERR '+e.message; }
      try { const r = await m.createBooking({...base, date:a.free, serviceIds:['s2']}); out.free = r && r.ref; } catch(e){ out.free='ERR '+e.message; }
      out.booked = (window.__BOOKED||[]).map(x=>[x.p_date, x.p_service_ids, x.p_features]);
      out.refused = (window.__REFUSED||[]).map(x=>[x.p_date, x.p_service_ids, x.p_features]);
      return out;}""", {"rsv": iso(Y1, M1, 8), "free": iso(Y1, M1, 20)})
    rec("السهرة وحدها في يومٍ مخصّص: يرفضها الخادم برسالة إيمان نفسها", res['alone'] == MSG, res['alone'])
    rec("والعروس مع السهرة تُقبل، واليوم الحرّ يُقبل", str(res['bride']).startswith('EA-') and str(res['free']).startswith('EA-'), (res['bride'], res['free']))
    rec("كلّ حجزٍ يحمل مصافحة الميزات p_features=1 (مرفوضًا ومقبولًا)",
        res['refused'] == [[iso(Y1, M1, 8), ['s2'], 1]] and all(x[2] == 1 for x in res['booked']) and len(res['booked']) == 2, res)
    rec("لا خطأ في صفحة العميلة", not errs, "; ".join(errs[:2]))
    await ctx.close()

    # ── شهرٌ كاملٌ مخصّص: يُرى مخطّطًا بسببه لا «لا أوقات»
    RS = [{"mode": "month", "dates": M1_DAYS(1, dim(Y1, M1)), "service_ids": ["s1"], "message": "ديسمبر للعرائس"}]
    ctx, pg, errs = await mk(b, MOCK, f"window.__RESERVED__ = {json.dumps(RS)};")
    await to_cal(pg, 1)
    gm = await grid(pg)
    rec("شهرٌ كامل: كلّ أيامه المفتوحة أصلًا مخصّصة", rsv_set(gm) == B and not open_set(gm), (sorted(rsv_set(gm)), len(B)))
    rec("ولا يُقال «لا توجد أوقات متاحة»؛ تُرى الرسالة", not gm['none'] and gm['msg'] and gm['msg']['t'] == "ديسمبر للعرائس")
    rec("والشهر ليس «مغلقًا» (ليس تمويه شهرٍ مشطوب)", not gm['shut'])
    await pg.screenshot(path=f"{_H.SHOTS}/48-client-month-reserved.png")
    rec("لا خطأ", not errs, "; ".join(errs[:2]))
    await ctx.close()

    # ── فترتان بنصّين في الشهر نفسه يُقرآن معًا بترتيب أيامهما؛ وفترتان بنصٍّ واحد سطرٌ واحد؛ ولكلّ يومٍ نصُّه في title
    RS = res_a(5, 8, ["s1"], "نصّ الأولى") + res_a(12, 13, ["s1"], "نصّ الأولى") + res_a(20, 23, ["s1"], "نصّ الثانية")
    ctx, pg, errs = await mk(b, MOCK, f"window.__RESERVED__ = {json.dumps(RS)};")
    await to_cal(pg, 1)
    gt = await grid(pg)
    lines = await pg.evaluate("()=>[...document.querySelectorAll('#rsvMsg p')].map(p=>p.textContent)")
    rec("فترتان بنصّين: يظهر النصّان بترتيب أيامهما، والمكرَّر سطرٌ واحد", lines == ["نصّ الأولى", "نصّ الثانية"], lines)
    own = {int(d['n']): d['title'] for d in real(gt) if d['rsv']}
    rec("ولكلّ يومٍ مخصّص نصُّ فترته في title", own and all(t == ("نصّ الأولى" if n < 15 else "نصّ الثانية") for n, t in own.items()), own)
    rec("والأيام المخصّصة هي المفتوحة أصلًا داخل الفترتين", set(own) == B & (set(range(5, 9)) | {12, 13} | set(range(20, 24))), sorted(own))
    rec("لا خطأ", not errs, "; ".join(errs[:2]))
    await ctx.close()

    # ── ما تكتبه المديرة لا يُفسَّر شيفرة: النصّ حرفًا في الرسالة وفي title
    RS = res_a(5, 15, ["s1"], HTMLISH)
    ctx, pg, errs = await mk(b, MOCK, f"window.__RESERVED__ = {json.dumps(RS)};")
    await to_cal(pg, 1)
    gx = await grid(pg)
    kids = await pg.evaluate("()=>({t:[...document.querySelectorAll('#rsvMsg p')].map(p=>p.textContent), el:document.querySelectorAll('#rsvMsg p *, #rsvMsg img').length, x:window.__xss||null})")
    rec("نصٌّ فيه علامات HTML يُعرض حرفًا: لا عنصرَ داخل الرسالة ولا شيفرة تعمل", kids['t'] == [HTMLISH] and kids['el'] == 0 and not kids['x'], kids)
    rec("وهو في title اليوم كما كُتب", all(d['title'] == HTMLISH for d in real(gx) if d['rsv']) and rsv_set(gx))
    rec("لا خطأ", not errs, "; ".join(errs[:2]))
    await ctx.close()

    # ── بصمة السلّة تحمل المعرّفات: خدمتان بالمدّة نفسها
    RS = res_a(5, 15, ["s3"], "للتسريحة فقط")
    ctx, pg, errs = await mk(b, MOCK_SAME, f"window.__RESERVED__ = {json.dumps(RS)};")
    await to_cal(pg, 1)
    gs = await grid(pg)
    rec("(مدّتان متساويتان) السهرة وحدها: الأيام مخصّصة للتسريحة", len(rsv_set(gs)) > 3, sorted(rsv_set(gs)))
    n_before = len(await rpc(pg, 'days_with_availability'))
    await pg.evaluate("()=>{const st=window.__state(); st.counts.s2=0; st.counts.s3=1; window.__pick(2,1);}")
    await pg.wait_for_timeout(1100)
    gs2 = await grid(pg)
    calls = await rpc(pg, 'days_with_availability')
    rec("استبدال السهرة بالتسريحة (٤٥ دقيقة لكلّ منهما) يعيد جلب الشهر", len(calls) > n_before and calls[-1].get('p_service_ids') == ['s3'] and calls[-1].get('p_duration_min') == 45, calls[-1])
    rec("فتُفتح الأيام بعد أن كانت مخصّصة (لا شبكةٌ قديمة)", not rsv_set(gs2) and gs2['msg'] is None and len(open_set(gs2)) >= len(B) - 1)
    rec("لا خطأ", not errs, "; ".join(errs[:2]))
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**_H.CHROME, args=["--no-sandbox"])
        await admin_part(b)
        await client_part(b)
        await b.close()

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
