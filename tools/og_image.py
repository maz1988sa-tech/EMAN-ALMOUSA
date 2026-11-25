# -*- coding: utf-8 -*-
"""صورة معاينة الرابط: ما يظهر فوق العنوان حين يُلصق eman-aalmousa.com في واتساب (§٧ف).

واتساب — ومعه آي مسج وتيليجرام وإكس — يقرأ `og:image` من رأس الصفحة ويعرضها كبيرةً فوق العنوان والوصف إن
كانت عريضةً وخفيفة. فهي ١٢٠٠×٦٣٠، المقاس الذي تعرضه هذه التطبيقات كبيرًا. وهي JPEG لا WebP: واتساب لا يضمن
WebP في المعاينة، وما لا يُقرأ يُسقَط بصمت فتعود البطاقة بلا صورة. وتبقى دون ٣٠٠ ك.ب لأنّ واتساب يتجاهل الثقيل.

التصميم «أ، ورق العلامة» الذي اعتمده صاحب المشروع من ثلاثة (٢٥ نوفمبر ٢٠٢٦، صفحة المقترحات:
https://claude.ai/artifact/C1kEDAQeR9zafibiKU9UTi): الشعار الأصليّ على ورق الموقع داخل إطارٍ نحاسيّ رفيع، وتحته
«حجز موعد ◆ ميك اب عروس وسهرة» بخطّ أميري. ويُرسم من الأصول نفسها (`lockup.png` وخطوط `assets/fonts.css`) لا
من صورةٍ تُحرَّر باليد، فيوم يتغيّر الشعار يُعاد التوليد ولا يُعاد التصميم.

    .venv/bin/python tools/og_image.py          # lab/assets/brand/og.jpg
    .venv/bin/python tools/og_image.py --root   # والجذر معه: assets/brand/og.jpg

غيّرتَ الصورة؟ ارفع بصمة الأصول (`?v=`): رابطُ الصورة في الوسم يحملها، فيجلب واتساب الجديدة بدل المحفوظة عنده.
"""
import argparse, asyncio, base64, io, pathlib, shutil, sys
from PIL import Image
from playwright.async_api import async_playwright

REPO = pathlib.Path(__file__).resolve().parent.parent
ASSETS = REPO / 'lab' / 'assets'
W, H, QUALITY = 1200, 630, 86
MAX_KB = 300


def lockup_uri() -> str:
    im = Image.open(ASSETS / 'brand' / 'lockup.png').convert('RGBA')
    im = im.crop(im.getbbox())   # الشعار بحدوده: الهامش الشفّاف حول الأصل لا يدخل في القياس
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def page() -> str:
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<link rel="stylesheet" href="{(ASSETS / 'fonts.css').as_uri()}">
<style>
html,body{{margin:0;padding:0}}
.og{{width:{W}px;height:{H}px;position:relative;overflow:hidden;direction:rtl;background:#faf5f0}}
.glow{{position:absolute;inset:0;background:
  radial-gradient(ellipse 52% 62% at 50% 42%,#fffdfa 0%,rgba(255,253,250,0) 72%),
  radial-gradient(ellipse 90% 100% at 50% 50%,rgba(242,231,222,0) 58%,rgba(201,138,114,.13) 100%)}}
.frame{{position:absolute;inset:26px;border:1px solid rgba(176,112,92,.36)}}
.frame i{{position:absolute;left:50%;width:9px;height:9px;background:#b0705c;
  transform:translate(-50%,-50%) rotate(45deg);box-shadow:0 0 0 7px #faf5f0}}
.frame .t{{top:0}} .frame .b{{top:100%}}
.lock{{position:absolute;top:72px;left:50%;transform:translateX(-50%);height:372px}}
.line{{position:absolute;left:0;right:0;bottom:76px;display:flex;align-items:center;justify-content:center;gap:18px}}
.line span{{width:64px;height:1px;background:rgba(176,112,92,.55)}}
.line b{{font:400 32px/1 'Amiri',serif;color:#8e5644;letter-spacing:.01em}}
.sep{{width:7px;height:7px;background:#b0705c;transform:rotate(45deg);flex:none}}
</style></head><body>
<div class="og"><div class="glow"></div><div class="frame"><i class="t"></i><i class="b"></i></div>
<img class="lock" src="{lockup_uri()}" alt="">
<div class="line"><span></span><b>حجز موعد</b><i class="sep"></i><b>ميك اب عروس وسهرة</b><span></span></div></div>
</body></html>"""


async def render(dst: pathlib.Path) -> None:
    # يُكتب المستند في build/ (خارج git) لا في الذاكرة: صفحةٌ من file:// وحدها تحمّل خطوطًا من file://.
    src = REPO / 'build' / 'og_image.html'
    src.parent.mkdir(exist_ok=True)
    src.write_text(page(), encoding='utf-8')
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--no-sandbox'])
        pg = await b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
        await pg.goto(src.as_uri(), wait_until='load')
        await pg.evaluate('document.fonts.ready')
        # خطٌّ لم يُحمَّل لا يُسقط شيئًا: يُرسم النصّ ببديلٍ صامت. فيُسأل عنه صراحةً قبل التصوير.
        if not await pg.evaluate("[...document.fonts].some(f => f.family.includes('Amiri') && f.status === 'loaded')"):
            sys.exit('خطّ أميري لم يُحمَّل — كانت الصورة ستُرسم بخطٍّ بديل')
        await pg.screenshot(path=str(dst), type='jpeg', quality=QUALITY,
                            clip={'x': 0, 'y': 0, 'width': W, 'height': H})
        await b.close()


def main() -> int:
    ap = argparse.ArgumentParser(description='صورة معاينة الرابط (og:image)')
    ap.add_argument('--root', action='store_true', help='انسخها إلى الجذر أيضًا')
    a = ap.parse_args()
    dst = ASSETS / 'brand' / 'og.jpg'
    asyncio.run(render(dst))
    im, kb = Image.open(dst), dst.stat().st_size / 1024
    print(f'{dst.relative_to(REPO)}  {im.width}×{im.height}  {kb:.0f} ك.ب')
    if (im.width, im.height) != (W, H) or kb >= MAX_KB:
        print(f'خارج الحدّ: المطلوب {W}×{H} ودون {MAX_KB} ك.ب', file=sys.stderr)
        return 1
    if a.root:
        root = REPO / 'assets' / 'brand' / 'og.jpg'
        shutil.copy2(dst, root)
        print(f'{root.relative_to(REPO)}  (نسخة الجذر)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
