// فكُّ رابط خرائط قوقل المختصر إلى إحداثيّتين.
//
// زرّ «مشاركة الموقع» في تطبيق الخرائط لا يُخرج رابطًا فيه إحداثيّات، بل
// `maps.app.goo.gl/XXXX` — وهذا هو الرابط الذي تلصقه العميلة فعلًا. وكان
// يُردّ عند الحقل، فبقي فحص الأحياء نظريًّا: الشرط مضبوط والرابط الشائع
// لا يُقرأ. والمتصفّح لا يستطيع فكَّه — التحويلة عابرةُ أصلٍ فيمنعها CORS
// — فيُفكّ هنا.
//
// وهذه الدالّة تجلب من الشبكة، فهي بابٌ لو فُتح على مصراعيه صارت وكيلًا
// يطلب باسم الخادم أيَّ عنوان. فالقائمة البيضاء تُفحص **عند كل قفزة** لا
// عند الأولى وحدها: تحويلةٌ إلى عنوانٍ داخليّ تُوقف السلسلة.
import 'jsr:@supabase/functions-js/edge-runtime.d.ts';

/** مضيفو خرائط قوقل وحدهم — ومعهم صفحة الموافقة التي تعترض أحيانًا. */
const HOSTS = [
  'maps.app.goo.gl', 'goo.gl', 'www.google.com', 'google.com',
  'maps.google.com', 'www.google.com.sa', 'google.com.sa',
  'maps.google.com.sa', 'consent.google.com',
];
const HOST_RE = /^(?:[a-z0-9-]+\.)*google\.(?:com|[a-z]{2,3}(?:\.[a-z]{2})?)$|^maps\.app\.goo\.gl$|^goo\.gl$/i;
const MAX_HOPS = 6;
const UA = 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Mobile Safari/537.36';

function allowed(u: URL): boolean {
  if (u.protocol !== 'https:') return false;
  const h = u.hostname.toLowerCase();
  return HOSTS.includes(h) || HOST_RE.test(h);
}

const num = (s: string) => {
  const n = Number(s);
  return isFinite(n) ? n : NaN;
};

/** نقطةٌ معقولة: لا صفرٌ مزدوج ولا خارج الكرة. */
function pt(lat: number, lng: number) {
  if (!isFinite(lat) || !isFinite(lng)) return null;
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
  if (lat === 0 && lng === 0) return null;
  return { lat: Number(lat.toFixed(7)), lng: Number(lng.toFixed(7)) };
}

/** الإحداثيّات من عنوانٍ صريح. ترتيبُ المحاولات ترتيبُ الثقة:
 *  `!3d…!4d…` موضعُ المكان نفسه، و`@` مركزُ الشاشة وقد يزيغ قليلًا. */
function fromUrl(raw: string) {
  let m = raw.match(/!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/);
  if (m) { const p = pt(num(m[1]), num(m[2])); if (p) return p; }

  try {
    const u = new URL(raw);
    for (const k of ['q', 'query', 'll', 'center', 'destination', 'daddr', 'viewpoint']) {
      const v = u.searchParams.get(k);
      const mm = v && v.match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/);
      if (mm) { const p = pt(num(mm[1]), num(mm[2])); if (p) return p; }
    }
    // صفحة الموافقة تحمل الوجهة في `continue`
    const cont = u.searchParams.get('continue');
    if (cont) { const p = fromUrl(cont); if (p) return p; }
  } catch { /* ليس عنوانًا صالحًا */ }

  m = raw.match(/[@\/](-?\d{1,2}\.\d{4,}),(-?\d{1,3}\.\d{4,})/);
  if (m) { const p = pt(num(m[1]), num(m[2])); if (p) return p; }

  /* وأخيرًا رمز Plus داخل `q` — وهو ما يضعه زرّ المشاركة غالبًا.
     ويُقرأ من النصّ **الخام**: `+` في سلسلة الاستعلام تعني مسافة، فـ
     `searchParams` تُرجع «RM2H 3XQ» ويضيع الرمز. والعنوان المفكوك يبقى
     للتحقّق من المدينة وحده. */
  const q = raw.match(/[?&]q=([^&#]*)/);
  if (q) {
    let text = q[1];
    try { text = decodeURIComponent(q[1].replace(/\+/g, ' ')); } catch { /* ترميز معطوب */ }
    const p = fromPlusCode(q[1], text);
    if (p) return p;
  }
  return null;
}

/* رمز Plus. زرّ «مشاركة الموقع» حين يكون على دبّوسٍ أو مكانٍ بحديقة أو
   شارع يُحوّل إلى `maps.google.com?q=RM2H+3XQ <العنوان>` — لا إحداثيّات
   بل **رمز موقعٍ مفتوح** يرمّزها ترميزًا معكوسًا تمامًا. فليس تخمينًا من
   الصفحة بل فكُّ ما وضعه قوقل نفسه في العنوان.

   والرمز المختصر (أربعة خانات قبل `+`) حُذف رأسه، فيُستعاد بأقرب نقطةٍ
   إلى مرجع. ومرجعُنا الرياض — فيلزم أن يقول العنوان إنّه فيها، وإلّا
   استُعيد رمزُ جدّة عند الرياض فوقعت العميلة في حيٍّ ليس حيَّها. */
const A = '23456789CFGHJMPQRVWX';
const PAIR_RES = [20, 1, 0.05, 0.0025, 0.000125];
const REF_LAT = 24.7136, REF_LNG = 46.6753;                 // مركز الرياض
const IN_RIYADH = /الرياض|riyadh|ar[- ]?riyadh/i;
const PLUS_RE = /(?:^|[\s+])([23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{0,5})(?:[\s+]|$)/i;

function olcDigits(lat: number, lng: number, n: number) {
  lat = Math.min(89.999999, Math.max(-90, lat));
  lng = ((lng + 180) % 360 + 360) % 360 - 180;
  let rLat = lat + 90, rLng = lng + 180, out = '';
  for (let i = 0; i < 5 && out.length < n; i++) {
    const r = PAIR_RES[i];
    let d = Math.floor(rLat / r); out += A[d]; rLat -= d * r;
    d = Math.floor(rLng / r); out += A[d]; rLng -= d * r;
  }
  return out.slice(0, n);
}

function olcBox(code: string) {
  const c = code.replace(/\+/g, '').replace(/0+$/, '').toUpperCase();
  let lat = -90, lng = -180, latRes = 20, lngRes = 20, i = 0;
  for (; i + 1 < c.length && i < 10; i += 2) {
    lat += A.indexOf(c[i]) * latRes;
    lng += A.indexOf(c[i + 1]) * lngRes;
    if (i < 8) { latRes /= 20; lngRes /= 20; }
  }
  for (; i < c.length && i < 15; i++) {
    const d = A.indexOf(c[i]);
    latRes /= 5; lngRes /= 4;
    lat += Math.floor(d / 4) * latRes;
    lng += (d % 4) * lngRes;
  }
  return { lat, lng, latRes, lngRes };
}

/** يفكّ رمز Plus من `rawQ` الخام، ويتحقّق من المدينة في `text` المفكوك. */
function fromPlusCode(rawQ: string, text: string) {
  const m = String(rawQ || '').match(PLUS_RE);
  if (!m) return null;
  const code = m[1].toUpperCase();
  const pad = 8 - code.indexOf('+');
  if (pad > 0 && !IN_RIYADH.test(text || '')) return null;
  let lat: number, lng: number;
  if (pad > 0) {
    const resolution = Math.pow(20, 2 - pad / 2), half = resolution / 2;
    const b = olcBox(olcDigits(REF_LAT, REF_LNG, pad) + code);
    lat = b.lat + b.latRes / 2; lng = b.lng + b.lngRes / 2;
    if (REF_LAT - lat > half) lat += resolution; else if (lat - REF_LAT > half) lat -= resolution;
    if (REF_LNG - lng > half) lng += resolution; else if (lng - REF_LNG > half) lng -= resolution;
  } else {
    const b = olcBox(code);
    lat = b.lat + b.latRes / 2; lng = b.lng + b.lngRes / 2;
  }
  return pt(lat, lng);
}

/* ولا يُقرأ جسمُ الصفحة. جُرّب فسقط: خادم الحافة في فرانكفورت، فقوقل
   يخدمه صفحةً ألمانية مركزُها ألمانيا — و«إحداثيّاتٌ وجدناها في الصفحة»
   كانت ستضع العميلة في حيٍّ ليس حيَّها، صامتةً. فلا يُوثق إلّا بما يأتي
   في عنوانٍ صريح: الرابط نفسه أو وجهةُ تحويلة. وما عداه يُردّ `no_coords`
   فيُقال لها: الصقي الرابط الكامل. الرفضُ المفهوم خيرٌ من موقعٍ خاطئ. */

Deno.serve(async (req) => {
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
    'Content-Type': 'application/json; charset=utf-8',
  };
  if (req.method === 'OPTIONS') return new Response('ok', { headers: cors });
  const reply = (body: Record<string, unknown>, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: cors });

  try {
    const payload = await req.json().catch(() => ({}));
    const raw = typeof payload?.url === 'string' ? payload.url.trim() : '';
    if (!raw || raw.length > 2048) return reply({ ok: false, reason: 'bad_url' }, 400);

    let u: URL;
    try { u = new URL(raw); } catch { return reply({ ok: false, reason: 'bad_url' }, 400); }
    if (!allowed(u)) return reply({ ok: false, reason: 'bad_host' }, 400);

    // قد يكون فيه إحداثيّات أصلًا فلا حاجة إلى الشبكة.
    const direct = fromUrl(raw);
    if (direct) return reply({ ok: true, ...direct, hops: 0 });

    let cur = u.toString();
    for (let hop = 0; hop < MAX_HOPS; hop++) {
      const res = await fetch(cur, {
        redirect: 'manual',
        headers: { 'user-agent': UA, 'accept-language': 'ar,en;q=0.8' },
      });
      const next = res.headers.get('location');
      if (res.status >= 300 && res.status < 400 && next) {
        let nu: URL;
        try { nu = new URL(next, cur); } catch { return reply({ ok: false, reason: 'bad_redirect' }); }
        if (!allowed(nu)) return reply({ ok: false, reason: 'bad_redirect' });
        cur = nu.toString();
        const p = fromUrl(cur);
        if (p) return reply({ ok: true, ...p, hops: hop + 1 });
        continue;
      }
      // آخر الطريق ولم تأتِ إحداثيّات في عنوان: يُترك الجسم بلا قراءة.
      await res.body?.cancel();
      break;
    }

    const p = fromUrl(cur);
    if (p) return reply({ ok: true, ...p });

    /* رابطٌ إلى «مكان» محفوظ عند قوقل: ينتهي إلى `ftid` وحده — معرّفُ
       مكانٍ لا موقع. لا سبيل إلى إحداثيّاته بلا مفتاح Places مدفوع،
       فيُميَّز السبب ليقال للعميلة ما تفعل بدل «تعذّر» غامضة. */
    const placeOnly = /[?&]ftid=/.test(cur) && !/[?&]q=/.test(cur);
    return reply({ ok: false, reason: placeOnly ? 'place_only' : 'no_coords' });
  } catch (e) {
    console.error('resolve_map_failed', String(e));
    return reply({ ok: false, reason: 'server_error' }, 500);
  }
});
