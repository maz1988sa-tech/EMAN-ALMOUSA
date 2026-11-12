# -*- coding: utf-8 -*-
"""مسارات الفحص، محسوبةً من موضع المستودع لا مكتوبةً بيد.

كانت الطُّقُم تحمل مسارات حاويةٍ بعينها، فلا تعمل إلّا فيها. وفحصٌ لا
يعمل عند صاحبه ليس فحصًا. فصارت كلُّها تستورد من هنا.

    ROOT    جذر الخادم الذي تُفتح منه الصفحات أثناء الفحص (build/)
    REPO    جذر المستودع
    LAB     مكان العمل — lab/
    SHOTS   حيث تُحفظ اللقطات
    CHROME  ما يُمرَّر إلى launch(): مسار متصفّح صريح أو لا شيء

قبل أي تشغيل:  python3 tests/sync.py
"""
import os, pathlib

REPO   = pathlib.Path(__file__).resolve().parent.parent
LAB    = REPO / 'lab'
ROOT   = REPO / 'build' / 'testroot'
SHOTS  = REPO / 'build' / 'shots'
OUT    = REPO / 'build' / 'out'
SAMPLE = REPO / 'tests' / 'fixtures' / 'receipt-sample.jpg'

for d in (SHOTS, OUT):
    d.mkdir(parents=True, exist_ok=True)

def _chrome():
    """متصفّحٌ صريح إن طُلب، وإلّا فمتصفّح Playwright الذي نصّبه بنفسه."""
    p = os.environ.get('PW_CHROME')
    if p and pathlib.Path(p).exists():
        return {'executable_path': p}
    fixed = pathlib.Path('/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
    return {'executable_path': str(fixed)} if fixed.exists() else {}

CHROME = _chrome()


async def open_settings(pg, page=None, wait=900):
    """«الإعدادات» قائمةٌ تفتح صفحات (§٧س): التبويب يُفتح على قائمته، ثمّ صفحةٌ
    بعينها إن طُلبت بمعرّف صفّها — hours · exceptions · rules · location ·
    services · deposit · messages · numbers · page · clients · visitors ·
    backup · delete. الطُّقُم تعرف الطريق من هنا، فلا تتعطّل كلّما تغيّر ترتيب القائمة."""
    await pg.evaluate("()=>document.querySelector('[data-tab=settings]').click()")
    await pg.wait_for_timeout(wait)
    await pg.evaluate("()=>{const b=document.getElementById('setBack'); if(b) b.click();}")
    await pg.wait_for_timeout(300)
    if page:
        await pg.evaluate("(id)=>document.querySelector(`.setrow[data-setpage=${id}]`).click()", page)
        await pg.wait_for_timeout(wait)
