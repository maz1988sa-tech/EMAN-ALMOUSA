# -*- coding: utf-8 -*-
"""فصل المختبر عن الحيّ — يُقاس على الملفّات وفي المتصفّح معًا.

الخطر هنا صامت: نسخةٌ تجريبية تبدو تجريبية وهي الحيّة، أو ترقيةٌ تنقل
شيئًا غير الذي جُرّب. فيُفحص أمران: أنّ الملفّين متطابقان بايتًا ببايت
فالترقية نسخٌ محض، وأنّ الصفحة نفسها تتكلّم في /lab/ وتصمت في الجذر.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, filecmp, os, pathlib, re, shutil, subprocess, sys, tempfile
import http.server, socketserver, threading, functools
from playwright.async_api import async_playwright

REPO = pathlib.Path(str(_H.REPO))
LAB  = REPO / 'lab'
ITEMS = ['index.html', 'admin.html', 'sw.js',
         'manifest.webmanifest', 'manifest-admin.webmanifest', 'assets']

R = []
def rec(n, ok, note=""):
    R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

# ── ١) الملفّات: المختبر كاملٌ، والحيّ مجمَّدٌ على ما رُفع
missing = [i for i in ITEMS if not (LAB / i).exists()]
rec("المختبر يحمل الموقع كاملًا", not missing, str(missing))

remote = subprocess.run(['git', '-C', str(REPO), 'rev-parse',
                         'origin/claude/iman-booking-system-s8s6rh'],
                        capture_output=True, text=True).stdout.strip()
# للجذر حالان صحيحتان لا واحدة: إمّا أنه ما على GitHub بالضبط — فالعمل
# كلُّه في المختبر ولم يصل الناسَ شيء — وإمّا أنه المختبرُ نفسه، أي أنّ
# ترقيةً جرت للتوّ. وما بينهما خطأ: جذرٌ لا هو المنشور ولا هو المُجرَّب.
# الحارس الحقيقيّ ليس «الجذر يساوي كذا اليوم» — فبين ترقيةٍ ورفعها يتقدّم
# المختبر فيختلفان بحقّ. الحارس أنّ **الجذر لا يتغيّر إلّا نسخًا من
# المختبر**: يُنظَر إلى الكومت الذي غيّر الجذر آخر مرّة، فإن كان الجذر
# فيه يطابق المختبر فالنسخة محضٌ ولا يد فيها.
last = subprocess.run(['git', '-C', str(REPO), 'log', '-1', '--format=%H', '--', *ITEMS],
                      capture_output=True, text=True).stdout.strip()
drift = []
for i in ITEMS:
    a = subprocess.run(['git', '-C', str(REPO), 'rev-parse', f'{last}:{i}'],
                       capture_output=True, text=True).stdout.strip()
    b = subprocess.run(['git', '-C', str(REPO), 'rev-parse', f'{last}:lab/{i}'],
                       capture_output=True, text=True).stdout.strip()
    if not a or a != b:
        drift.append(i)
rec("الجذر لم يتغيّر إلّا نسخًا من المختبر", not drift,
    f"@{last[:8]} — {drift[:3] if drift else 'مطابق'}")

# ولا يُترك الجذر معدَّلًا خارج كومت: تغييرٌ لم يُسجَّل يفلت من كلّ حارس.
dirty = subprocess.run(['git', '-C', str(REPO), 'status', '--porcelain', '--', *ITEMS],
                       capture_output=True, text=True).stdout.strip()
rec("ولا تغييرَ في الجذر خارج كومت", not dirty, dirty[:60])
# وحين يتقدّم المختبر على الجذر وجب أن يحمل إصدار أصولٍ أحدث، وإلّا خدم
# المتصفّح ملفَّه المحفوظ بعد الترقية.
lab_same = all(
    (filecmp.cmp(LAB / i, REPO / i, shallow=False) if (REPO / i).is_file()
     else not filecmp.dircmp(LAB / i, REPO / i).diff_files)
    for i in ITEMS)
if not lab_same:
    lab_v = set(re.findall(r'\?v=(\d+)', (LAB / 'index.html').read_text(encoding='utf-8')))
    root_v = set(re.findall(r'\?v=(\d+)', (REPO / 'index.html').read_text(encoding='utf-8')))
    rec("والمختبر المتقدّم يحمل إصدارًا أحدث",
        bool(lab_v) and bool(root_v) and max(map(int, lab_v)) > max(map(int, root_v)),
        f"lab={sorted(lab_v)} root={sorted(root_v)}")

# ── ٢) الترقية نسخٌ محض: نجرّبها على نسخةٍ من المستودع لا عليه
with tempfile.TemporaryDirectory() as tmp:
    work = pathlib.Path(tmp) / 'repo'
    shutil.copytree(REPO, work, symlinks=True,
                    ignore=shutil.ignore_patterns('node_modules', '.git', 'dist'))
    out = subprocess.run(['bash', 'tools/promote.sh'], cwd=work,
                         capture_output=True, text=True)
    rec("الترقية تنجح وتُبلغ بالتطابق",
        out.returncode == 0 and 'بايتًا ببايت' in out.stdout,
        (out.stdout + out.stderr).strip().splitlines()[-1][:70] if (out.stdout or out.stderr) else '')
    diffs = [i for i in ITEMS if not (
        filecmp.cmp(work / 'lab' / i, work / i, shallow=False) if (work / i).is_file()
        else not filecmp.dircmp(work / 'lab' / i, work / i).diff_files)]
    rec("وبعدها الجذر = المختبر في كل ملفّ", not diffs, str(diffs))

    # وتُكشف المخالفة: لو غُيّر الجذر وحده وجب أن يصرخ الفحص
    (work / 'index.html').write_text(
        (work / 'index.html').read_text(encoding='utf-8') + '\n<!-- x -->', encoding='utf-8')
    bad = subprocess.run(['bash', 'tools/promote.sh', '--check'], cwd=work,
                         capture_output=True, text=True)
    rec("والفحص يكشف أيّ فرقٍ بينهما", bad.returncode != 0,
        'رصد الاختلاف' if bad.returncode else 'لم يرصد!')

# ── ٣) في المتصفّح: الشارة تظهر في /lab/ وحدها
ROOT_SRV = pathlib.Path(f'{_H.SHOTS}/labroot')
if ROOT_SRV.exists(): shutil.rmtree(ROOT_SRV)
ROOT_SRV.mkdir(parents=True)
for i in ITEMS:
    src = REPO / i
    (shutil.copytree if src.is_dir() else shutil.copy2)(src, ROOT_SRV / i)
shutil.copytree(LAB, ROOT_SRV / 'lab')
shutil.copytree(REPO / 'dev', ROOT_SRV / 'dev')

class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(H, directory=str(ROOT_SRV)))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
MOCK = (REPO / 'dev/mock-supabase.js').read_text(encoding='utf-8')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(
            **_H.CHROME,
            args=["--no-sandbox"])
        for label, prefix, want in (("المختبر", "/lab", True), ("الحيّ", "", False)):
            ctx = await b.new_context(viewport={"width": 430, "height": 932},
                                      device_scale_factor=2)
            await ctx.route("**/assets/vendor/supabase.js",
                            lambda r: asyncio.ensure_future(r.fulfill(
                                content_type="application/javascript", body=MOCK)))
            pg = await ctx.new_page()
            errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
            await pg.goto(f"http://127.0.0.1:{PORT}{prefix}/admin.html")
            await pg.wait_for_timeout(1800)
            m = await pg.evaluate("""()=>{const f=document.querySelector('.labflag');
              const cs=f?getComputedStyle(f):null;
              return {lab:!!window.__LAB__, cls:document.documentElement.classList.contains('is-lab'),
                      shown: !!(cs && cs.display!=='none' && f.getBoundingClientRect().height>0),
                      txt: f?f.innerText.trim():'',
                      robots: !!document.querySelector('meta[name="robots"]'),
                      top: f?Math.round(f.getBoundingClientRect().top):null,
                      z: cs?cs.zIndex:null};}""")
            rec(f"[{label}] الشارة {'تظهر' if want else 'لا تظهر'}", m["shown"] is want,
                m["txt"][:44] if m["shown"] else "—")
            rec(f"[{label}] العلم يعرف موضعه", m["lab"] is want and m["cls"] is want)
            if want:
                rec("[المختبر] الشارة في أعلى الصفحة وفوق كل شيء",
                    m["top"] == 0 and int(m["z"]) > 1000, f'top={m["top"]} z={m["z"]}')
                rec("[المختبر] noindex مضاف", m["robots"])
                sw = await pg.evaluate("()=>navigator.serviceWorker.getRegistrations().then(r=>r.length)")
                rec("[المختبر] بلا service worker يخبّئ القديم", sw == 0, str(sw))
            rec(f"[{label}] بلا أخطاء", not errs, "; ".join(errs[:2]))
            await pg.screenshot(path=f"{_H.SHOTS}/37-{'lab' if want else 'live'}.png")
            await ctx.close()

        # صفحة العميلة في المختبر: الشارة لا تقتطع أسفل التطبيق
        ctx = await b.new_context(viewport={"width": 390, "height": 760},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js",
                        lambda r: asyncio.ensure_future(r.fulfill(
                            content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.goto(f"http://127.0.0.1:{PORT}/lab/index.html")
        await pg.wait_for_timeout(1700)
        g = await pg.evaluate("""()=>{const a=document.getElementById('app').getBoundingClientRect();
          const f=document.querySelector('.labflag').getBoundingClientRect();
          return {appTop:Math.round(a.top), appBottom:Math.round(a.bottom),
                  vh:innerHeight, flagH:Math.round(f.height)};}""")
        rec("[العميلة] التطبيق يبدأ تحت الشارة", g["appTop"] >= g["flagH"] - 1,
            f'app@{g["appTop"]} flag={g["flagH"]}')
        rec("[العميلة] ولا يخرج أسفله عن الشاشة",
            abs(g["appBottom"] - g["vh"]) <= 1, f'{g["appBottom"]} / {g["vh"]}')
        await pg.screenshot(path=f"{_H.SHOTS}/37-lab-client.png")
        await ctx.close()
        await b.close()

asyncio.run(main())
shutil.rmtree(ROOT_SRV, ignore_errors=True)
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
