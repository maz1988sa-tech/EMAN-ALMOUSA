# -*- coding: utf-8 -*-
"""وسائط الخدمة كما تُرى، لا كما تُكتب.

شكا صاحب المشروع أنّ ما تُرفقه زوجته من صورةٍ أو فيديو لا يظهر في صفحة
الحجز، وتبقى البطاقة باسمٍ وخلفيةٍ صمّاء. وكان لذلك ثلاثة أسباب اجتمعت:
خدمةٌ مخفيّة تحمل الوسيطة فلا تصل العميلة أصلًا، وفيديو بلا ملصقٍ يُخرج
`url('')` فتصير البطاقة صمّاء، واحتياطٌ يُختار بالترتيب فتلبس خدمةٌ وجهَ
غيرها.

فهذا الطقم يقيس ما رسمه المتصفّح: مصدرُ الوسيطة الفعليّ، وأنّ الصورة
انطبعت (naturalWidth)، وأنّ خلفيّةً فارغةً لا تخرج أبدًا.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, re, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright

ROOT = str(_H.ROOT)

class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

MOCK = open(os.path.join(ROOT, "dev/mock-supabase.js"), encoding="utf-8").read()

# خدماتٌ مصنوعة لهذا الفحص وحده، فلا تتأثّر بقيّة الطُّقُم.
FIXTURE = """  const SERVICES = [
    { id:'m1', name:'ميك اب عروس', icon:'bride', price:1500, duration_min:60,
      description:'بلا وسيطة — يُنتظر احتياط الاسم', sort:1, active:true,
      bookable_by_client:true, group_discount:false, deposit_amount:375,
      media_kind:null, media_path:null, poster_path:null, media_x:50, media_y:50, media_zoom:1 },
    { id:'m2', name:'ميك اب سهرة', icon:'evening', price:600, duration_min:45,
      description:'صورة مرفوعة', sort:2, active:true,
      bookable_by_client:true, group_discount:true, deposit_amount:150,
      media_kind:'image', media_path:'svc/up-image.jpg', poster_path:null,
      media_x:50, media_y:30, media_zoom:1.2 },
    { id:'m3', name:'تسريحة شعر', icon:'mirror', price:400, duration_min:40,
      description:'فيديو مع ملصق', sort:3, active:true,
      bookable_by_client:true, group_discount:true, deposit_amount:100,
      media_kind:'video', media_path:'svc/up-video.mp4', poster_path:'svc/up-poster.jpg',
      media_x:50, media_y:50, media_zoom:1 },
    { id:'m4', name:'مكياج زواج ٢', icon:'sparkle', price:900, duration_min:50,
      description:'فيديو بلا ملصق', sort:4, active:true,
      bookable_by_client:true, group_discount:true, deposit_amount:200,
      media_kind:'video', media_path:'svc/bare-video.mp4', poster_path:null,
      media_x:50, media_y:50, media_zoom:1 },
    { id:'m5', name:'خدمة مخفية', icon:'sparkle', price:700, duration_min:40,
      description:'مخفيّة وتحمل وسيطة', sort:5, active:false,
      bookable_by_client:false, group_discount:false, deposit_amount:100,
      media_kind:'video', media_path:'svc/hidden-video.mp4', poster_path:'svc/hidden-poster.jpg',
      media_x:50, media_y:50, media_zoom:1 },
  ];
"""
MOCK_MEDIA = re.sub(r"  const SERVICES = \[.*?\n  \];\n", FIXTURE, MOCK, count=1, flags=re.S)
assert MOCK_MEDIA != MOCK, "لم يُستبدل جدول الخدمات في المحاكي"

JPG = (_H.LAB / 'assets' / 'brand' / 'pst_bridal.jpg').read_bytes()
MP4 = (_H.LAB / 'assets' / 'brand' / 'svc_bridal.mp4').read_bytes()

R = []
def rec(n, ok, note=""):
    R.append((n, ok))
    print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

async def serve_media(route):
    """ما يشير إلى التخزين يُردّ ملفًّا حقيقيًّا، ليُقاس الانطباع لا الرابط."""
    url = route.request.url
    if url.endswith('.mp4') or url.endswith('.mov'):
        await route.fulfill(status=200, content_type='video/mp4', body=MP4)
    else:
        await route.fulfill(status=200, content_type='image/jpeg', body=JPG)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**_H.CHROME, args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 390, "height": 780},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js",
                        lambda r: asyncio.ensure_future(r.fulfill(
                            content_type="application/javascript", body=MOCK_MEDIA)))
        await ctx.route("https://mock.local/**", lambda r: asyncio.ensure_future(serve_media(r)))
        pg = await ctx.new_page()
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html")
        await pg.wait_for_timeout(1800)
        await pg.evaluate("window.__goto(1)")
        await pg.wait_for_timeout(1200)

        cards = await pg.evaluate("""() => [...document.querySelectorAll('#svcRail .svc')].map((c) => {
            const v = c.querySelector('video.bg'), i = c.querySelector('img.bg');
            const h2 = c.querySelector('h2');
            return { name: h2 ? h2.textContent.trim() : null,
                     kind: v ? 'video' : i ? 'img' : 'none',
                     src: v ? (v.querySelector('source') || {}).src || '' : i ? i.src : '',
                     poster: v ? v.getAttribute('poster') : null,
                     painted: i ? i.naturalWidth > 0 : null,
                     style: (v || i) ? (v || i).getAttribute('style') || '' : '' };
        })""")
        by = {c["name"]: c for c in cards}

        rec("الخدمة المخفيّة لا تصل العميلة", "خدمة مخفية" not in by,
            "الأسماء: " + " · ".join(by))

        c = by.get("ميك اب سهرة", {})
        rec("الصورة المرفوعة هي خلفيّة البطاقة",
            c.get("kind") == "img" and c.get("src", "").endswith("service-media/svc/up-image.jpg"),
            f"{c.get('kind')} · {c.get('src','')[-42:]}")
        rec("الصورة المرفوعة انطبعت فعلًا", c.get("painted") is True)
        rec("تموضع الصورة كما ضُبط في اللوحة",
            "50% 30%" in c.get("style", "") and "scale(1.2)" in c.get("style", ""),
            c.get("style", ""))

        c = by.get("تسريحة شعر", {})
        rec("الفيديو المرفوع هو مصدر البطاقة",
            c.get("kind") == "video" and c.get("src", "").endswith("service-media/svc/up-video.mp4"),
            f"{c.get('kind')} · {c.get('src','')[-42:]}")
        rec("ملصق الفيديو هو الصورة المرفوعة",
            (c.get("poster") or "").endswith("service-media/svc/up-poster.jpg"),
            str(c.get("poster"))[-42:])

        # العطب الذي رآه الناس: بطاقةٌ صمّاء لأنّ الملصق فارغ.
        c = by.get("مكياج زواج ٢", {})
        rec("فيديو بلا ملصق لا يترك البطاقة بلا صورة",
            bool((c.get("poster") or "").strip()), f"poster={c.get('poster')!r}")
        rec("فيديو بلا ملصق لا يلبس وجه خدمةٍ أخرى",
            "bridal" not in (c.get("poster") or "") and "evening" not in (c.get("poster") or ""),
            str(c.get("poster")))

        c = by.get("ميك اب عروس", {})
        rec("خدمةٌ بلا وسيطة تأخذ احتياطها بالاسم",
            "bridal" in (c.get("src", "") + str(c.get("poster") or "")),
            f"{c.get('src','')[-30:]} · {c.get('poster')}")

        # خلفيّةٌ فارغة في السلّة: `url('')` كانت تُرسم من نفس العطب.
        await pg.evaluate("()=>{window.__pick(1,1); window.__pick(2,1); window.__pick(3,1);}")
        await pg.wait_for_timeout(700)
        await pg.evaluate("window.__goto(3)")
        await pg.wait_for_timeout(900)
        thumbs = await pg.evaluate("""() => [...document.querySelectorAll('.th, .art')].map((e) =>
            getComputedStyle(e).backgroundImage)""")
        empty = [t for t in thumbs if (not t) or t == 'none' or 'url("")' in t or "url('')" in t]
        rec("لا صورة فارغة في سلّة الاختيار", len(thumbs) > 0 and not empty,
            f"{len(thumbs)} صورة · فارغة {len(empty)}")

        await pg.screenshot(path=f"{_H.SHOTS}/34-svc-media.png")
        await ctx.close()
        await b.close()

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
