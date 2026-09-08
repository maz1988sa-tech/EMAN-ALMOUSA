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
  return null;
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
    return reply({ ok: false, reason: 'no_coords' });
  } catch (e) {
    console.error('resolve_map_failed', String(e));
    return reply({ ok: false, reason: 'server_error' }, 500);
  }
});
