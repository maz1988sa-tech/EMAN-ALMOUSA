// Stand-in for the Supabase client, used only by dev/shots.js so the two
// surfaces can be rendered and screenshotted without a live project.
// It answers the same call shapes assets/db.js uses.
(function () {
  const svc = (id, name, icon, price, dur, desc, grp = true) =>
    ({ id, name, icon, price, duration_min: dur, description: desc, sort: 0, active: true,
       bookable_by_client: true, group_discount: grp, deposit_amount: 0 });
  const dep = (s, amount) => ({ ...s, deposit_amount: amount });

  const SERVICES = [
    dep(svc('s1', 'ميك اب عروس', 'bride', 1500, 60, 'مكياج زفاف كامل مع التثبيت', false), 375),
    dep(svc('s2', 'ميك اب سهرة', 'evening', 600, 45, 'مكياج مناسبات وسهرات'), 150),
    dep(svc('s3', 'تسريحة شعر', 'mirror', 400, 40, 'تسريحة مناسبات'), 100),
  ];

  const pad = n => String(n).padStart(2, '0');
  const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const day = n => { const d = new Date(); d.setDate(d.getDate() + n); return iso(d); };

  const SLOTS = ['16:00:00','16:30:00','17:00:00','17:30:00','18:00:00','19:30:00','20:00:00','20:30:00'];

  const BOOKINGS = [
    { id:'b1', ref:'EA-20260800', public_token:'tok-1', client_name:'نورة العتيبي', client_phone:'966501234567',
      the_date: day(0), start_time:'16:00:00', duration_min:60, status:'confirmed', price:1500, deposit:500,
      items_total:1500, price_override:null, loc_text:'حي النخيل، الرياض', loc_map:'https://maps.app.goo.gl/x',
      client_notes:'بشرة حساسة', admin_notes:null, source:'client', cancel_requested:false,
      created_at:new Date().toISOString(),
      booking_items:[{id:'i1',service_name:'ميك اب عروس',service_icon:'bride',person_name:null,price:1500,duration_min:60,sort:1}] },
    { id:'b2', ref:'EA-20260801', public_token:'tok-2', client_name:'ريم القحطاني', client_phone:'966555554444',
      the_date: day(0), start_time:'19:30:00', duration_min:45, status:'done', price:600, deposit:600,
      items_total:600, price_override:null, loc_text:'الملقا', loc_map:null, client_notes:null,
      admin_notes:null, source:'admin', cancel_requested:false, created_at:new Date().toISOString(),
      booking_items:[{id:'i2',service_name:'ميك اب سهرة',service_icon:'evening',person_name:null,price:600,duration_min:45,sort:1}] },
    { id:'b3', ref:'EA-20260802', public_token:'tok-3', client_name:'سارة الدوسري', client_phone:'966533221100',
      the_date: day(2), start_time:'17:00:00', duration_min:150, status:'pending', price:2700, deposit:0,
      items_total:2700, price_override:null, loc_text:'حي الياسمين', loc_map:'https://maps.app.goo.gl/y',
      client_notes:'مجموعة صديقات', admin_notes:null, source:'client', cancel_requested:false,
      created_at:new Date().toISOString(),
      booking_items:[
        {id:'i3',service_name:'ميك اب عروس',service_icon:'bride',person_name:'سارة',price:1500,duration_min:60,sort:1},
        {id:'i4',service_name:'ميك اب سهرة',service_icon:'evening',person_name:'لمى',price:600,duration_min:45,sort:2},
        {id:'i5',service_name:'ميك اب سهرة',service_icon:'evening',person_name:'هند',price:600,duration_min:45,sort:3}] },
    { id:'b4', ref:'EA-20260803', public_token:'tok-4', client_name:'مها الشمري', client_phone:'966544332211',
      the_date: day(4), start_time:'18:00:00', duration_min:60, status:'confirmed', price:1500, deposit:400,
      items_total:1500, price_override:null, loc_text:'حي الورود', loc_map:null, client_notes:null,
      admin_notes:null, source:'client', cancel_requested:true, created_at:new Date().toISOString(),
      booking_items:[{id:'i6',service_name:'ميك اب عروس',service_icon:'bride',person_name:null,price:1500,duration_min:60,sort:1}] },
    { id:'b5', ref:'EA-20260804', public_token:'tok-5', client_name:'أمل الغامدي', client_phone:'966512340000',
      the_date: day(-6), start_time:'17:30:00', duration_min:45, status:'done', price:600, deposit:600,
      items_total:600, price_override:null, loc_text:null, loc_map:null, client_notes:null,
      admin_notes:null, source:'admin', cancel_requested:false, created_at:new Date().toISOString(),
      booking_items:[{id:'i7',service_name:'ميك اب سهرة',service_icon:'evening',person_name:null,price:600,duration_min:45,sort:1}] },
  ];

  const RULES = [
    { id:'r1', label:'أيام الأسبوع', weekday:6, start_time:'16:00:00', end_time:'22:00:00', active:true, valid_from:null, valid_to:null },
    { id:'r2', label:'أيام الأسبوع', weekday:0, start_time:'16:00:00', end_time:'22:00:00', active:true, valid_from:null, valid_to:null },
    { id:'r3', label:'أيام الأسبوع', weekday:1, start_time:'16:00:00', end_time:'22:00:00', active:true, valid_from:null, valid_to:null },
    { id:'r4', label:'الخميس صباحًا', weekday:4, start_time:'09:00:00', end_time:'13:00:00', active:true, valid_from:null, valid_to:null },
  ];

  const OVERRIDES = [
    { id:'o1', the_date: day(9), end_date: day(9), kind:'closed',
      start_time:null, end_time:null, note:'إجازة' },
    // فترةٌ ممتدّة: سفرٌ أربعة أيام — تُقرأ صفًّا واحدًا لا أربعة.
    { id:'o2', the_date: day(14), end_date: day(17), kind:'closed',
      start_time:null, end_time:null, note:'سفر' },
  ];

  const TEMPLATES = [
    { id:'t1', title:'تأكيد الموعد', pinned:true, sort:1, active:true, builtin:true,
      auto_enabled:false, auto_trigger:null, auto_offset_min:0, auto_at_hour:null,
      wa_template_name:null, wa_template_lang:'ar', wa_template_ok:false,
      body:'أهلاً {الاسم} 🌸\nتم تأكيد موعدك مع {الاسم التجاري}:\n\n📅 {التاريخ}\n🕐 {الوقت}\n💄 {الخدمة}\n💰 الإجمالي: {الإجمالي}\n\nلمتابعة حجزك:\n{رابط الحجز}\n\nبانتظارك 💗',
      created_at:new Date().toISOString() },
    { id:'t2', title:'تذكير قبل الموعد', pinned:false, sort:2, active:true, builtin:true,
      auto_enabled:true, auto_trigger:'before_appt', auto_offset_min:1440, auto_at_hour:18,
      wa_template_name:'appt_reminder', wa_template_lang:'ar', wa_template_ok:true,
      body:'تذكير بموعدك غدًا مع {الاسم التجاري} 🌸\n\n📅 {التاريخ}\n🕐 {الوقت}\n📍 {الموقع}\n\nالمتبقي: {المتبقي}\n\nنراكِ غدًا 💗',
      created_at:new Date().toISOString() },
    { id:'t3', title:'طلب العربون', pinned:false, sort:3, active:true, builtin:false,
      auto_enabled:false, auto_trigger:null, auto_offset_min:0, auto_at_hour:null,
      wa_template_name:null, wa_template_lang:'ar', wa_template_ok:false,
      body:'أهلاً {الاسم} 🌸\nلتثبيت موعد {التاريخ} الساعة {الوقت} يلزم عربون {العربون} من إجمالي {الإجمالي}.\n\nشاكرين لكِ 💗',
      created_at:new Date().toISOString() },
  ];

  // الطابور الوهميّ: يمتلئ من schedule المحاكى، وتقرؤه اللوحة كما تقرأ الحقيقيّ.
  const OUTBOX = [];

  const SETTINGS = {
    id:1, business_name:'إيمان آل موسى', tagline:'ميك اب عرائس ومناسبات', timezone:'Asia/Riyadh',
    travel_buffer_min:40, slot_step_min:30, min_lead_hours:4, max_advance_days:120,
    driver_phone:'966500000000', whatsapp_phone:'966501112222', accepting_bookings:true,
    closed_message:'الحجز مغلق مؤقتًا، تواصلي معنا عبر واتساب.',
    require_loc_map:false, group_discount:true, group_discount_amount:100,
    deposit_rate:0.25, iban:'SA0380000000608010167519', bank_name:'الراجحي',
    beneficiary_name:'إيمان آل موسى', receipt_ocr_required:false,
    instagram_url:'https://instagram.com/example',
    tiktok_url:'https://tiktok.com/@example',
    show_closed_months:true, closed_month_word:'غير مفتوحة',
    wa_auto_enabled:false, wa_phone_id:null, wa_quiet_from:22, wa_quiet_to:9,
    wa_test_phone:null, receipt_iban_digits:6,
  };

  const ok = (data) => Promise.resolve({ data, error: null });

  function table(name) {
    const rows = { services: SERVICES, bookings: BOOKINGS, availability_rules: RULES,
                   date_overrides: OVERRIDES, settings: [SETTINGS], public_settings: [SETTINGS],
                   booking_items: [], activity_log: [],
                   message_templates: TEMPLATES }[name] || [];
    const q = {
      _rows: rows.slice(),
      select() { return q; }, eq() { return q; }, in() { return q; }, gte() { return q; },
      lte() { return q; }, ilike() { return q; }, order() { return q; }, limit() { return q; },
      insert(v) { return { select: () => ({ maybeSingle: () => ok(Array.isArray(v) ? v[0] : v) }) , then:(r)=>r({data:v,error:null}) }; },
      update(v) { return { eq: () => ({ select: () => ({ maybeSingle: () => ok({ ...rows[0], ...v }) }), then:(r)=>r({data:v,error:null}) }), then:(r)=>r({data:v,error:null}) }; },
      upsert(v) { (window.__UPSERT = window.__UPSERT || []).push(v);
                  return { select: () => ({ maybeSingle: () => ok(v) }) }; },
      delete() { return { eq: () => ok(null) }; },
      maybeSingle() { return ok(q._rows[0] || null); },
      single() { return ok(q._rows[0] || null); },
      then(res) { return res({ data: q._rows, error: null }); },
    };
    return q;
  }

  window.supabase = {
    createClient() {
      return {
        from: table,
        rpc(name, args) {
          const fn = name;
          (window.__RPC = window.__RPC || []).push({ name, args });
          if (fn === 'admin_create_group') {
            const gid = 'grp-' + Math.random().toString(36).slice(2, 8);
            return ok((args.p_people || []).map((p, i) => ({
              id: 'gb' + i, ref: 'EA-20260' + String(810 + i), public_token: 'tok-g' + i,
              group_id: gid, group_label: args.p_label || null,
              status: 'confirmed', source: 'admin',
              price: (p.items || []).reduce((n, it) => n + Number(it.price || 0), 0),
              booking_items: p.items || [], ...p,
            })));
          }
          if (fn === 'admin_create_booking' || fn === 'admin_replace_items') {
            if (fn === 'admin_create_booking') {
              const bk = args.p_booking || {};
              return ok([{ id:'b-new', ref:'EA-20260806', public_token:'tok-new',
                           ...bk, booking_items: args.p_items || [] }]);
            }
            return ok([{ id: args.p_booking_id, booking_items: args.p_items || [] }]);
          }
          if (fn === 'admin_purge_bookings') {
            const from = args.p_from, to = args.p_to;
            const hit = BOOKINGS.filter(b => (!from || b.the_date >= from) && (!to || b.the_date <= to));
            const files = hit.slice(0, 2).map((b, i) => `pending/r${i + 1}.jpg`);
            if (args.p_dry === false) hit.forEach(b => {
              const i = BOOKINGS.indexOf(b); if (i >= 0) BOOKINGS.splice(i, 1);
            });
            return ok([{ affected: hit.length, receipts: files }]);
          }
          if (fn === 'orphan_receipts') return ok([]);
          if (fn === 'admin_snapshot') {
            return ok({ taken_at: new Date().toISOString(),
                        counts: { bookings: BOOKINGS.length, services: SERVICES.length,
                                  rules: RULES.length, overrides: OVERRIDES.length,
                                  templates: TEMPLATES.length },
                        bookings: BOOKINGS.map((b, i) => ({ ...b,
                          receipt_path: i < 2 ? `pending/r${i + 1}.jpg` : null })),
                        services: SERVICES, availability_rules: RULES,
                        date_overrides: OVERRIDES, message_templates: TEMPLATES,
                        settings: SETTINGS });
          }
          if (fn === 'available_slots') {
            const dur = args.p_duration_min || 45;
            return ok(SLOTS.filter((_, i) => dur <= 60 || i % 2 === 0).map(slot => ({ slot })));
          }
          if (fn === 'days_with_availability') {
            const out = [];
            for (let i = 0; i < (args.p_days || 14); i++) {
              const d = day(i);
              const dow = new Date(d).getDay();
              out.push({ the_date: d, slot_count: (dow === 5 || i === 9) ? 0 : (args.p_duration_min > 120 ? 4 : 8) });
            }
            return ok(out);
          }
          if (fn === 'create_booking') {
            return ok([{ ref:'EA-20260805', public_token:'tok-demo', the_date:args.p_date,
                         start_time:args.p_time, price:1500 }]);
          }
          if (fn === 'get_booking_by_token') {
            const b = BOOKINGS.find(x => x.public_token === args.p_token) || BOOKINGS[2];
            return ok([{ ...b, items: b.booking_items }]);
          }
          if (fn === 'get_public_settings') return ok([SETTINGS]);

          /* حكم الإيصال: يُملى من الفحص عبر window.__RECEIPT__ ليُجرَّب
             القبولُ والرفض والانتظار بلا قراءةٍ حقيقية للصورة. */
          if (fn === 'check_receipt') {
            (window.__CHECKS = window.__CHECKS || []).push(args);
            const v = window.__RECEIPT__ || 'ok';
            const d = Number(window.__RECEIPT_DELAY__) || 0;
            // الفحص الحقيقي يستغرق ثوانيَ؛ التأخير يجعل حال الانتظار قابلةً للقياس.
            return d ? new Promise((r) => setTimeout(() => r({ data: v, error: null }), d))
                     : ok(v);
          }

          /* ــ الرسائل التلقائية: جدولةٌ مبسّطة تكفي لفحص اللوحة ــــــــــ */
          if (fn === 'render_template') {
            const b = BOOKINGS.find(x => x.id === args.p_booking) || BOOKINGS[0] || {};
            const items = b.booking_items || [];
            const M = new Intl.NumberFormat('ar-SA-u-nu-latn', { maximumFractionDigits: 0 });
            const rs = (v) => `${M.format(Math.round(Number(v) || 0))} ر.س`;
            const DOW = ['الأحد','الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت'];
            const MON = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس',
                         'سبتمبر','أكتوبر','نوفمبر','ديسمبر'];
            const [Y,Mo,D] = String(b.the_date || '').split('-').map(Number);
            const dt = new Date(Y, (Mo||1)-1, D||1);
            const [hh,mm] = String(b.start_time || '00:00').split(':');
            const h24 = Number(hh);
            const map = {
              '{الاسم}': b.client_name || '',
              '{التاريخ}': `${DOW[dt.getDay()]} ${dt.getDate()} ${MON[dt.getMonth()]} ${dt.getFullYear()}`,
              '{الوقت}': `${h24 % 12 === 0 ? 12 : h24 % 12}:${String(mm).padStart(2,'0')} ${h24 < 12 ? 'ص' : 'م'}`,
              '{الخدمة}': items.map(i => i.service_name).filter(Boolean).join(' + '),
              '{الإجمالي}': rs(b.price), '{العربون}': rs(b.deposit),
              '{المتبقي}': rs(Math.max(Number(b.price||0) - Number(b.deposit||0), 0)),
              '{الموقع}': b.loc_text || '',
              '{رابط الحجز}': `https://eman-aalmousa.com/?t=${b.public_token || ''}`,
              '{الاسم التجاري}': SETTINGS.business_name,
            };
            return ok(String(args.p_body || '').replace(/\{[^}]{1,24}\}/g,
              (m) => (m in map ? map[m] : m)));
          }
          if (fn === 'admin_reschedule_auto') {
            OUTBOX.length = 0;
            const live = !!SETTINGS.wa_auto_enabled && !!SETTINGS.wa_phone_id;
            TEMPLATES.filter(t => t.auto_enabled && t.auto_trigger).forEach((t) => {
              BOOKINGS.slice(0, 3).forEach((b, i) => {
                const due = new Date(Date.now() + (i - 1) * 86400000);
                OUTBOX.push({ id: `ob-${t.id}-${b.id}`, booking_id: b.id, ref: b.ref,
                  client_name: b.client_name, to_phone: b.client_phone, title: t.title,
                  trigger_kind: t.auto_trigger, due_at: due.toISOString(),
                  status: due <= new Date() ? (live ? 'failed' : 'preview') : 'queued',
                  body: due <= new Date() ? t.body : null,
                  error: due <= new Date() && !live ? 'وضع المعاينة — لم يُربط حساب واتساب بعد' : null,
                  sent_at: null });
              });
            });
            return ok(OUTBOX.length);
          }
          if (fn === 'admin_outbox') return ok(OUTBOX.slice(0, args?.p_limit || 100));
          if (fn === 'admin_send_test') {
            OUTBOX.unshift({ id:'ob-test', booking_id:null, ref:'—', client_name:'رسالة تجربة',
              to_phone:args.p_phone, title:'تجربة الإرسال', trigger_kind:'test',
              due_at:new Date().toISOString(), status:'sending',
              body:'رسالة تجربة من إيمان آل موسى — إن وصلتك هذه فالإرسال التلقائي يعمل.',
              error:null, sent_at:null });
            return ok('ob-test');
          }
          if (fn === 'admin_reconcile') {
            OUTBOX.filter(o => o.status === 'sending').forEach((o) => {
              o.status = 'sent'; o.sent_at = new Date().toISOString(); o.error = null;
            });
            return ok(1);
          }
          if (fn === 'request_cancel') return ok(true);
          return ok([]);
        },
        auth: {
          getSession: () => Promise.resolve({ data: { session: window.__MOCK_SIGNED_IN__ ? { user: { email:'eman@example.com' } } : null } }),
          signInWithPassword: () => Promise.resolve({ data: { session: {} }, error: null }),
          signOut: () => Promise.resolve({}),
          onAuthStateChange: () => ({ data: { subscription: { unsubscribe(){} } } }),
        },
        // تخزينٌ صوريّ: يقبل الرفع ويعيد مسارًا، فيمشي مسار الإيصال والنسخ
        // الاحتياطيّة في التطوير كما يمشي على القاعدة الحقيقيّة.
        storage: {
          from(bucket) {
            const files = (window.__FILES = window.__FILES || {});
            files[bucket] = files[bucket] || {};
            return {
              upload(path, body) {
                // عطبٌ يُطلب صراحةً: يسقط الرفع كما يسقط على شبكةٍ رديئة.
                if (window.__UPLOAD_FAILS__) {
                  return Promise.resolve({ data: null, error: { message: 'upload failed' } });
                }
                files[bucket][path] = body;
                (window.__UP = window.__UP || []).push({ bucket, path });
                if (bucket === 'receipts') (window.__UPLOADED__ = window.__UPLOADED__ || []).push(path);
                return Promise.resolve({ data: { path }, error: null });
              },
              copy(from, to, opts) {
                const dest = (opts && opts.destinationBucket) || bucket;
                files[dest] = files[dest] || {};
                files[dest][to] = files[bucket][from] || new Blob(['x']);
                (window.__COPIES = window.__COPIES || []).push({ bucket: dest, from, to });
                return Promise.resolve({ data: { path: to }, error: null });
              },
              remove(paths) {
                [].concat(paths).forEach((p) => delete files[bucket][p]);
                return Promise.resolve({ data: null, error: null });
              },
              list(dir) {
                return Promise.resolve({ data: Object.keys(files[bucket])
                  .filter((k) => !dir || k.startsWith(dir))
                  .map((k) => ({ name: k.split('/').pop(), id: k,
                                 created_at: new Date().toISOString(),
                                 metadata: { size: 1024 } })), error: null });
              },
              download(path) {
                return Promise.resolve({ data: files[bucket][path] || new Blob(['{}']), error: null });
              },
              getPublicUrl(path) {
                return { data: { publicUrl: `https://mock.local/${bucket}/${path}` } };
              },
              createSignedUrl(path) {
                return Promise.resolve({ data: { signedUrl: `https://mock.local/${bucket}/${path}?s=1` },
                                         error: null });
              },
            };
          },
        },
        functions: {
          // قراءة الإيصال: يردّ ما يضعه الاختبار في window.__ocrReply، وإلّا
          // تعذّرت القراءة — وهو ما لا يمنع الحجز على القاعدة الحقيقيّة.
          invoke(name, opts) {
            (window.__FN = window.__FN || []).push({ name, opts });
            const r = window.__ocrReply;
            if (r) return Promise.resolve({ data: r, error: null });
            return Promise.resolve({ data: null, error: { message: 'no function in mock' } });
          },
        },
        channel() { return { on() { return this; }, subscribe() { return this; } }; },
        removeChannel() {},
      };
    },
  };
})();
