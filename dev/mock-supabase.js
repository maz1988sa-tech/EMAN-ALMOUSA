// Stand-in for the Supabase client, used only by dev/shots.js so the two
// surfaces can be rendered and screenshotted without a live project.
// It answers the same call shapes assets/db.js uses.
(function () {
  const svc = (id, name, icon, price, dur, desc) =>
    ({ id, name, icon, price, duration_min: dur, description: desc, sort: 0, active: true, bookable_by_client: true });

  const SERVICES = [
    svc('s1', 'ميك اب عروس', 'bride', 1500, 60, 'مكياج زفاف كامل مع التثبيت'),
    svc('s2', 'ميك اب سهرة', 'evening', 600, 45, 'مكياج مناسبات وسهرات'),
    svc('s3', 'تسريحة شعر', 'mirror', 400, 40, 'تسريحة مناسبات'),
  ];

  const pad = n => String(n).padStart(2, '0');
  const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const day = n => { const d = new Date(); d.setDate(d.getDate() + n); return iso(d); };

  const SLOTS = ['16:00:00','16:30:00','17:00:00','17:30:00','18:00:00','19:30:00','20:00:00','20:30:00'];

  const BOOKINGS = [
    { id:'b1', ref:'IA-7K3QP', public_token:'tok-1', client_name:'نورة العتيبي', client_phone:'966501234567',
      the_date: day(0), start_time:'16:00:00', duration_min:60, status:'confirmed', price:1500, deposit:500,
      items_total:1500, price_override:null, loc_text:'حي النخيل، الرياض', loc_map:'https://maps.app.goo.gl/x',
      client_notes:'بشرة حساسة', admin_notes:null, source:'client', cancel_requested:false,
      created_at:new Date().toISOString(),
      booking_items:[{id:'i1',service_name:'ميك اب عروس',service_icon:'bride',person_name:null,price:1500,duration_min:60,sort:1}] },
    { id:'b2', ref:'IA-M2XR8', public_token:'tok-2', client_name:'ريم القحطاني', client_phone:'966555554444',
      the_date: day(0), start_time:'19:30:00', duration_min:45, status:'done', price:600, deposit:600,
      items_total:600, price_override:null, loc_text:'الملقا', loc_map:null, client_notes:null,
      admin_notes:null, source:'admin', cancel_requested:false, created_at:new Date().toISOString(),
      booking_items:[{id:'i2',service_name:'ميك اب سهرة',service_icon:'evening',person_name:null,price:600,duration_min:45,sort:1}] },
    { id:'b3', ref:'IA-QQ4LZ', public_token:'tok-3', client_name:'سارة الدوسري', client_phone:'966533221100',
      the_date: day(2), start_time:'17:00:00', duration_min:150, status:'pending', price:2700, deposit:0,
      items_total:2700, price_override:null, loc_text:'حي الياسمين', loc_map:'https://maps.app.goo.gl/y',
      client_notes:'مجموعة صديقات', admin_notes:null, source:'client', cancel_requested:false,
      created_at:new Date().toISOString(),
      booking_items:[
        {id:'i3',service_name:'ميك اب عروس',service_icon:'bride',person_name:'سارة',price:1500,duration_min:60,sort:1},
        {id:'i4',service_name:'ميك اب سهرة',service_icon:'evening',person_name:'لمى',price:600,duration_min:45,sort:2},
        {id:'i5',service_name:'ميك اب سهرة',service_icon:'evening',person_name:'هند',price:600,duration_min:45,sort:3}] },
    { id:'b4', ref:'IA-8VN2C', public_token:'tok-4', client_name:'مها الشمري', client_phone:'966544332211',
      the_date: day(4), start_time:'18:00:00', duration_min:60, status:'confirmed', price:1500, deposit:400,
      items_total:1500, price_override:null, loc_text:'حي الورود', loc_map:null, client_notes:null,
      admin_notes:null, source:'client', cancel_requested:true, created_at:new Date().toISOString(),
      booking_items:[{id:'i6',service_name:'ميك اب عروس',service_icon:'bride',person_name:null,price:1500,duration_min:60,sort:1}] },
    { id:'b5', ref:'IA-3RTY6', public_token:'tok-5', client_name:'أمل الغامدي', client_phone:'966512340000',
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
    { id:'o1', the_date: day(9), kind:'closed', start_time:null, end_time:null, note:'إجازة' },
  ];

  const SETTINGS = {
    id:1, business_name:'إيمان آل موسى', tagline:'ميك اب عرائس ومناسبات', timezone:'Asia/Riyadh',
    travel_buffer_min:40, slot_step_min:30, min_lead_hours:4, max_advance_days:120,
    driver_phone:'966500000000', whatsapp_phone:'966501112222', accepting_bookings:true,
    closed_message:'الحجز مغلق مؤقتًا، تواصلي معنا عبر واتساب.',
  };

  const ok = (data) => Promise.resolve({ data, error: null });

  function table(name) {
    const rows = { services: SERVICES, bookings: BOOKINGS, availability_rules: RULES,
                   date_overrides: OVERRIDES, settings: [SETTINGS], public_settings: [SETTINGS],
                   booking_items: [], activity_log: [] }[name] || [];
    const q = {
      _rows: rows.slice(),
      select() { return q; }, eq() { return q; }, in() { return q; }, gte() { return q; },
      lte() { return q; }, ilike() { return q; }, order() { return q; }, limit() { return q; },
      insert(v) { return { select: () => ({ maybeSingle: () => ok(Array.isArray(v) ? v[0] : v) }) , then:(r)=>r({data:v,error:null}) }; },
      update(v) { return { eq: () => ({ select: () => ({ maybeSingle: () => ok({ ...rows[0], ...v }) }), then:(r)=>r({data:v,error:null}) }), then:(r)=>r({data:v,error:null}) }; },
      upsert(v) { return { select: () => ({ maybeSingle: () => ok(v) }) }; },
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
        rpc(fn, args) {
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
            return ok([{ ref:'IA-DEMO1', public_token:'tok-demo', the_date:args.p_date,
                         start_time:args.p_time, price:1500 }]);
          }
          if (fn === 'get_booking_by_token') {
            const b = BOOKINGS.find(x => x.public_token === args.p_token) || BOOKINGS[2];
            return ok([{ ...b, items: b.booking_items }]);
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
        channel() { return { on() { return this; }, subscribe() { return this; } }; },
        removeChannel() {},
      };
    },
  };
})();
