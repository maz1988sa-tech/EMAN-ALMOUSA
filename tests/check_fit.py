# -*- coding: utf-8 -*-
"""مطابقة اللوحة لنموذج «ضوء اليوم».

لا يكفي أن تعمل الشاشة؛ المطلوب أن تكون هي الشاشة التي وُوفق عليها. كل
تأكيدٍ هنا يقابل عنصرًا في النموذج: زرّ الإنجاز، وكتلة المبلغ، وإحصاء
اليوم، والتبويبات الحبّية، والقوس في الورقة، والمفاتيح في الإعدادات.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright

ROOT = str(_H.ROOT)
OUT  = "/home/claude/proj/cmp"
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
MOCK = open(os.path.join(ROOT, "dev/mock-supabase.js"), encoding="utf-8").read()

def ghazal_from_source():
    """يقرأ ديوان الغزل من admin.html مباشرةً: المصفوفة داخل وحدةٍ لا تُرى من الصفحة."""
    import re
    src = open(os.path.join(ROOT, "admin.html"), encoding="utf-8").read()
    body = re.search(r"const GHAZAL = \[(.*?)\n\];", src, re.S).group(1)
    ents = re.findall(r"\{\s*v:\s*\[\s*'([^']*)'\s*,\s*'([^']*)'\s*\]\s*,\s*p:\s*'([^']*)'", body)
    n = len(re.findall(r"\{\s*v:", body))
    keys = [f"{a}|{b}" for a, b, _ in ents]
    bad = [p for a, b, p in ents if not a.strip() or not b.strip() or not p.strip()]
    return {"n": n, "poets": sorted({p for _, _, p in ents}), "pairs": ents,
            "dup": len(keys) - len(set(keys)),
            "shape": len(ents) == n and not bad,
            "bad": f"مقروء={len(ents)} من {n}" + (f" · ناقص={bad[:2]}" if bad else "")}

ok = fail = 0
def rec(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1;   print(f"PASS {name}" + (f" — {extra}" if extra else ""))
    else:    fail += 1; print(f"FAIL {name} — {extra}")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(
            **_H.CHROME,
            args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 430, "height": 932}, device_scale_factor=2,
                                  permissions=["clipboard-read", "clipboard-write"])
        await ctx.route("**/assets/vendor/supabase.js",
                        lambda r: asyncio.ensure_future(r.fulfill(
                            content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
        await pg.goto(f"http://127.0.0.1:{PORT}/admin.html")
        await pg.wait_for_timeout(1900)

        # ── الشريط: علامة، اسم، حاجب لاتيني، ساعة ────────────────────
        bar = await pg.evaluate("""()=>{const b=document.querySelector('.appbar .bar');
          if(!b) return null; return {
            mark: !!b.querySelector('.brandmark'),
            name: b.querySelector('#bizName')?.textContent.trim(),
            sub:  b.querySelector('.sub')?.textContent.trim(),
            clock:b.querySelector('#clock')?.textContent.trim(),
            radius:getComputedStyle(b).borderRadius};}""")
        rec("الشريط يحمل العلامة والاسم", bar and bar["mark"] and bar["name"], str(bar and bar["name"]))
        rec("الحاجب اللاتيني تحت الاسم", bar and bar["sub"], str(bar and bar["sub"]))
        rec("الساعة تعمل في الشريط", bar and len(bar["clock"] or "") >= 4, str(bar and bar["clock"]))
        rec("الشريط حبّةٌ مستديرة لا حافّة", bar and bar["radius"].startswith("26"), str(bar and bar["radius"]))

        # ── التبويبات: نصٌّ بلا أيقونات، والمختار مملوء بلون الهوية ──
        tabs = await pg.evaluate("""()=>{const t=[...document.querySelectorAll('.tab')];
          const cur=t.find(x=>x.getAttribute('aria-current')==='page');
          const probe=document.createElement('i'); probe.style.color='var(--accent)';
          document.body.appendChild(probe);
          const accent=getComputedStyle(probe).color; probe.remove();
          return {n:t.length, svg:t.reduce((a,x)=>a+x.querySelectorAll('svg').length,0),
                  bg:cur?getComputedStyle(cur).backgroundColor:'', accent,
                  fits: document.querySelector('.appbar .tabs').scrollWidth
                        <= document.querySelector('.appbar .tabs').clientWidth + 1,
                  dot: !!cur?.querySelector('.dot')};}""")
        rec("خمسة تبويبات", tabs["n"] == 5, str(tabs["n"]))
        rec("التبويبات نصٌّ بلا أيقونات كالنموذج", tabs["svg"] == 0, f"svg={tabs['svg']}")
        rec("المختار مملوءٌ بلون الهوية", tabs["bg"] == tabs["accent"], f'{tabs["bg"]} = {tabs["accent"]}')
        rec("التبويبات الخمسة تتّسع بلا قصّ", tabs["fits"], str(tabs["fits"]))
        rec("عدّاد الطلبات على تبويب الرئيسية", tabs["dot"], str(tabs["dot"]))
        dot = await pg.evaluate("""()=>{const d=document.querySelector('.tab .dot');
          if(!d) return null; const s=getComputedStyle(d);
          const probe=document.createElement('i'); probe.style.background='var(--alert)';
          document.body.appendChild(probe);
          const al=getComputedStyle(probe).backgroundColor; probe.remove();
          return {bg:s.backgroundColor, alert:al, anim:s.animationName,
                  ring:s.outlineWidth, cur:d.closest('.tab').getAttribute('aria-current')};}""")
        rec("العدّاد أحمر ولو كان تبويبه مختارًا",
            dot and dot["bg"] == dot["alert"], f'{dot and dot["bg"]} vs {dot and dot["alert"]}')
        rec("وينبض", dot and dot["anim"] == "dot-pulse", str(dot and dot["anim"]))
        rec("وحلقةٌ تفصله عن أرضيّة التبويب المختار",
            dot and (dot["cur"] != "page" or dot["ring"] not in ("0px", "")), str(dot and dot["ring"]))

        # ── إحصاء اليوم أسفل التحيّة مباشرة ──────────────────────────
        st = await pg.evaluate("""()=>{const s=document.querySelector('.greet + .stats');
          if(!s) return null; const c=[...s.querySelectorAll('.stat')];
          return {n:c.length, k:c.map(x=>x.querySelector('.k')?.textContent.trim()),
                  v:c.map(x=>x.querySelector('.v')?.textContent.trim())};}""")
        rec("إحصاء اليوم يلي التحيّة مباشرة", st and st["n"] == 2, str(st and st["k"]))
        rec("الإحصاء عن اليوم لا عن الشهر",
            st and "مواعيد اليوم" in st["k"] and "المتوقّع اليوم" in st["k"], str(st and st["k"]))

        # ── بطاقة الحجز: زرّ إنجاز، كتلة مبلغ، شاراتٌ ثم حالة ────────
        card = await pg.evaluate("""()=>{const c=document.querySelector('.bk');
          const chips=[...c.querySelector('.chips').children].map(e=>e.className.split(' ')[0]);
          return {tick: !!c.querySelector('.tick'),
                  main: !!c.querySelector('.bk-main'),
                  nested: !!c.querySelector('button button'),
                  money: c.querySelector('.money .t')?.textContent.trim(),
                  rest:  c.querySelector('.money .r')?.textContent.trim(),
                  first: chips[0], last: chips[chips.length-1],
                  metaParts:(c.querySelector('.who .meta')?.textContent||'').split('·').length};}""")
        rec("لكل بطاقة زرّ إنجاز", card["tick"], "")
        rec("لا زرّ داخل زرّ", card["nested"] is False, "")
        rec("المبلغ كتلةٌ في طرف البطاقة", card["money"] and card["rest"], f"{card['money']} / {card['rest']}")
        rec("الشارات قبل الحالة كالنموذج", card["first"] == "svcb", str(card["first"]))
        rec("سطر الوصف ثلاثة أجزاء لا يلتفّ", card["metaParts"] == 3, f"أجزاء={card['metaParts']}")
        oneline = await pg.evaluate("""()=>[...document.querySelectorAll('.bk .who .meta')]
            .every(e=>e.getBoundingClientRect().height < 24)""")
        rec("ولا سطر وصفٍ يلتفّ على سطرين", oneline, str(oneline))

        ticks = await pg.evaluate("""()=>[...document.querySelectorAll('.bk')].map(c=>({
            s:[...c.classList].find(x=>x.startsWith('s-')),
            live:!!c.querySelector('button.tick'), still:!!c.querySelector('.tick.still')}))""")
        rec("المعلّق لا يعرض زرّ إنجاز يوهم",
            all((t["still"] and not t["live"]) if t["s"] == "s-pending" else True for t in ticks), str(ticks))
        rec("المؤكّد والمكتمل يعرضان الزرّ",
            all(t["live"] for t in ticks if t["s"] in ("s-confirmed", "s-done")), str(ticks))
        done = await pg.evaluate("""()=>{const c=document.querySelector('.bk.done');
          const probe=document.createElement('i'); probe.style.background='var(--ok-bg)';
          document.body.appendChild(probe);
          const okbg=getComputedStyle(probe).backgroundColor; probe.remove();
          return c?{bg:getComputedStyle(c.querySelector('.tick')).backgroundColor, okbg,
                    strike:getComputedStyle(c.querySelector('.who b .nm')).textDecorationLine}:null;}""")
        rec("المكتمل: الزرّ ممتلئ والاسم مشطوب",
            done and done["bg"] == done["okbg"] and done["strike"] == "line-through", str(done))

        # ── سؤال العربون داخل البطاقة لا في نافذة النظام ─────────────
        await pg.evaluate("""()=>{const c=[...document.querySelectorAll('.bk')]
            .find(x=>x.classList.contains('s-confirmed')); c.querySelector('button.tick').click();}""")
        await pg.wait_for_timeout(600)
        ask = await pg.evaluate("""()=>{const a=document.querySelector('.ask:not([hidden])');
          return a?{q:a.querySelector('p')?.innerText.trim(),
                    btns:[...a.querySelectorAll('.btn')].map(b=>b.textContent.trim())}:null;}""")
        rec("سؤال العربون يظهر داخل البطاقة", ask is not None, str(ask and ask["q"])[:60])
        rec("السؤال يذكر الاسم والمبلغ", ask and "باقٍ على" in ask["q"], str(ask and ask["q"])[:60])
        rec("جوابان لا واحد", ask and len(ask["btns"]) == 2, str(ask and ask["btns"]))
        await pg.screenshot(path=f"{OUT}/fit-ask.png")
        await pg.evaluate("""()=>[...document.querySelectorAll('.bk')]
            .find(x=>x.classList.contains('s-confirmed')).querySelector('button.tick').click()""")
        await pg.wait_for_timeout(400)
        rec("الضغط ثانيةً يطوي السؤال",
            await pg.evaluate("()=>!document.querySelector('.ask:not([hidden])')"))

        # ── ورقة التفاصيل: قوسٌ يتصدّرها وشارات في وسطه ─────────────
        await pg.evaluate("()=>document.querySelector('.bk-main').click()")
        await pg.wait_for_timeout(900)
        sh = await pg.evaluate("""()=>{const s=document.querySelector('#sheet.open');
          if(!s) return null; const a=s.querySelector('.arch');
          return {arch:!!a, name:a?.querySelector('h3')?.textContent.trim(),
                  badges:a?a.querySelectorAll('.svcb').length:0,
                  pill:a?!!a.querySelector('.pill'):false,
                  acts:s.querySelectorAll('.qact').length,
                  warm:getComputedStyle(s.querySelector('.sheet-body')).backgroundColor};}""")
        rec("الورقة تُفتتح بقوسٍ كالنموذج", sh and sh["arch"], str(sh and sh["name"]))
        rec("القوس يحمل شارات الخدمات", sh and sh["badges"] >= 1, f"شارات={sh and sh['badges']}")
        rec("القوس يحمل شارة الحالة", sh and sh["pill"], "")
        rec("صفّ الأفعال الثلاثة في الورقة", sh and sh["acts"] == 3, f"أفعال={sh and sh['acts']}")
        await pg.screenshot(path=f"{OUT}/fit-sheet.png")
        await pg.evaluate("()=>document.getElementById('sheetClose')?.click()")
        await pg.wait_for_timeout(500)

        # ── الأجندة: التقويم داخل بطاقة، وأيام الأسبوع فوقه ──────────
        await pg.evaluate("""()=>[...document.querySelectorAll('.tab')]
            .find(t=>t.textContent.includes('الأجندة')).click()""")
        await pg.wait_for_timeout(1100)
        cal = await pg.evaluate("""()=>{const c=document.querySelector('.cal');
          if(!c) return null; const cell=c.querySelector('.cd:not(.blank)');
          return {inCard: !!c.closest('.card'), dow:c.querySelectorAll('.dow').length,
                  square: Math.abs(cell.getBoundingClientRect().width
                                 - cell.getBoundingClientRect().height) < 2};}""")
        rec("التقويم داخل بطاقة زجاجية", cal and cal["inCard"], str(cal and cal["inCard"]))
        rec("أيام الأسبوع سبعة فوق الشبكة", cal and cal["dow"] == 7, str(cal and cal["dow"]))
        rec("خانات التقويم مربّعة كالنموذج", cal and cal["square"], str(cal and cal["square"]))

        # ── الإعدادات: مفاتيح تُقلب لا مربّعات ──────────────────────
        await pg.evaluate("""()=>[...document.querySelectorAll('.tab')]
            .find(t=>t.textContent.includes('الإعدادات')).click()""")
        await pg.wait_for_timeout(1200)
        sw = await pg.evaluate("""()=>{const t=document.querySelector('.toggle');
          if(!t) return null; const i=t.querySelector('input'), s=t.querySelector('.sw');
          const cs=getComputedStyle(i);
          const probe=document.createElement('i'); probe.style.background='var(--ok-bg)';
          document.body.appendChild(probe);
          const okbg=getComputedStyle(probe).backgroundColor; probe.remove();
          return {sw:!!s, hidden:cs.opacity==='0'||cs.position==='absolute',
                  on:i.checked, bg:getComputedStyle(s).backgroundColor, okbg,
                  panes:document.querySelectorAll('.panetab').length};}""")
        rec("الخيار مفتاحٌ يُقلب لا مربّع", sw and sw["sw"] and sw["hidden"], str(sw and sw["sw"]))
        rec("المفتاح المفعّل يخضرّ", sw and (not sw["on"] or sw["bg"] == sw["okbg"]), str(sw and sw["bg"]))
        rec("شريط أقسام الإعدادات ظاهر", sw and sw["panes"] == 4, str(sw and sw["panes"]))
        await pg.screenshot(path=f"{OUT}/fit-settings.png", full_page=True)

        # ── لا سطح شفّافٌ يختفي فوق المشهد ──────────────────────────
        ghosts = await pg.evaluate("""()=>[...document.querySelectorAll('.card,.arch,.bk,.empty:not(.qact)')]
          .map(e=>{const s=getComputedStyle(e);
            const m=s.backgroundColor.match(/rgba?\\(([^)]+)\\)/);
            const a=m? (m[1].split(',')[3]!==undefined?+m[1].split(',')[3]:1) : 1;
            return {c:e.className.split(' ')[0], a, h:Math.round(e.getBoundingClientRect().height)};})
          .filter(x=>x.a<.12 && x.h>40)""")
        rec("ولا سطحٍ شفّافٍ يبتلعه المشهد", len(ghosts) == 0, str(ghosts[:3]))

        # ══ ملاحظات المراجعة على الـ Artifact ═══════════════════════
        await pg.evaluate("""()=>[...document.querySelectorAll('.tab')]
            .find(t=>t.textContent.includes('الرئيسية')).click()""")
        await pg.wait_for_timeout(1000)

        # ١ · قائمة التواصل: عنوانٌ وزرّ إرسال، بلا مقتطف
        await pg.evaluate("()=>document.querySelector('.bk [data-msg]').click()")
        await pg.wait_for_timeout(900)
        ml = await pg.evaluate("""()=>{const rows=[...document.querySelectorAll('#sheetContent .rowline')];
          return {n:rows.length,
                  titles:rows.map(r=>r.querySelector('.t')?.textContent.trim()).filter(Boolean),
                  previews:rows.filter(r=>r.querySelector('.s')).length,
                  sends:rows.filter(r=>r.querySelector('[data-send]')).length};}""")
        rec("قائمة التواصل صفوفٌ بعناوين", ml["n"] >= 1 and ml["titles"], str(ml["titles"][:3]))
        rec("بلا مقتطفٍ تحت العنوان", ml["previews"] == 0, f"مقتطفات={ml['previews']}")
        rec("زرّ إرسال في كل صفّ", ml["sends"] == ml["n"], f"{ml['sends']}/{ml['n']}")
        await pg.evaluate("()=>document.getElementById('sheetClose').click()")
        await pg.wait_for_timeout(500)

        # ٢ · الأسطح بيضاء تحت الزجاج فلا يعبرها لون المشهد
        tint = await pg.evaluate("""()=>{const c=document.querySelector('.bk');
          const s=getComputedStyle(c);
          const probe=document.createElement('i'); probe.style.background='var(--tint)';
          document.body.appendChild(probe);
          const t=getComputedStyle(probe).backgroundColor; probe.remove();
          const a=(t.match(/[\d.]+(?=\))/)||[0])[0];
          return {img:s.backgroundImage, alpha:+a};}""")
        rec("طبقةٌ بيضاء تحت زجاج البطاقات", "gradient" in (tint["img"] or ""), tint["img"][:40])
        rec("الصبغة كثيفةٌ بما يمنع عبور اللون", tint["alpha"] >= .5, str(tint["alpha"]))

        # ٣ · الدخل: ثلاث صيغ تُختار، كلٌّ تُرسم
        seg = await pg.evaluate("()=>[...document.querySelectorAll('[data-iv]')].map(b=>b.dataset.iv)")
        rec("ثلاث صيغ لعرض الدخل", seg == ["tiles", "ring", "grid"], str(seg))
        shapes = {}
        for v, sel in (("tiles", ".stats3 .stat"), ("ring", ".ring circle"), ("grid", ".heat .hc:not(.blank)")):
            await pg.evaluate(f"""()=>document.querySelector('[data-iv="{v}"]').click()""")
            await pg.wait_for_timeout(700)
            shapes[v] = await pg.evaluate(f"()=>document.querySelectorAll('{sel}').length")
        rec("صيغة الأرقام ثلاث خانات", shapes["tiles"] == 3, str(shapes))
        rec("الحلقة تُرسم بأجزائها", shapes["ring"] >= 2, str(shapes))
        rec("الشبكة تُرسم بأيام الشهر", shapes["grid"] >= 28, str(shapes))
        bars = await pg.evaluate("""()=>{const f=document.querySelector('.bars .bar.muted .fill');
          return f?getComputedStyle(f).backgroundColor:'';}""")
        rec("أشرطة الخدمات تُرى في مسارها",
            bars and "rgba(0, 0, 0, 0)" not in bars and "255, 255, 255" not in bars, bars)

        # ٤ · محرّر الخدمة: إطارا الفيديو والصورة وضبط التموضع
        await pg.evaluate("""()=>[...document.querySelectorAll('.tab')]
            .find(t=>t.textContent.includes('الإعدادات')).click()""")
        await pg.wait_for_timeout(1000)
        await pg.evaluate("""()=>document.querySelector('[data-pane="services"]').click()""")
        await pg.wait_for_timeout(800)
        await pg.evaluate("""()=>{const r=document.querySelector('.rowline');
            r.querySelector('button,.iconbtn').click();}""")
        await pg.wait_for_timeout(1000)
        med = await pg.evaluate("""()=>({
            frames:document.querySelectorAll('#sheetContent .frame').length,
            vid:!!document.getElementById('s-vidpick'), img:!!document.getElementById('s-imgpick'),
            accVid:document.getElementById('s-vidfile')?.accept||'',
            accImg:document.getElementById('s-imgfile')?.accept||'',
            pos:document.querySelectorAll('[data-pos]').length,
            zoom:!!document.getElementById('s-zoom')})""")
        rec("إطارا الفيديو والصورة في محرّر الخدمة", med["frames"] == 2, str(med["frames"]))
        rec("زرّا الرفع موجودان", med["vid"] and med["img"], "")
        rec("الفيديو يقبل فيديو والصورة تقبل صورة",
            "video/mp4" in med["accVid"] and "image/jpeg" in med["accImg"], "")
        rec("خيارات التموضع الخمسة", med["pos"] == 5, str(med["pos"]))
        rec("مزلاج التكبير", med["zoom"], "")
        await pg.screenshot(path=f"{OUT}/fit-service-media.png", full_page=True)
        await pg.evaluate("()=>document.getElementById('sheetClose').click()")
        await pg.wait_for_timeout(400)

        # ٥ · منطقة الحذف: سطحٌ مصمت ونصٌّ أبيض يُقرأ
        await pg.evaluate("""()=>{const p=document.querySelector('[data-pane="general"]'); if(p) p.click();}""")
        await pg.wait_for_timeout(1000)
        dz = await pg.evaluate("""()=>{const z=document.querySelector('.danger-zone');
          if(!z) return null; const zs=getComputedStyle(z);
          const rgb=(c)=>c.match(/\\d+/g).slice(0,3).map(Number);
          const lum=(c)=>{const [r,g,b]=rgb(c).map(v=>{v/=255;
            return v<=0.04045? v/12.92 : Math.pow((v+0.055)/1.055,2.4)});
            return 0.2126*r+0.7152*g+0.0722*b;};
          const cr=(a,b)=>{const l=[lum(a),lum(b)].sort((x,y)=>y-x);
            return (l[0]+0.05)/(l[1]+0.05);};
          const hint=document.querySelector('.danger-zone .hint');
          const cnt=document.getElementById('pg-count');
          const go=document.getElementById('pg-go');
          const inp=document.querySelector('.danger-zone .input');
          return {solid: zs.backgroundImage === 'none' && !/rgba/.test(zs.backgroundColor),
                  blur: zs.backdropFilter === 'none' || !zs.backdropFilter,
                  hintCR: +cr(getComputedStyle(hint).color, zs.backgroundColor).toFixed(2),
                  cntCR:  +cr(getComputedStyle(cnt).color,  zs.backgroundColor).toFixed(2),
                  goCR:   +cr(getComputedStyle(go).color, getComputedStyle(go).backgroundColor).toFixed(2),
                  inpCR:  +cr(getComputedStyle(inp).color, getComputedStyle(inp).backgroundColor).toFixed(2)};}""")
        rec("منطقة الحذف سطحٌ مصمت لا غشاوة", dz and dz["solid"] and dz["blur"], str(dz and dz["solid"]))
        rec("شرحها يُقرأ (تباين ≥ ٤٫٥)", dz and dz["hintCR"] >= 4.5, f"{dz and dz['hintCR']}:1")
        rec("سطر العدد يُقرأ", dz and dz["cntCR"] >= 4.5, f"{dz and dz['cntCR']}:1")
        rec("زرّ الحذف أعلى تباينٍ في اللوحة", dz and dz["goCR"] >= 6, f"{dz and dz['goCR']}:1")
        rec("حقولها فاتحةٌ فيُقرأ ما يُكتب", dz and dz["inpCR"] >= 7, f"{dz and dz['inpCR']}:1")
        await pg.screenshot(path=f"{OUT}/fit-danger.png")

        # ٦ · الورقة على المشهد: الصفحة تتنحّى وتعود
        await pg.evaluate("""()=>[...document.querySelectorAll('.tab')]
            .find(t=>t.textContent.includes('الرئيسية')).click()""")
        await pg.wait_for_timeout(1000)
        await pg.evaluate("()=>document.querySelector('.bk-main').click()")
        await pg.wait_for_timeout(1000)
        sc = await pg.evaluate("""()=>({on:document.body.classList.contains('sheeting'),
          shell:getComputedStyle(document.querySelector('.shell')).opacity,
          bar:getComputedStyle(document.querySelector('.appbar')).opacity,
          scrim:getComputedStyle(document.getElementById('sheet')).backgroundColor,
          blur:getComputedStyle(document.getElementById('sheet')).backdropFilter,
          scene:getComputedStyle(document.querySelector('.scene')).display})""")
        rec("الورقة تُنحّي الصفحة", sc["on"] and sc["shell"] == "0" and sc["bar"] == "0", str(sc))
        rec("بلا حجابٍ يحجب المشهد",
            "rgba(0, 0, 0, 0)" in sc["scrim"] and sc["blur"] in ("none", ""), f'{sc["scrim"]} / {sc["blur"]}')
        rec("المشهد قائمٌ خلفها", sc["scene"] != "none", sc["scene"])

        # ٧ · «تواصل» في الورقة يفتح القائمة نفسها ومعها طريق عودة
        talk = await pg.evaluate("""()=>{const e=document.querySelector('#sheetContent .qacts [data-msg]');
          return e?{tag:e.tagName, txt:e.textContent.trim()}:null;}""")
        rec("«تواصل» في الورقة زرٌّ لا رابط واتساب", talk and talk["tag"] == "BUTTON", str(talk))
        subline = await pg.evaluate("()=>document.querySelectorAll('#sheetContent .choice .s').length")
        rec("سطر «التفاصيل ورابط المتابعة» محذوف", subline == 0, str(subline))
        await pg.evaluate("()=>document.querySelector('#sheetContent .qacts [data-msg]').click()")
        await pg.wait_for_timeout(900)
        mm = await pg.evaluate("""()=>{const send=document.querySelector('.qact.send');
          const cs=send?getComputedStyle(send):null;
          return {title:document.getElementById('sheetTitle').textContent,
                  sends:document.querySelectorAll('.qact.send').length,
                  bg:cs?cs.backgroundColor:'', border:cs?cs.borderTopColor:'',
                  back:!!document.getElementById('msg-back')};}""")
        rec("يفتح قائمة التواصل نفسها", "تواصل مع" in mm["title"], mm["title"])
        rec("ومعها طريق عودة إلى التفاصيل", mm["back"], "")
        # الليل يخفض البياض قليلًا عمدًا، فيُقاس القرب من الأبيض لا مطابقته.
        chan = [int(x) for x in __import__('re').findall(r'\d+', mm["bg"])[:3]] or [0]
        rec("أزرار الإرسال بيضاء لكامل القائمة",
            mm["sends"] >= 1 and min(chan) >= 240, f'{mm["sends"]} × {mm["bg"]}')
        rec("ولها إطارٌ يُرى لا يذوب في البطاقة",
            mm["border"] and "rgba(0, 0, 0, 0)" not in mm["border"], mm["border"])
        await pg.evaluate("()=>document.getElementById('msg-back').click()")
        await pg.wait_for_timeout(900)
        rec("الرجوع يُعيد ورقة التفاصيل",
            "تواصل مع" not in (await pg.inner_text("#sheetTitle")), await pg.inner_text("#sheetTitle"))
        await pg.evaluate("()=>document.getElementById('sheetClose').click()")
        await pg.wait_for_timeout(800)
        back = await pg.evaluate("""()=>({on:document.body.classList.contains('sheeting'),
          shell:getComputedStyle(document.querySelector('.shell')).opacity,
          cards:document.querySelectorAll('.bk').length})""")
        rec("الإغلاق يُرجع قائمة الحجوزات",
            (not back["on"]) and back["shell"] == "1" and back["cards"] >= 1, str(back))

        # ٨ · مصدر الحجز: شارةٌ حاضرة دائمًا وفلترٌ ثالث
        await pg.evaluate("""()=>[...document.querySelectorAll('.tab')]
            .find(t=>t.textContent.includes('الرئيسية')).click()""")
        await pg.wait_for_timeout(1000)
        src = await pg.evaluate("""()=>[...document.querySelectorAll('.bk')].map(c=>{
            const s=c.querySelector('.who b .srcmark');
            return s? {kind:[...s.classList].find(x=>x==='client'||x==='admin'),
                       txt:(s.getAttribute('title')||'').trim(), svg:!!s.querySelector('svg'),
                       beside: s.previousElementSibling?.className === 'nm'} : null;})""")
        rec("كل بطاقة تحمل علامة المصدر", src and all(x for x in src), f"{len([x for x in src if x])}/{len(src)}")
        rec("العلامة بجانب الاسم لا في صفّ الشارات",
            all(x and x["beside"] for x in src)
            and (await pg.evaluate("()=>document.querySelectorAll('.bk .chips .pill.src').length")) == 0, "")
        rec("ولكلٍّ أيقونتها", all(x and x["svg"] for x in src), "")
        isz = await pg.evaluate("()=>{const g=document.querySelector('.who b .srcmark svg');"
                                "return g? Math.round(g.getBoundingClientRect().width) : 0;}")
        rec("العلامة تُرى من غير تحديق", isz >= 16, f"{isz}px")
        kinds = {x["kind"] for x in src if x}
        rec("الحالتان معروضتان لا واحدة", kinds <= {"client", "admin"} and kinds, str(kinds))
        labels = {x["txt"] for x in src if x}
        rec("النصّ يقول أيّهما", labels <= {"من الرابط", "يدوي"}, str(labels))

        await pg.evaluate("""()=>[...document.querySelectorAll('.tab')]
            .find(t=>t.textContent.includes('الحجوزات')).click()""")
        await pg.wait_for_timeout(1100)
        row = await pg.evaluate("""()=>[...document.querySelectorAll('[data-sr]')]
            .map(b=>({id:b.dataset.sr, txt:b.textContent.replace(/\\s+/g,' ').trim(),
                      n:+(b.querySelector('i')?.textContent||0), svg:!!b.querySelector('svg')}))""")
        rec("صفّ فلتر المصدر ثلاثة خيارات", len(row) == 3, str([r["id"] for r in row]))
        rec("ومعها عدّاد لكلٍّ", all("i" or True for r in row) and row[0]["n"] == row[1]["n"] + row[2]["n"],
            f'{row[0]["n"]} = {row[1]["n"]} + {row[2]["n"]}')
        rec("أيقونة مع كل مصدر", row[1]["svg"] and row[2]["svg"], "")

        # الفلتر يعزل فعلًا — تُجرّب الحالة التي فيها نتائج
        await pg.evaluate("""()=>[...document.querySelectorAll('[data-st]')]
            .find(b=>/الكل/.test(b.textContent))?.click()""")
        await pg.wait_for_timeout(800)
        iso = {}
        for sid in ("client", "admin"):
            await pg.evaluate(f"""()=>document.querySelector('[data-sr="{sid}"]').click()""")
            await pg.wait_for_timeout(700)
            iso[sid] = await pg.evaluate("""()=>[...new Set([...document.querySelectorAll('.bk .srcmark')]
                .map(e=>[...e.classList].find(x=>x==='client'||x==='admin')))]""")
        rec("«من الرابط» لا يعرض إلا حجوزات الرابط", iso["client"] in ([], ["client"]), str(iso["client"]))
        rec("«يدوي» لا يعرض إلا اليدويّة", iso["admin"] in ([], ["admin"]), str(iso["admin"]))
        await pg.evaluate("""()=>document.querySelector('[data-sr="all"]').click()""")
        await pg.wait_for_timeout(600)
        await pg.screenshot(path=f"{OUT}/fit-source.png", full_page=True)

        # ٩ · الشاشة الأولى لا تحمل إلا ما فيه خبر
        await pg.evaluate("""()=>[...document.querySelectorAll('.tab')]
            .find(t=>t.textContent.includes('الرئيسية')).click()""")
        await pg.wait_for_timeout(1000)
        empty_probe = await pg.evaluate("""()=>{
          const view = document.getElementById('view');
          const heads = [...view.querySelectorAll('.sec-head h2')].map(h=>h.textContent.trim());
          return {heads,
                  arch: view.querySelectorAll('.arch').length,
                  empty: view.querySelectorAll('.empty:not(.qact)').length,
                  zeroStat: [...view.querySelectorAll('.stats .stat .v')]
                    .map(v=>v.textContent.trim()).filter(t=>/^0(\\s|$)/.test(t)).length};}""")
        rec("لا قوسَ «لا طلبات معلّقة» ولا صندوقَ «لا مواعيد»",
            empty_probe["arch"] == 0 and empty_probe["empty"] == 0, str(empty_probe))
        rec("ولا بطاقةَ رقمها صفر", empty_probe["zeroStat"] == 0, str(empty_probe["zeroStat"]))
        rec("«طلبات بانتظارك» لا تظهر إلا ومعها طلب",
            ("طلبات بانتظارك" in empty_probe["heads"])
            == (await pg.evaluate("()=>[...document.querySelectorAll('.bk.s-pending')].length > 0")),
            str(empty_probe["heads"]))
        qk = await pg.evaluate("""()=>[...document.querySelectorAll('#view .stats')]
            .flatMap(s=>[...s.querySelectorAll('.k')].map(k=>k.textContent.trim()))""")
        rec("رقما «نظرة سريعة» عن المدّة نفسها",
            ("المحصّل هذا الشهر" in qk) == ("حجوزات هذا الشهر" in qk), str(qk))

        # ١٠ · الأفعال الثلاثة بمقاسٍ واحد، والعدد المنتظِر ينبض
        rows = await pg.evaluate("""()=>[...document.querySelectorAll('#view .qacts')].map(r=>
          [...r.children].map(x=>{const b=x.getBoundingClientRect();
            return {tag:x.tagName, w:Math.round(b.width), h:Math.round(b.height),
                    empty:x.classList.contains('empty')};}))""")
        flat = [c for r in rows for c in r]
        rec("صفوف الأفعال موجودة", len(rows) >= 1 and all(len(r) == 3 for r in rows), f"صفوف={len(rows)}")
        same = all(abs(c["w"] - r[0]["w"]) <= 1 and abs(c["h"] - r[0]["h"]) <= 1
                   for r in rows for c in r)
        rec("الثلاثة بعرضٍ وارتفاعٍ واحد", same,
            str([[f'{c["tag"][0]}:{c["w"]}x{c["h"]}' for c in r] for r in rows[:2]]))
        empties = [c for c in flat if c["empty"]]
        rec("و«بلا موقع» منها لا أصغر",
            all(abs(e["h"] - flat[0]["h"]) <= 1 and abs(e["w"] - flat[0]["w"]) <= 1 for e in empties),
            str(empties[:2]) if empties else "لا حالة بلا موقع في هذه البيانات")

        gb = await pg.evaluate("""()=>{const b=document.querySelector('.greet p b');
          if(!b) return null; const s=getComputedStyle(b), p=getComputedStyle(b.parentElement);
          const probe=document.createElement('i'); probe.style.color='var(--accent)';
          document.body.appendChild(probe);
          const acc=getComputedStyle(probe).color; probe.remove();
          return {live:b.classList.contains('live'), fs:parseFloat(s.fontSize),
                  pfs:parseFloat(p.fontSize), color:s.color, acc, anim:s.animationName,
                  pending:document.querySelectorAll('.bk.s-pending').length};}""")
        rec("العدد في التحيّة أكبر من سطره", gb and gb["fs"] > gb["pfs"] + 1.5,
            f'{gb and gb["fs"]} > {gb and gb["pfs"]}')
        rec("وبلون الهوية", gb and gb["color"] == gb["acc"], str(gb and gb["color"]))
        rec("ينبض متى كان ثمّة طلبٌ ينتظر",
            gb and (gb["anim"] == "greet-pulse") == (gb["pending"] > 0 and gb["live"]),
            f'{gb and gb["anim"]} · معلّق={gb and gb["pending"]}')

        # ١١ · الفراشة زرًّا: ثابتةٌ تُلمَس، لا زينةً تسرح
        await pg.evaluate("()=>[...document.querySelectorAll('.tab')]"
                          ".find(t=>t.textContent.includes('الرئيسية')).click()")
        await pg.wait_for_timeout(1000)
        bf = await pg.evaluate("""()=>{const e=document.querySelector('.bfly');
          if(!e) return null; const s=getComputedStyle(e); const r=e.getBoundingClientRect();
          return {tag:e.tagName, pe:s.pointerEvents, aria:e.getAttribute('aria-label'),
                  z:+s.zIndex, pos:s.position,
                  inView: r.left > -30 && r.right < innerWidth + 30,
                  besideName: (()=>{const h=document.querySelector('.greet h1');
                    return !!h && r.right <= h.getBoundingClientRect().left + 1;})(),
                  centred: (()=>{const a=document.querySelector('.greet-act');
                    if(!a) return null; const ar=a.getBoundingClientRect();
                    return {dx: Math.abs((r.left+r.right)/2 - (ar.left+ar.right)/2),
                            dy: Math.abs((r.top+r.bottom)/2 - (ar.top+ar.bottom)/2)};})(),
                  w:Math.round(r.width), h:Math.round(r.height)};}""")
        rec("الفراشة موجودة", bf is not None, "")
        rec("زرٌّ يُلمَس ويُقرأ اسمُه", bf and bf["tag"] == "BUTTON"
            and bf["pe"] != "none" and bf["aria"] == "إضافة حجز", str(bf and bf["aria"]))
        rec("تبقى داخل الشاشة", bf and bf["inView"], str(bf and bf["inView"]))
        rec("وداخل بطاقة التحيّة لا فوق الصفحة",
            bf and bf["pos"] == "static", str(bf and bf["pos"]))
        rec("مساحة لمسٍ لا تقلّ عن ٤٦", bf and bf["w"] >= 46 and bf["h"] >= 46,
            f'{bf and bf["w"]}×{bf and bf["h"]}')
        rec("بجانب اسمها لا فوقه", bf and bf["besideName"], str(bf and bf["besideName"]))
        rec("متوسّطًا الفراغ الباقي طولًا وعرضًا",
            bf and bf["centred"] and bf["centred"]["dx"] <= 1 and bf["centred"]["dy"] <= 1,
            str(bf and bf["centred"]))
        # لا تتنقّل: التمرير لا يزحزحها
        p0 = await pg.evaluate("()=>document.querySelector('.bfly').getBoundingClientRect().top")
        await pg.evaluate("()=>scrollTo(0, 380)"); await pg.wait_for_timeout(1300)
        p1 = await pg.evaluate("()=>document.querySelector('.bfly').getBoundingClientRect().top")
        await pg.evaluate("()=>scrollTo(0, 0)"); await pg.wait_for_timeout(400)
        rec("تمضي مع الصفحة ولا تتبع العين", p1 < p0 - 100, f"{round(p0)} → {round(p1)}")

        # القرص الساكن: أيقونة الخدمة في وسطه وأكبر من علامة الإنجاز
        tk = await pg.evaluate("""()=>{const t=document.querySelector('.tick.still');
          if(!t) return null; const g=t.querySelector('svg');
          const tr=t.getBoundingClientRect(), gr=g.getBoundingClientRect();
          return {circle:Math.round(tr.width), icon:Math.round(gr.width),
                  dx:Math.round((gr.left+gr.width/2)-(tr.left+tr.width/2)),
                  dy:Math.round((gr.top+gr.height/2)-(tr.top+tr.height/2))};}""")
        rec("أيقونة القرص في منتصفه تمامًا",
            tk and abs(tk["dx"]) <= 1 and abs(tk["dy"]) <= 1, str(tk))
        rec("وأكبر ممّا كانت", tk and tk["icon"] >= 26, f'{tk and tk["icon"]}px داخل {tk and tk["circle"]}')

        # ١٢ · بيت الغزل يفتتح اللوحة
        by = await pg.evaluate("""()=>{const e=document.querySelector('.greet .bayt');
          if(!e) return null;
          return {v:[...e.querySelectorAll(':scope > span')].map(x=>x.textContent.trim()),
                  poet:e.querySelector('b')?.textContent.trim(),
                  kick:!!document.querySelector('.greet .kick'),
                  h1:document.querySelector('.greet h1')?.textContent.trim()};}""")
        rec("البيت يتصدّر التحيّة", by and len(by["v"]) == 2 and all(by["v"]), str(by and by["v"]))
        rec("ومعه اسم الشاعر", by and by["poet"], str(by and by["poet"]))
        cp = await pg.evaluate("""()=>{const b=document.getElementById('baytCopy');
          return b? {txt:b.textContent.trim(), svg:!!b.querySelector('svg'),
                     aria:b.getAttribute('aria-label')} : null;}""")
        rec("زرّ نسخ البيت موجود", cp and cp["svg"] and cp["aria"], str(cp and cp["aria"]))
        rec("أيقونةٌ بلا كلمة", cp and cp["txt"] == "", f'نصّ={cp and cp["txt"]!r}')
        pos = await pg.evaluate("""()=>{const b=document.getElementById('baytCopy');
          const g=b.closest('.greet'); const br=b.getBoundingClientRect(), gr=g.getBoundingClientRect();
          const v=document.querySelector('.greet .bayt span');
          return {top:Math.round(br.top-gr.top), inCorner:(br.top-gr.top)<26,
                  clearOfText: v ? br.bottom <= v.getBoundingClientRect().bottom + 2 : true,
                  overlaps: v ? !(br.left > v.getBoundingClientRect().right ||
                                  br.right < v.getBoundingClientRect().left) &&
                                !(br.top > v.getBoundingClientRect().bottom ||
                                  br.bottom < v.getBoundingClientRect().top) : false};}""")
        rec("في ركن البطاقة العلويّ", pos and pos["inCorner"], f'{pos and pos["top"]}px من الأعلى')
        await pg.click("#baytCopy"); await pg.wait_for_timeout(700)
        clip = await pg.evaluate("()=>navigator.clipboard.readText().catch(()=>'')")
        rec("ينسخ الشطرين", clip and by["v"][0] in clip and by["v"][1] in clip, clip[:24])
        rec("بتشكيل واتساب (نجمتان للعريض)",
            clip and clip.startswith("*") and f'*{by["v"][0]}*' in clip, "")
        rec("واسم الشاعر مائلًا", clip and f'_{by["poet"]}_' in clip, "")
        rec("بلا اسمٍ ولا مهنة — البيت والشاعر فقط",
            clip and "MAKEUP ARTIST" not in clip and "\u2726" not in clip
            and "\u2014\u2014" not in clip, repr(clip[-28:]))
        rec("وينتهي عند اسم الشاعر", clip and clip.rstrip().endswith(f'_{by["poet"]}_'),
            repr(clip.rstrip()[-20:]))
        rec("والزرّ يقول إنّه نسخ",
            await pg.evaluate("()=>document.getElementById('baytCopy').classList.contains('done')"), "")
        tst = await pg.evaluate("()=>document.querySelector('.toast')?.textContent.trim()||''")
        rec("والرسالة: نُسخ بيت الشعر — بلا زيادة", tst == "نُسخ بيت الشعر", repr(tst))
        rec("والتحيّة الزمنيّة باقية تحته", by and "،" in (by["h1"] or ""), str(by and by["h1"]))
        # الشعراء كلّهم أقدم من قرون: لا حقوق على أبياتهم.
        OLD = {"امرؤ القيس","الأعشى","عنترة بن شدّاد","قيس بن المُلوَّح","جميل بُثينة",
               "كُثيِّر عزّة","عمر بن أبي ربيعة","ذو الرُّمّة","الأحوص الأنصاري",
               "أبو صخر الهذلي","قيس بن ذريح","بشّار بن بُرد","المتنبّي",
               "الشريف الرضيّ","ابن الفارض","ابن سهل الأندلسي"}
        # ما يُفتَتَح به يومُها لا يحمل فِراقًا ولا عِتابًا ولا حزنًا.
        DARK = ["فراق","فارقت","هجر","الهجرِ","عتاب","عاتب","بكى","بكاء","دمع","الدموع",
                "أموت","الموتُ","موتي","مِتُّ","قتيل","قاتل","مقتل","دمي","حزن","الأسى",
                "شكوى","أشكو","سقم","مريض","وحشة","جفا","جفاء","صدَّ عنّي","نأى","البُعد",
                "أرَق","سهر","الوشاة","عذاب","لوعة","حسرة","ندم","يتيم","ثكل"]
        rec("الشاعر من الأقدمين لا المحدثين", by and by["poet"] in OLD, str(by and by["poet"]))
        # الديوان كلّه، لا البيت المعروض وحده — يُقرأ من المصدر لأنّ المصفوفة داخل وحدة.
        div = ghazal_from_source()
        rec("الديوان أربعون بيتًا فأكثر", div["n"] >= 40, f'{div["n"]} بيتًا')
        rec("من عشرة شعراء فأكثر", len(div["poets"]) >= 10, f'{len(div["poets"])} شاعرًا')
        rec("كلّ الشعراء من الأقدمين", not (set(div["poets"]) - OLD),
            "، ".join(sorted(set(div["poets"]) - OLD)))
        gloom = [f'{a[:22]}… ({w})' for a, b, _p in div["pairs"]
                 for w in DARK if w in a or w in b]
        rec("لا فِراق ولا عِتاب ولا حزن في الديوان", not gloom, " · ".join(gloom[:3]))
        rec("لا بيت مكرّر", div["dup"] == 0, f'مكرّر={div["dup"]}')
        rec("كلّ بيتٍ شطران وشاعر", div["shape"], div["bad"])
        # لا يتبدّل البيت تحت العين: إعادة الرسم لا تغيّره.
        before = by["v"][0]
        await pg.evaluate("()=>[...document.querySelectorAll('.tab')]"
                          ".find(t=>t.textContent.includes('الأجندة')).click()")
        await pg.wait_for_timeout(900)
        await pg.evaluate("()=>[...document.querySelectorAll('.tab')]"
                          ".find(t=>t.textContent.includes('الرئيسية')).click()")
        await pg.wait_for_timeout(900)
        after = await pg.evaluate("()=>document.querySelector('.greet .bayt span')?.textContent.trim()")
        rec("ولا يتبدّل بين رسمةٍ وأخرى", before == after, f"{before[:18]} == {after[:18] if after else None}")

        rec("بلا أخطاء", len(errs) == 0, "; ".join(errs[:3]))
        await ctx.close(); await b.close()

asyncio.run(main())
print(f"\n=== {ok}/{ok+fail} passed ===")
