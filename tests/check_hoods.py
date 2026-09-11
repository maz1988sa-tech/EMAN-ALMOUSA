# -*- coding: utf-8 -*-
"""اشتراطات الأحياء — الشاشة عند صاحبة العمل، والنافذة عند العميلة.

الخطر هنا ليس عطبًا يُرى بل حكمًا يُخطئ: موقعٌ مرفوض يمرّ، أو رسومٌ
تدخل العربون فيختلف المطلوب تحويله عمّا يفحصه حارس الإيصال، أو رابطٌ
مختصر يُقبل صامتًا ثمّ يُرفض الحجز في آخر خطوة بلا سبب.

فيُقاس ما تراه العميلة فعلًا: النافذة، ونصُّها، والزرّ المقفل، والسطر
الذي يظهر في الملخّص، والعربون قبل الرسوم وبعدها.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as _H
import asyncio, os, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright

ROOT = str(_H.ROOT)

class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
MOCK = open(os.path.join(ROOT, "dev/mock-supabase.js"), encoding="utf-8").read()

R = []
def Number_(v):
    try: return float(v)
    except Exception: return None

def rec(n, ok, note=""):
    R.append((n, ok)); print(("PASS " if ok else "FAIL ") + n + ((" — " + note) if note else ""))

LONG = "https://www.google.com/maps/place/x/@24.5742,46.7101,15z"
SHORT = "https://maps.app.goo.gl/8kQmR3vX2ZpL9nT7A"

async def fill_form(pg, url=LONG):
    await pg.evaluate("()=>window.__pick(0,1)"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>window.__sheet()"); await pg.wait_for_timeout(600)
    await pg.fill("#nm", "نورة التجربة")
    await pg.fill("#ph", "0501234567")
    await pg.fill("#locTxt", "حي الشفا، الرياض")
    await pg.fill("#loc", url)
    await pg.wait_for_timeout(1400)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**_H.CHROME, args=["--no-sandbox"])

        # ══ صفحة العميلة ══════════════════════════════════════════════
        for kind, loc, want in (
            ('ok',        {"state": "ok", "checked": True, "district": "حي العليا"}, 'open=False'),
            ('condition', {"state": "condition", "checked": True, "district": "حي المروج",
                           "fee": 150, "message": "رسوم مواصلات لهذا الحي."}, 'open=True'),
            ('reject',    {"state": "reject", "checked": True, "district": "حي عكاظ",
                           "message": "لا نستقبل حجوزات في هذا الحي."}, 'open=True'),
            ('blocked',   {"state": "blocked", "checked": True, "district": "حي الشفا",
                           "min_people": 2, "message": "يتطلّب شخصين فأكثر."}, 'open=True'),
        ):
            ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                      has_touch=True, is_mobile=True, device_scale_factor=2)
            await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
                r.fulfill(content_type="application/javascript", body=MOCK)))
            pg = await ctx.new_page()
            await pg.add_init_script(
                "window.__SETTINGS_PATCH__={loc_check_enabled:true};"
                "window.__LOC__=" + str(loc).replace("'", '"').replace("True", "true") + ";")
            await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
            await fill_form(pg)

            st = await pg.evaluate("""()=>{
              const m=document.getElementById('locModal');
              return {open:m.classList.contains('open'),
                      title:(document.getElementById('locModalTitle').textContent||'').trim(),
                      note:(document.getElementById('locModalNote').textContent||'').trim(),
                      blocked:document.getElementById('toPay').disabled,
                      fee:(window.__state().loc||{}).fee||0,
                      feeRow:!document.getElementById('rcFeeRow').hidden,
                      total:(document.getElementById('rcDep').textContent||'').trim(),
                      okLine:!document.getElementById('locOk').hidden,
                      okTxt:(document.getElementById('locOkTxt').textContent||'').trim(),
                      sent:(window.__LOCCHK||[]).length};}""")

            if kind == 'ok':
                rec("موقعٌ بلا شرط: لا نافذة ولا تنبيه", not st["open"], str(st["open"]))
                rec("ولا يُقفل الزرّ", not st["blocked"])
                rec("ولا يظهر سطر رسوم", not st["feeRow"])
                # الصمتُ عند السليم كان يُقرأ «لم يُفحص» — فسطرٌ يقول إنّه فُحص.
                rec("لكنّ سطرًا يقول إنّ الموقع فُحص وقُبل",
                    st["okLine"] and "حي العليا" in st["okTxt"], st["okTxt"][:60])
            elif kind == 'condition':
                rec("شرطٌ برسوم: تظهر النافذة بنصّها", st["open"] and "مواصلات" in st["note"],
                    st["note"][:60])
                rec("والرسوم تدخل الإجمالي سطرًا مستقلًّا", st["feeRow"] and st["fee"] == 150,
                    f"سطر={st['feeRow']} رسوم={st['fee']}")
                rec("ولا يُقفل الزرّ — شرطٌ لا رفض", not st["blocked"])
                rec("والسطر يبقى بعد النافذة ويذكر الرسوم",
                    st["okLine"] and "حي المروج" in st["okTxt"] and "150" in st["okTxt"],
                    st["okTxt"][:70])
            elif kind == 'reject':
                rec("موقعٌ مرفوض: النافذة تقول السبب",
                    st["open"] and "لا نستقبل" in st["note"], st["note"][:60])
                rec("والزرّ يُقفل قبل ذكر أيّ مبلغ", st["blocked"])
                rec("ولا يظهر سطرُ القبول على موقعٍ مرفوض", not st["okLine"])
            else:
                rec("عددٌ أقلّ من الحدّ: يُمنع ويُقال السبب",
                    st["open"] and st["blocked"] and "شخصين" in st["note"], st["note"][:60])

            rec(f"[{kind}] الإحداثيّتان أُرسلتا للقاعدة", st["sent"] >= 1, f"نداءات={st['sent']}")
            await ctx.close()

        # ══ حدٌّ مستوفًى: لا نافذة ولا إزعاج ═══════════════════════════
        # ثلاثةٌ وعشرون حيًّا حكمُها «شخصان فأكثر»، فكانت كلُّ عميلةٍ
        # فيها ترى نافذةَ شرطٍ وقد استوفته. والمنع قائمٌ قبله.
        ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.add_init_script(
            "window.__SETTINGS_PATCH__={loc_check_enabled:true};"
            "window.__LOC__={state:'ok',checked:true,district:'حي الشفا',min_people:2};")
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
        await fill_form(pg)
        st = await pg.evaluate("""()=>({
            open:document.getElementById('locModal').classList.contains('open'),
            blocked:document.getElementById('toPay').disabled,
            okLine:!document.getElementById('locOk').hidden,
            okTxt:(document.getElementById('locOkTxt').textContent||'').trim()})""")
        rec("حدٌّ مستوفًى: لا نافذة ولا قفل",
            not st["open"] and not st["blocked"], str(st))
        rec("ويبقى السطر الأخضر باسم الحيّ",
            st["okLine"] and "الشفا" in st["okTxt"], st["okTxt"][:50])
        await ctx.close()

        # ══ تسعيرةٌ خاصّة: تُعرض كما ستُحسب ══════════════════════════
        # `create_booking` تحسب من سعر المجموعة. فلو عرضت الصفحةُ السعر
        # المعتاد رأت العميلة رقمًا وحُوسبت بغيره — والعروس في العمارية
        # ٢٣٠٠ لا ٢٠٠٠.
        ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.add_init_script("window.__SETTINGS_PATCH__={loc_check_enabled:true};")
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
        sid = await pg.evaluate("()=>((window.__state().services||[])[0]||{}).id")
        base = await pg.evaluate("()=>Number(((window.__state().services||[])[0]||{}).price)")
        await pg.evaluate("(id)=>{window.__LOC__={state:'condition',checked:true,"
                          "district:'العمارية',fee:0,no_group_discount:true,"
                          "prices:[{service_id:id,price:2300}],"
                          "message:'تسعيرةٌ خاصّة.'};"
                          "}", sid)
        await pg.evaluate("()=>window.__pick(0,1)"); await pg.wait_for_timeout(400)
        await pg.evaluate("()=>window.__sheet()"); await pg.wait_for_timeout(600)
        await pg.fill("#nm", "نورة"); await pg.fill("#ph", "0501234567")
        await pg.fill("#locTxt", "العمارية"); await pg.fill("#loc", LONG)
        await pg.wait_for_timeout(1500)
        m = await pg.evaluate("""()=>({cart:(document.getElementById('sumLines')||{}).innerText||'',
            total:(document.getElementById('total1')||{}).innerText||''})""")
        rec("التسعيرة الخاصّة تُعرض في السلّة لا السعر المعتاد",
            "2,300" in m["cart"] or "2300" in m["cart"].replace(",", ""),
            f"base={base} · " + (m["cart"] + " ⟨" + m["total"] + "⟩").replace("\n", " | ")[:100])
        await ctx.close()

        # ══ الحكم السادس: تُقبل وحدها، والرسوم بندٌ باسم الحيّ ═════════
        # عروسٌ واحدة في العمارية: الحدُّ شخصان، والاستثناء يمرّرها ومعه
        # ٣٠٠. والمبلغ يُعرض سطرًا باسمه لا يُضاف صامتًا إلى الإجمالي —
        # وإلّا قفز الرقم فلا تعرف العميلة من أين جاء الفرق.
        ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.add_init_script(
            "window.__SETTINGS_PATCH__={loc_check_enabled:true};"
            "window.__LOC__={state:'condition',checked:true,district:'العمارية',"
            "fee:300,svc_fee:300,solo:true,min_people:2,prices:[],"
            "message:'ميك اب عروس: رسوم إضافية 300 ر.س في هذا الموقع — بندٌ مستقلّ يُدفع يوم الموعد ولا يدخل العربون.'};")
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
        base = await pg.evaluate("()=>Number(((window.__state().services||[])[0]||{}).price)")
        await fill_form(pg)
        m = await pg.evaluate("""()=>({
            modal:(document.getElementById('locModal')||{}).innerText||'',
            open:(document.getElementById('locModal')||{classList:{contains:()=>false}})
                   .classList.contains('open'),
            cart:(document.getElementById('sumLines')||{}).innerText||'',
            total:(document.getElementById('total1')||{}).innerText||'',
            feeRow:!document.getElementById('rcFeeRow').hidden,
            feeLbl:(document.getElementById('rcFeeLbl')||{}).innerText||'',
            btn:!!document.getElementById('toPay') && document.getElementById('toPay').disabled,
            sent:(window.__LOCCHK||[]).slice(-1)})""")
        # الرسالة تُسمّي الخدمة والمبلغ. «أسعار الخدمات في هذا الموقع
        # تختلف» جملةٌ صحيحة لا تقول شيئًا — وهي ما رآه صاحب المشروع.
        rec("العروس الواحدة: النافذة تسمّي الخدمة والمبلغ",
            m["open"] and "300" in m["modal"] and "ميك اب عروس" in m["modal"],
            m["modal"].replace("\n", " ")[:110])
        rec("ولا تُذيَّل بجملةٍ تكرّر ما قالته",
            m["modal"].count("بندٌ مستقلّ") <= 1,
            m["modal"].replace("\n", " ")[:110])
        rec("ولا تُقفل الزرّ — الاستثناء قبولٌ لا منع", not m["btn"])
        cart = m["cart"].replace(",", "")
        rec("والرسوم بندٌ مستقلٌّ باسم الحيّ في الملخّص",
            "رسوم العمارية" in m["cart"] and "300" in cart,
            m["cart"].replace("\n", " | ")[:110])
        rec("والإجمالي سعرُ الخدمة زائدَ الرسوم",
            str(int(base + 300)) in m["total"].replace(",", ""),
            f"base={base} · {m['total']}")
        rec("ولوحة المراجعة تسمّيه كذلك",
            m["feeRow"] and m["feeLbl"].strip() == "رسوم العمارية", m["feeLbl"])
        # الإجمالي وحده كان يقول ٢٣٠٠ ولا يقول من أين — فصار سطرُ الخدمات
        # يحمل قيمتها. وسطرٌ جديد كان يُطيل اللوحة فلا تكتمل على ٣٦٠.
        rc = await pg.evaluate("()=>({svc:(document.getElementById('rcSvc')||{}).innerText||'',"
            "dep:(document.getElementById('rcDep')||{}).innerText||''})")
        rec("ولوحة المراجعة تفصل قيمة الخدمات عن الرسوم",
            str(int(base)) in rc["svc"].replace(",", "")
            and str(int(base + 300)) in rc["dep"].replace(",", ""),
            f"{rc['svc']} + 300 = {rc['dep']}")
        rec("والفحص يرسل الخدمات — الرسم حكمُ خدمةٍ لا حكمُ عدد",
            bool(m["sent"]) and len(m["sent"][0].get("p_service_ids") or []) == 1,
            str(m["sent"])[:110])
        await ctx.close()

        # ══ الثغرة: فحصٌ بشخصين ثمّ يُنقَص العدد ═══════════════════════
        # تفحص بخدمتين فيُفتح الزرّ، ثمّ ترجع فتجعلها واحدة، فتمضي على
        # حكمٍ لم يعد يخصّها — حتى تُرفض عند الإرسال وقد حوّلت العربون.
        ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.add_init_script(
            "window.__SETTINGS_PATCH__={loc_check_enabled:true};"
            "window.__LOC__={state:'ok',checked:true,district:'حي الشفا',min_people:2};")
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
        await pg.evaluate("()=>window.__pick(0,2)"); await pg.wait_for_timeout(400)
        await pg.evaluate("()=>window.__sheet()"); await pg.wait_for_timeout(600)
        await pg.fill("#nm", "نورة التجربة")
        await pg.fill("#ph", "0501234567")
        await pg.fill("#locTxt", "حي الشفا، الرياض")
        await pg.fill("#loc", LONG)
        await pg.wait_for_timeout(1500)
        a = await pg.evaluate("""()=>({open:!document.getElementById('toPay').disabled,
            loc:!!window.__state().loc})""")
        rec("بخدمتين: الفحص يمرّ ويُفتح الزرّ", a["open"] and a["loc"], str(a))

        # ترجع وتُنقص العدد — كما وصف صاحب المشروع
        await pg.evaluate("()=>window.__pick(0,1)"); await pg.wait_for_timeout(600)
        await pg.evaluate("()=>window.__sheet()"); await pg.wait_for_timeout(700)
        z = await pg.evaluate("""()=>({open:!document.getElementById('toPay').disabled,
            loc:!!window.__state().loc,
            link:(document.getElementById('loc').value||''),
            nm:(document.getElementById('nm').value||''),
            ph:(document.getElementById('ph').value||''),
            txt:(document.getElementById('locTxt').value||''),
            msg:(document.getElementById('locErr').textContent||'').trim(),
            errOn:document.getElementById('locErr').classList.contains('on')})""")
        rec("بعد التعديل: الحكم يسقط والرابط يُمسح",
            not z["loc"] and z["link"] == "", str({k: z[k] for k in ("loc", "link")}))
        rec("والزرّ يُقفل فلا تمضي على فحصٍ قديم", not z["open"], str(z["open"]))
        rec("واسمها وجوّالها وحيُّها تبقى",
            z["nm"] == "نورة التجربة" and z["ph"] and "الشفا" in z["txt"],
            f'{z["nm"]} · {z["ph"]} · {z["txt"]}')
        rec("ويُقال لها لماذا فرغ الحقل",
            z["errOn"] and "غيّرتِ الخدمات" in z["msg"], z["msg"][:60])

        # ولصقُ رابطٍ جديد يُعيد الفحص ويرفع الوسم
        await pg.fill("#loc", LONG); await pg.wait_for_timeout(1500)
        y = await pg.evaluate("""()=>({open:!document.getElementById('toPay').disabled,
            stale:!!window.__state().locStale, loc:!!window.__state().loc})""")
        rec("ورابطٌ جديد يُعيد الفحص", y["open"] and y["loc"] and not y["stale"], str(y))
        await ctx.close()

        # ══ الرابط المختصر يُردّ مبكّرًا ═══════════════════════════════
        ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.add_init_script("window.__SETTINGS_PATCH__={loc_check_enabled:true};")
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
        await fill_form(pg, SHORT)
        st = await pg.evaluate("""()=>({blocked:document.getElementById('toPay').disabled,
            msg:(document.getElementById('locErr').textContent||'').trim(),
            asked:(window.__FN||[]).filter(f=>f.name==='resolve-map').length,
            sent:(window.__LOCCHK||[]).length})""")
        rec("رابطٌ تعذّر فكُّه: يُردّ عند الحقل بسببٍ مفهوم",
            st["blocked"] and "تعذّر قراءة موقع" in st["msg"], st["msg"][:70])
        rec("وقد حاول الخادمُ فكَّه قبل الردّ", st["asked"] == 1, f"محاولات={st['asked']}")
        rec("ولا يُسأل الحكمُ بلا إحداثيات", st["sent"] == 0, f"نداءات={st['sent']}")
        await ctx.close()

        # ══ «مكانٌ محفوظ»: علاجُه غير علاج الرابط الناقص ════════════════
        # رابط مشاركة مكانٍ عند قوقل ينتهي إلى معرّفٍ لا موقع، فلا سبيل
        # إلى إحداثيّاته. وقولُ «تعذّر» وحدها يتركها تُعيد الشيء نفسه.
        ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.add_init_script(
            "window.__SETTINGS_PATCH__={loc_check_enabled:true};"
            "window.__RESOLVE__={ok:false,reason:'place_only'};")
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
        await fill_form(pg, SHORT)
        st = await pg.evaluate("""()=>({blocked:document.getElementById('toPay').disabled,
            msg:(document.getElementById('locErr').textContent||'').trim()})""")
        rec("تعذّرُ سؤال المكان: يُقال لها أعيدي أو ضعي دبّوسًا",
            st["blocked"] and "أعيدي المحاولة" in st["msg"] and "دبّوس" in st["msg"],
            st["msg"][:80])
        await ctx.close()

        # ══ والمكان المحفوظ حين يُعرف موضعه: يُفحص كأيّ نقطة ═══════════
        # هذا أكثر ما تشاركه العميلة: مكانٌ من الخرائط لا دبّوس. وكان
        # يُردّ، فيُطلب منها ما لا تعرفه.
        ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.add_init_script(
            "window.__SETTINGS_PATCH__={loc_check_enabled:true};"
            "window.__RESOLVE__={ok:true,lat:24.9233771,lng:46.4367397,via:'place'};"
            "window.__LOC__={state:'ok',checked:true,district:'حي الجبيلة'};")
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
        await fill_form(pg, SHORT)
        st = await pg.evaluate("""()=>({sent:(window.__LOCCHK||[]),
            blocked:document.getElementById('toPay').disabled,
            okLine:!document.getElementById('locOk').hidden,
            okTxt:(document.getElementById('locOkTxt').textContent||'').trim()})""")
        rec("موضعُ المكان المحفوظ يصل الحكمَ",
            len(st["sent"]) == 1 and Number_(st["sent"][0].get("p_lat")) == 24.9233771,
            str(st["sent"][:1])[:80])
        rec("ولا يُقفل الزرّ، ويُقال إنّ الموقع فُحص",
            not st["blocked"] and st["okLine"] and "الجبيلة" in st["okTxt"], st["okTxt"][:60])

        # ── مصافحة النسخة: الصفحة تُعرّف نفسها عند الحفظ ─────────────
        # القاعدة لا تُلزم بالموقع إلّا من قال إنّه يعرفه. بدونها كان
        # إشعالُ المفتاح للتجربة يردّ كلَّ حجزٍ على الصفحة المنشورة.
        n = await pg.eval_on_selector_all("#peopleFields input", "e=>e.length")
        for i in range(n):
            await pg.eval_on_selector_all(
                "#peopleFields input",
                f"(e)=>{{e[{i}].value='ضيفة {i+1}';"
                f"e[{i}].dispatchEvent(new Event('input',{{bubbles:true}}))}}")
        await pg.wait_for_timeout(300)
        await pg.click("#toPay"); await pg.wait_for_timeout(800)
        await pg.set_input_files("#rcptFile", f"{_H.SAMPLE}"); await pg.wait_for_timeout(900)
        await pg.click("#sendBooking"); await pg.wait_for_timeout(2000)
        sent = await pg.evaluate("()=>(window.__BOOKED||[])")
        rec("حمولةُ الحجز تحمل نسخة الصفحة ولحظةَ الموقع",
            bool(sent) and sent[-1].get("p_client_v") == 2
            and Number_(sent[-1].get("p_lat")) == 24.9233771,
            str({k: v for k, v in (sent[-1] or {}).items()
                 if k in ("p_client_v", "p_lat", "p_lng")}) if sent else "لا حمولة")
        await ctx.close()

        # ══ والمختصر إن فُكّ: يُفحص كما لو كان كاملًا ═══════════════════
        # هذا هو الرابط الذي يُخرجه زرّ المشاركة فعلًا. كان يُردّ دائمًا،
        # فبقي فحص الأحياء نظريًّا: الشرط مضبوط والرابط الشائع لا يُقرأ.
        ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.add_init_script(
            "window.__SETTINGS_PATCH__={loc_check_enabled:true};"
            "window.__RESOLVE__={ok:true,lat:24.7778,lng:46.7959};"
            "window.__LOC__={state:'reject',checked:true,district:'حي الخليج',"
            "message:'لا نستقبل حجوزات في هذا الحي.'};")
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
        await fill_form(pg, SHORT)
        st = await pg.evaluate("""()=>({sent:(window.__LOCCHK||[]),
            open:document.getElementById('locModal').classList.contains('open'),
            note:(document.getElementById('locModalNote').textContent||'').trim(),
            blocked:document.getElementById('toPay').disabled})""")
        rec("المختصرُ المفكوك يصل الحكمَ بإحداثيّاته",
            len(st["sent"]) == 1 and Number_(st["sent"][0].get("p_lat")) == 24.7778,
            str(st["sent"][:1])[:80])
        rec("وحكمُه يُطبَّق كأيّ رابطٍ كامل",
            st["open"] and st["blocked"] and "لا نستقبل" in st["note"], st["note"][:60])
        await ctx.close()

        # ══ سعرٌ صافٍ: الخصم يسقط في الإجمالي المعروض ══════════════════
        # الحكم الرابع وحده كان يعطي ٦٠٠ للفرد بدل ٨٠٠، لأنّ الخصم كان
        # قرارَ خدمةٍ لا قرارَ موقع.
        for nodisc, want in ((False, True), (True, False)):
            ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                      has_touch=True, is_mobile=True, device_scale_factor=2)
            await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
                r.fulfill(content_type="application/javascript", body=MOCK)))
            pg = await ctx.new_page()
            await pg.add_init_script(
                "window.__SETTINGS_PATCH__={loc_check_enabled:true};"
                "window.__LOC__={state:'condition',checked:true,district:'العمارية',"
                "fee:0,no_group_discount:" + ("true" if nodisc else "false") + ","
                "message:'سعرٌ صافٍ في هذا الموقع.'};")
            await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
            await pg.evaluate("()=>window.__pick(0,3)"); await pg.wait_for_timeout(400)
            await pg.evaluate("()=>window.__sheet()"); await pg.wait_for_timeout(600)
            await pg.fill("#nm", "نورة"); await pg.fill("#ph", "0501234567")
            await pg.fill("#locTxt", "العمارية"); await pg.fill("#loc", LONG)
            await pg.wait_for_timeout(1500)
            d = await pg.evaluate("()=>({disc:window.__disc?window.__disc():null,"
                                  "row:!document.getElementById('rcDiscRow')?.hidden})"
                                  if False else
                                  "()=>({loc:window.__state().loc})")
            got = await pg.evaluate("""()=>{const s=window.__state();
                return {nd:!!(s.loc||{}).noGroupDiscount};}""")
            rec(f"[صافٍ={nodisc}] الصفحة تقرأ حكم الخصم من الموقع",
                got["nd"] == nodisc, str(got))
            await ctx.close()

        # ══ الفحص مُطفأ: لا شيء يتغيّر ═════════════════════════════════
        ctx = await b.new_context(viewport={"width": 430, "height": 900},
                                  has_touch=True, is_mobile=True, device_scale_factor=2)
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.goto(f"http://127.0.0.1:{PORT}/index.html"); await pg.wait_for_timeout(1700)
        await fill_form(pg, SHORT)
        st = await pg.evaluate("""()=>({blocked:document.getElementById('toPay').disabled,
            sent:(window.__LOCCHK||[]).length,
            open:document.getElementById('locModal').classList.contains('open')})""")
        rec("والفحص مُطفأ: لا نداء ولا نافذة ولا منع",
            st["sent"] == 0 and not st["open"] and not st["blocked"],
            f"نداءات={st['sent']} نافذة={st['open']} مقفل={st['blocked']}")
        await ctx.close()

        # ══ لوحة صاحبة العمل ══════════════════════════════════════════
        ctx = await b.new_context(viewport={"width": 430, "height": 950},
                                  device_scale_factor=2, locale="ar-SA")
        await ctx.route("**/assets/vendor/supabase.js", lambda r: asyncio.ensure_future(
            r.fulfill(content_type="application/javascript", body=MOCK)))
        pg = await ctx.new_page()
        await pg.add_init_script("window.__MOCK_SIGNED_IN__ = true;")
        await pg.goto(f"http://127.0.0.1:{PORT}/admin.html"); await pg.wait_for_timeout(2000)
        await pg.evaluate("""()=>{const t=[...document.querySelectorAll('.tab')]
            .find(e=>e.textContent.includes('الإعدادات')); t && t.click();}""")
        await pg.wait_for_timeout(800)
        tabs = await pg.eval_on_selector_all(".panetab", "e=>e.map(x=>x.textContent.trim())")
        rec("تبويب «الأحياء» في الإعدادات", "الأحياء" in tabs, str(tabs))

        await pg.evaluate("""()=>{const b=[...document.querySelectorAll('[data-pane]')]
            .find(x=>x.dataset.pane==='hoods'); b && b.click();}""")
        await pg.wait_for_timeout(1200)
        m = await pg.evaluate("""()=>({
            groups:document.querySelectorAll('[data-gedit]').length,
            txt:(document.getElementById('h-groups').innerText||'').trim(),
            hasOn:!!document.getElementById('h-on'),
            hasOut:!!document.getElementById('o-reject'),
            hasNew:!!document.getElementById('h-new'),
            noImport:!document.getElementById('h-import')})""")
        rec("المجموعتان تظهران", m["groups"] == 2, f"عدد={m['groups']}")
        rec("وكلٌّ بحكمها ملخّصًا",
            "أطراف الرياض" in m["txt"] and "2 أشخاص فأكثر" in m["txt"] and "+150" in m["txt"],
            m["txt"].replace("\n", " | ")[:120])
        rec("والموقوفة مُعلَّمة", "موقوفة" in m["txt"])
        rec("ولا وجود لاستيراد ملفّ الحدود", m["noImport"])
        rec("ومفتاح الفحص وحكم الخارج وزرّ المجموعة الجديدة",
            m["hasOn"] and m["hasOut"] and m["hasNew"])

        # ── التنبيه والمجرِّب: تُجرَّب الشروط بلا إشعال حارسٍ على العميلات ──
        # وقع مرّةً أنّ الطريق الوحيد لتجربة شرطٍ كان إشعال المفتاح، وهو
        # مشترك بين المختبر والحيّ — فرُفض كلّ حجزٍ على الصفحة المنشورة.
        w = await pg.evaluate("""()=>{const n=document.getElementById('h-warn');
            return {shown:!!n && !n.hidden, txt:(n?n.innerText:'').trim(),
                    hasTry:!!document.getElementById('h-try-go')};}""")
        rec("تنبيهٌ يشرح أثر المفتاح قبل النشر",
            w["shown"] and "لا يمنع أحدًا" in w["txt"], w["txt"].replace("\n", " ")[:90])
        rec("ومجرِّبُ الموقع في الشاشة", w["hasTry"])

        await pg.evaluate("""()=>{
            window.__LOC__={state:'condition',checked:true,district:'حي المروج',
                            fee:150,message:'رسوم مواصلات لهذا الحي.'};
            document.getElementById('h-try').value=
              'https://www.google.com/maps/place/x/@24.5742,46.7101,15z';
            document.getElementById('h-try-go').click();}""")
        await pg.wait_for_timeout(900)
        t = await pg.evaluate("""()=>({out:(document.getElementById('h-try-out').innerText||'').trim(),
            calls:(window.__LOCCHK||[]).slice(-1)})""")
        rec("المجرِّب يعرض الحكم كما تراه العميلة",
            "حي المروج" in t["out"] and "مقبول بشرط" in t["out"] and "150" in t["out"],
            t["out"].replace("\n", " ")[:100])
        rec("ويطلب المعاينة صراحةً — لا يمرّ عبر المفتاح",
            bool(t["calls"]) and t["calls"][0].get("p_preview") is True, str(t["calls"])[:90])

        await pg.evaluate("""()=>{window.__RESOLVE__={ok:false,reason:'no_coords'};
            document.getElementById('h-try').value='https://maps.app.goo.gl/zzzz1111';
            document.getElementById('h-try-go').click();}""")
        await pg.wait_for_timeout(900)
        t2 = await pg.evaluate("()=>(document.getElementById('h-try-out').innerText||'').trim()")
        rec("ورابطٌ تعذّر فكُّه يُقال سببه لا يُترك صامتًا",
            "تعذّر قراءة موقع" in t2, t2.replace("\n", " ")[:80])

        # ── مجموعة جديدة: اختيار أحياء + حكم + تسعيرة ──────────────────
        await pg.evaluate("()=>document.getElementById('h-new').click()")
        await pg.wait_for_timeout(700)
        blocked = await pg.evaluate("""()=>{
            const rows=[...document.querySelectorAll('[data-hd]')];
            const taken=rows.find(r=>r.innerText.includes('في مجموعة أخرى'));
            return !!taken;}""")
        rec("حيٌّ في مجموعةٍ أخرى يُعلَّم قبل الاختيار لا بعد الحفظ", blocked)

        await pg.evaluate("""()=>{
            document.getElementById('g-name').value='مجموعة التجربة';
            const free=[...document.querySelectorAll('[data-hd]')]
              .filter(r=>!r.innerText.includes('في مجموعة أخرى'));
            free[0].click(); free[1] && free[1].click();
            document.getElementById('g-fee').value='200';
            const p=document.querySelector('[data-gprice]'); if(p) p.value='800';
        }""")
        await pg.wait_for_timeout(300)
        await pg.evaluate("()=>document.getElementById('g-save').click()")
        await pg.wait_for_timeout(900)
        sent = await pg.evaluate("()=>(window.__HSAVE||[])[0] || null")
        rec("المجموعة تُحفظ بأحيائها وحكمها",
            sent is not None and len(sent.get("districts") or []) >= 1
            and Number_(sent.get("fee_amount")) == 200,
            str(sent and {k: sent.get(k) for k in ("name", "districts", "fee_amount")}))
        rec("والتسعيرة الخاصة تُرسل مع المجموعة",
            sent is not None and len(sent.get("prices") or []) == 1,
            str(sent and sent.get("prices")))

        # ── الحكم الخامس: سعرٌ صافٍ بلا خصم مجموعات ───────────────────
        # العمارية ٨٠٠ للفرد لا ٦٠٠: الخصم قرارُ موقعٍ أيضًا، لا قرارُ
        # خدمةٍ وحدها. وبدونه كان الحكم الرابع يعطي ٦٠٠ صامتًا.
        await pg.evaluate("()=>document.getElementById('h-new').click()")
        await pg.wait_for_timeout(700)
        nod = await pg.evaluate("()=>!!document.getElementById('g-nodisc')")
        rec("مفتاح «سعر صافٍ» في ورقة المجموعة", nod)
        await pg.evaluate("""()=>{
            document.getElementById('g-name').value='العمارية';
            const free=[...document.querySelectorAll('[data-hd]')]
              .filter(r=>!r.innerText.includes('في مجموعة أخرى'));
            free[0] && free[0].click();
            document.getElementById('g-nodisc').checked=true;}""")
        await pg.wait_for_timeout(200)
        await pg.evaluate("()=>document.getElementById('g-save').click()")
        await pg.wait_for_timeout(900)
        saved = await pg.evaluate("()=>(window.__HSAVE||[]).slice(-1)")
        rec("ويُحفظ مع المجموعة",
            bool(saved) and saved[0].get("no_group_discount") is True,
            str(saved[:1])[:110])


        # ── الحكم السادس في اللوحة: صحُّ «تُقبل وحدها» وخانة الرسوم ────
        await pg.evaluate("()=>document.getElementById('h-new').click()")
        await pg.wait_for_timeout(700)
        has = await pg.evaluate("""()=>({s:!!document.querySelector('[data-gsolo]'),
            f:!!document.querySelector('[data-gsvcfee]'),
            u:!!document.querySelector('[data-gsum]')})""")
        rec("صحُّ «تُقبل وحدها» وخانةُ رسومه في ورقة المجموعة",
            has["s"] and has["f"] and has["u"], str(has))

        # الحارس: استثناءٌ بلا حدٍّ أكبرَ من واحد لا يستثني شيئًا، ورسومُه
        # لن تُحصَّل أبدًا — فيُردّ عند الضبط لا يُكتشف عند أوّل عميلة.
        n0 = await pg.evaluate("()=>(window.__HSAVE||[]).length")
        await pg.evaluate("""()=>{
            document.getElementById('g-name').value='بلا حدّ';
            const free=[...document.querySelectorAll('[data-hd]')]
              .filter(r=>!r.innerText.includes('في مجموعة أخرى'));
            free[0] && free[0].click();
            document.getElementById('g-min').value='0';
            const c=document.querySelector('[data-gsolo]'); c.checked=true;
            c.dispatchEvent(new Event('change',{bubbles:true}));
            document.querySelector('[data-gsvcfee]').value='300';}""")
        await pg.wait_for_timeout(250)
        await pg.evaluate("()=>document.getElementById('g-save').click()")
        await pg.wait_for_timeout(700)
        g = await pg.evaluate("""()=>({n:(window.__HSAVE||[]).length,
            err:(document.getElementById('g-err').innerText||'').trim()})""")
        rec("و«تُقبل وحدها» بلا أقلّ عددٍ ٢ تُردّ ولا تُحفظ",
            g["n"] == n0 and "أقلّ عدد" in g["err"], f"{g['n']}=={n0} · " + g["err"][:80])

        # والمجموعُ يُرى لحظةَ الضبط: التعديل والرسوم يتراكمان.
        await pg.evaluate("""()=>{document.getElementById('g-min').value='2';
            const p=document.querySelector('[data-gprice]'); p.value='2300';
            p.dispatchEvent(new Event('input',{bubbles:true}));}""")
        await pg.wait_for_timeout(250)
        sm = await pg.evaluate("()=>(document.querySelector('[data-gsum]').innerText||'').trim()")
        rec("والمجموع يُقال قبل أن يُحصَّل: تعديلُ السعر والرسوم يتراكمان",
            "2,600" in sm or "2600" in sm.replace(",", ""), sm[:80])
        # ويظهر بالرسم وحده: الحقلان انفصلا، فلا يُشترط الصحّ لرؤية المبلغ.
        await pg.evaluate("()=>{const c=document.querySelector('[data-gsolo]');"
            "c.checked=false; c.dispatchEvent(new Event('change',{bubbles:true}));}")
        await pg.wait_for_timeout(250)
        sm2 = await pg.evaluate("()=>(document.querySelector('[data-gsum]').innerText||'').trim()")
        rec("والرسم يُحسب بلا صحِّ «تُقبل وحدها» — الحقلان مستقلّان",
            "2,600" in sm2 or "2600" in sm2.replace(",", ""), sm2[:80])
        await pg.evaluate("()=>{const c=document.querySelector('[data-gsolo]');"
            "c.checked=true; c.dispatchEvent(new Event('change',{bubbles:true}));}")
        await pg.wait_for_timeout(200)

        await pg.evaluate("()=>document.getElementById('g-save').click()")
        await pg.wait_for_timeout(900)
        sv = await pg.evaluate("()=>((window.__HSAVE||[]).slice(-1)[0]||{}).prices||[]")
        solo = [x for x in sv if x.get("solo_ok")]
        rec("ويُحفظ الصحُّ ومبلغُه مع المجموعة",
            bool(solo) and Number_(solo[0].get("svc_fee")) == 300,
            str(sv)[:110])

        # والمجرِّب يرسل الخدمة: بلا معرّفها يُردّ الاستثناء ويُقال «موقوف».
        await pg.evaluate("()=>document.getElementById('sheetClose').click()")
        await pg.wait_for_timeout(400)
        await pg.evaluate("""()=>{window.__RESOLVE__=null;
            window.__LOC__={state:'condition',checked:true,district:'العمارية',
                            fee:300,svc_fee:300,solo:true,message:'ميك اب عروس: رسوم إضافية 300 ر.س.'};
            document.getElementById('h-try').value=
              'https://www.google.com/maps/place/x/@24.7941,46.4233,15z';
            document.getElementById('h-try-go').click();}""")
        await pg.wait_for_timeout(900)
        tv = await pg.evaluate("""()=>({out:(document.getElementById('h-try-out').innerText||'').trim(),
            call:(window.__LOCCHK||[]).slice(-1)[0]||{}})""")
        rec("والمجرِّب يرسل الخدمة مع العدد",
            bool(tv["call"].get("p_service_ids")), str(tv["call"])[:110])
        rec("ويقول إنّها مرّت وحدها", "مرّت وحدها" in tv["out"], tv["out"].replace("\n", " ")[:90])

        await pg.screenshot(path=f"{_H.SHOTS}/36-hoods.png", full_page=True)
        await ctx.close()
        await b.close()

asyncio.run(main())
bad = [r for r in R if not r[1]]
print("\n=== %d/%d passed ===" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
