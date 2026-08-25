/* ==========================================================================
   Shared data + formatting layer.

   Both surfaces talk to the database only through this file, so the security
   boundary stays legible: the public page calls the rpc* helpers, which map
   onto security-definer functions; everything under `admin` needs a session.
   ========================================================================== */

const CFG = window.APP_CONFIG || {};

export const sb = window.supabase.createClient(CFG.SUPABASE_URL, CFG.SUPABASE_KEY, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
});

/* ── Formatting ────────────────────────────────────────────────────────────
   The previous system mixed Arabic-Indic and Western digits inside a single
   card, and stamped "م" on every time including 9 in the morning. Both are
   fixed here, once, for every screen.
   ------------------------------------------------------------------------ */

const MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
                'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];
const DOW_LONG  = ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];
const DOW_SHORT = ['أحد', 'اثنين', 'ثلاثاء', 'أربعاء', 'خميس', 'جمعة', 'سبت'];

export const WEEKDAYS = DOW_LONG.map((name, i) => ({ value: i, name, short: DOW_SHORT[i] }));

// Latin digits throughout, Arabic grouping. One rule, no mixed cards.
const NUM = new Intl.NumberFormat('ar-SA-u-nu-latn', { maximumFractionDigits: 0 });

export const money = (v) => NUM.format(Math.round(Number(v) || 0));
export const riyal = (v) => `${money(v)} ر.س`;
export const int   = (v) => NUM.format(Number(v) || 0);

/** 'YYYY-MM-DD' for a Date, read in the local calendar — never via toISOString,
 *  which silently reports yesterday for anyone east of Greenwich. */
export function isoDate(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Parse 'YYYY-MM-DD' as a local date, so no timezone shift can occur. */
export function parseDate(s) {
  const [y, m, d] = String(s).split('-').map(Number);
  return new Date(y, m - 1, d);
}

export const today    = () => isoDate(new Date());
export const addDays  = (s, n) => { const d = parseDate(s); d.setDate(d.getDate() + n); return isoDate(d); };
export const weekday  = (s) => parseDate(s).getDay();

export function fmtDate(s, { withDow = true, short = false } = {}) {
  if (!s) return '';
  const d = parseDate(s);
  const body = `${d.getDate()} ${MONTHS[d.getMonth()]}${short ? '' : ` ${d.getFullYear()}`}`;
  return withDow ? `${DOW_LONG[d.getDay()]} ${body}` : body;
}

export function fmtDateRelative(s) {
  const t = today();
  if (s === t) return 'اليوم';
  if (s === addDays(t, 1)) return 'غدًا';
  if (s === addDays(t, -1)) return 'أمس';
  return fmtDate(s, { short: true });
}

/** 'HH:MM:SS' → '٩:٣٠ ص' / '٦:٠٠ م', with the meridiem actually correct. */
export function fmtTime(t) {
  if (!t) return '';
  const [hRaw, m] = String(t).split(':');
  const h24 = Number(hRaw);
  const meridiem = h24 < 12 ? 'ص' : 'م';
  const h12 = h24 % 12 === 0 ? 12 : h24 % 12;
  return `${h12}:${String(m).padStart(2, '0')} ${meridiem}`;
}

export function fmtDuration(mins) {
  const n = Number(mins) || 0;
  const h = Math.floor(n / 60), m = n % 60;
  if (!h) return `${m} دقيقة`;
  const hw = h === 1 ? 'ساعة' : h === 2 ? 'ساعتان' : `${h} ساعات`;
  return m ? `${hw} و${m} دقيقة` : hw;
}

/** Wall-clock arithmetic that keeps the day, so a job crossing midnight stays
 *  ordered instead of wrapping to a smaller number than it started at. */
export function addMinutes(time, mins) {
  const [h, m] = String(time).split(':').map(Number);
  const total = h * 60 + m + Number(mins || 0);
  const dayOffset = Math.floor(total / 1440);
  const inDay = ((total % 1440) + 1440) % 1440;
  return {
    time: `${String(Math.floor(inDay / 60)).padStart(2, '0')}:${String(inDay % 60).padStart(2, '0')}`,
    dayOffset,
    absolute: total,
  };
}

export const endOf = (start, mins) => addMinutes(start, mins);

/* ── Phone ─────────────────────────────────────────────────────────────── */

/** Accepts 05…, +9665…, 009665…, spaces, dashes and Arabic-Indic digits.
 *  Returns the canonical 9665XXXXXXXX, or null when it is not a Saudi mobile. */
export function normalisePhone(raw) {
  if (!raw) return null;
  let s = String(raw)
    .replace(/[٠-٩]/g, (d) => '٠١٢٣٤٥٦٧٨٩'.indexOf(d))
    .replace(/[۰-۹]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
    .replace(/\D/g, '');
  s = s.replace(/^00966/, '').replace(/^966/, '').replace(/^0/, '');
  const full = `966${s}`;
  return /^9665\d{8}$/.test(full) ? full : null;
}

/** 9665XXXXXXXX → 05X XXX XXXX, for display only. */
export function prettyPhone(p) {
  const n = normalisePhone(p);
  if (!n) return p || '';
  const local = `0${n.slice(3)}`;
  return `${local.slice(0, 3)} ${local.slice(3, 6)} ${local.slice(6)}`;
}

export const telHref = (p) => `tel:+${normalisePhone(p) || p}`;

export function waHref(phone, message = '') {
  const n = normalisePhone(phone);
  if (!n) return '#';
  const text = message ? `?text=${encodeURIComponent(message)}` : '';
  return `https://wa.me/${n}${text}`;
}

/* ── Escaping ──────────────────────────────────────────────────────────────
   Client names are rendered into markup in several places. Everything that
   is not a literal goes through here.
   ------------------------------------------------------------------------ */
export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ── Status vocabulary ─────────────────────────────────────────────────── */
export const STATUS = {
  pending:   { label: 'بانتظار التأكيد', icon: 'clock' },
  confirmed: { label: 'مؤكّد',           icon: 'check' },
  done:      { label: 'مكتمل',           icon: 'check' },
  cancelled: { label: 'ملغي',            icon: 'close' },
  rejected:  { label: 'معتذر عنه',       icon: 'close' },
  no_show:   { label: 'لم تحضر',         icon: 'close' },
};
export const statusLabel = (s) => (STATUS[s] || { label: s }).label;

/* ── Public reads (anon) ───────────────────────────────────────────────── */

// Read through the function rather than the view: the public surface should
// not hinge on a table-level grant, which is exactly what went missing in
// production and took the whole page down with it.
//
// The view is tried second so this file works against a database that has the
// migration and one that does not — the page must not depend on which of the
// two deploys landed first.
export async function getPublicSettings() {
  const viaRpc = await sb.rpc('get_public_settings');
  if (!viaRpc.error) {
    const d = viaRpc.data;
    return Array.isArray(d) ? d[0] || null : d;
  }

  const viaView = await sb.from('public_settings').select('*').maybeSingle();
  if (!viaView.error) return viaView.data;

  // Both closed: report the function's error, which names the supported path.
  throw viaRpc.error;
}

export async function getServices({ clientOnly = true } = {}) {
  let q = sb.from('services').select('*').eq('active', true).order('sort');
  if (clientOnly) q = q.eq('bookable_by_client', true);
  const { data, error } = await q;
  if (error) throw error;
  return data || [];
}

export async function getAvailableSlots(date, durationMin, excludeId = null) {
  const { data, error } = await sb.rpc('available_slots', {
    p_date: date, p_duration_min: durationMin, p_exclude: excludeId,
  });
  if (error) throw error;
  return (data || []).map((r) => (typeof r === 'string' ? r : r.slot));
}

export async function getDaysWithAvailability(from, days, durationMin) {
  const { data, error } = await sb.rpc('days_with_availability', {
    p_from: from, p_days: days, p_duration_min: durationMin,
  });
  if (error) throw error;
  return data || [];
}

/* ── إيصال العربون ──────────────────────────────────────────────────────

   المخزن خاص: العميلة ترفع ولا تقرأ، وصاحبة اللوحة تقرأ برابط موقّع
   قصير العمر. الرفع يسبق إنشاء الحجز لأن الحجز مرفوض بلا إيصال، ثم
   تربط create_booking الملفَ بالحجز داخل نفس العملية.                */

const RECEIPT_TYPES = {
  'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp',
  'image/heic': 'heic', 'image/heif': 'heic', 'application/pdf': 'pdf',
};
export const RECEIPT_ACCEPT = 'image/jpeg,image/png,image/webp,image/heic,image/heif,application/pdf';
export const RECEIPT_MAX_BYTES = 5 * 1024 * 1024;

export async function uploadReceipt(file) {
  if (!file) throw new Error('اختاري صورة التحويل أولًا');
  const ext = RECEIPT_TYPES[file.type];
  if (!ext) throw new Error('صيغة الملف غير مدعومة — أرسلي صورة أو PDF');
  if (file.size > RECEIPT_MAX_BYTES) throw new Error('حجم الملف كبير — الحد 5 ميجابايت');

  const path = `pending/${crypto.randomUUID()}.${ext}`;
  const { error } = await sb.storage.from('receipts')
    .upload(path, file, { contentType: file.type, upsert: false });
  if (error) throw new Error('تعذّر رفع الإيصال، تأكدي من الاتصال وحاولي مرة أخرى');
  return path;
}

// Supabase يمنع الحذف المباشر من جداول التخزين، فالتنظيف يمرّ بواجهته.
// القاعدة تسمّي اليتيم فقط، واللوحة تحذفه بمفتاح جلستها.
export async function purgeOrphanReceipts() {
  const { data, error } = await sb.rpc('orphan_receipts');
  if (error || !data?.length) return 0;
  const names = data.map((r) => (typeof r === 'string' ? r : r.orphan_receipts)).filter(Boolean);
  if (!names.length) return 0;
  const { error: rmErr } = await sb.storage.from('receipts').remove(names);
  if (rmErr) throw rmErr;
  return names.length;
}

/* ── وسائط الخدمة ──────────────────────────────────────────────────
   فيديو تسويقي أو صورة، تُرفع لكل خدمة وتُعرض خلف بطاقتها في صفحة
   العميلة. الدلو عامّ القراءة: هذه وسائط تُعرض لكل من يفتح الرابط،
   وتوقيعُها المؤقّت يبطئ الصفحة بلا سرٍّ يُحمى. */
const MEDIA_TYPES = {
  'image/jpeg': { ext: 'jpg',  kind: 'image' },
  'image/png':  { ext: 'png',  kind: 'image' },
  'image/webp': { ext: 'webp', kind: 'image' },
  'video/mp4':  { ext: 'mp4',  kind: 'video' },
  'video/webm': { ext: 'webm', kind: 'video' },
  'video/quicktime': { ext: 'mov', kind: 'video' },
};
export const MEDIA_ACCEPT_VIDEO = 'video/mp4,video/webm,video/quicktime';
export const MEDIA_ACCEPT_IMAGE = 'image/jpeg,image/png,image/webp';
export const MEDIA_MAX_BYTES = 25 * 1024 * 1024;

export async function uploadServiceMedia(file, want) {
  if (!file) throw new Error('اختاري الملف أولًا');
  const t = MEDIA_TYPES[file.type];
  if (!t) throw new Error('صيغة الملف غير مدعومة — MP4 أو WebM للفيديو، JPG أو PNG للصورة');
  if (want && t.kind !== want) {
    throw new Error(want === 'video' ? 'هذا ليس ملف فيديو' : 'هذه ليست صورة');
  }
  if (file.size > MEDIA_MAX_BYTES) throw new Error('حجم الملف كبير — الحد 25 ميجابايت');

  const path = `svc/${crypto.randomUUID()}.${t.ext}`;
  const { error } = await sb.storage.from('service-media')
    .upload(path, file, { contentType: file.type, upsert: false });
  if (error) throw new Error('تعذّر الرفع، تأكدي من الاتصال وحاولي مرة أخرى');
  return { path, kind: t.kind };
}

/* الرابط العامّ يُبنى مرّةً بلا نداء شبكة — الدلو عامّ فلا توقيع. */
export function mediaUrl(path) {
  if (!path) return null;
  const { data } = sb.storage.from('service-media').getPublicUrl(path);
  return data?.publicUrl || null;
}

export async function removeServiceMedia(paths) {
  const list = (Array.isArray(paths) ? paths : [paths]).filter(Boolean);
  if (!list.length) return 0;
  const { error } = await sb.storage.from('service-media').remove(list);
  if (error) throw error;
  return list.length;
}

// للوحة التحكم وحدها: رابط مؤقت لعرض الإيصال.
export async function receiptUrl(path, seconds = 300) {
  if (!path) return null;
  const { data, error } = await sb.storage.from('receipts').createSignedUrl(path, seconds);
  if (error) throw error;
  return data?.signedUrl || null;
}

/* العربون: مبلغ ثابت تضعه صاحبة العمل بجانب كل خدمة، يُجمع على من
   اختارتهم العميلة — عنصر لكل شخص — ولا يتجاوز المستحقّ بعد الخصم.
   الرقم هنا للعرض فقط؛ الخادم يعيد حسابه من قاعدة البيانات عند الحجز. */
export const depositFor = (services, dueTotal) => {
  const sum = (services || []).reduce((n, s) => n + Number(s?.deposit_amount || 0), 0);
  const cap = Number(dueTotal ?? Infinity);
  return Math.max(0, Math.min(Math.round(sum), isFinite(cap) ? cap : Math.round(sum)));
};

/* يُبقى للتوافق مع نسخة قديمة من اللوحة قد تكون مفتوحة في تبويب. */
export const depositDue = (price, rate) =>
  Math.round(Number(price || 0) * Number(rate ?? 0.25));

/* يطلب من الخادم قراءة صورة الإيصال وتسجيل ما فيها. لا يُرجع حكمًا
   مُلزِمًا — الحكم في create_booking — لكنه يخبر العميلة مبكرًا إن كانت
   الصورة لا تصلح، فلا تكتشف ذلك بعد ملء كل شيء. */
export async function verifyReceipt(path) {
  try {
    const { data, error } = await sb.functions.invoke('verify-receipt', { body: { path } });
    if (error) return { ok: false, reason: 'unreachable' };
    return data || { ok: false, reason: 'empty' };
  } catch {
    return { ok: false, reason: 'unreachable' };
  }
}

export async function createBooking(payload) {
  const { data, error } = await sb.rpc('create_booking', {
    p_client_name:  payload.name,
    p_client_phone: payload.phone,
    p_date:         payload.date,
    p_time:         payload.time,
    p_service_ids:  payload.serviceIds,
    p_person_names: payload.personNames || null,
    p_loc_text:     payload.locText || null,
    p_loc_map:      payload.locMap || null,
    p_notes:        payload.notes || null,
    p_receipt_path: payload.receiptPath || null,
  });
  if (error) throw error;
  return Array.isArray(data) ? data[0] : data;
}

export async function getBookingByToken(token) {
  const { data, error } = await sb.rpc('get_booking_by_token', { p_token: token });
  if (error) throw error;
  return Array.isArray(data) ? data[0] || null : data;
}

export async function requestCancel(token) {
  const { data, error } = await sb.rpc('request_cancel', { p_token: token });
  if (error) throw error;
  return data === true;
}

/* ── Admin (requires a session) ────────────────────────────────────────── */

/* ── الشبكة المتقطّعة ───────────────────────────────────────────────────
   على شبكة الجوّال يسقط الطلب أحيانًا قبل أن يصل، فيرمي المتصفّح خطأً بلا
   معنى للمستخدمة: سفاري يقول "Load failed" وكروم يقول "Failed to fetch".
   ما يلي يميّز هذا السقوط عن رفضٍ حقيقي من الخادم، فيُعيد المحاولة مرّتين
   بصمت ثمّ يشرح بالعربية إن أصرّ الانقطاع. الكتابة التي تُعاد ذرّيّةٌ
   ومحميّة بمفتاح تكرار، فالإعادة لا تُنتج حجزًا ثانيًا. */
export function isOffline(err) {
  const m = String(err?.message || err || '').toLowerCase();
  return m.includes('load failed') || m.includes('failed to fetch')
      || m.includes('networkerror') || m.includes('network request failed')
      || m.includes('the internet connection appears to be offline')
      || m.includes('timeout') || m.includes('aborted');
}

export const NET_MSG =
  'تعذّر الوصول للإنترنت. تأكّدي من الاتصال ثم أعيدي المحاولة — لن يتكرّر الحجز.';

/** يعيد المحاولة على الانقطاع وحده. أخطاء الخادم تمرّ كما هي فورًا. */
export async function retrying(fn, tries = 3) {
  for (let i = 1; ; i++) {
    try {
      return await fn();
    } catch (e) {
      if (!isOffline(e)) throw e;
      if (i >= tries) { const err = new Error(NET_MSG); err.offline = true; throw err; }
      await new Promise((r) => setTimeout(r, 700 * i));
    }
  }
}

export const uuid = () => (crypto?.randomUUID
  ? crypto.randomUUID()
  : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    }));

/* ── النسخ الاحتياطي ────────────────────────────────────────────────────
   لقطةٌ كاملة تُحفظ في تخزين المشروع نفسه، باسمٍ هو تاريخها ووقتها. صور
   الإيصالات تُنسخ معها في دلوٍ منفصل، لأنّ كانس الملفّات اليتيمة يمسح ما
   لا يشير إليه حجزٌ قائم — فنسخةٌ داخل دلو الإيصالات كانت ستُمحى وحدها.

   والاستعادة تُرجع المفقود ولا تمسّ الموجود: هذا شرطٌ لا مساومة فيه، لأنّ
   أسوأ ما قد تفعله ميزةُ إنقاذ أن تصير هي الكارثة. */

const BK = 'backups';
const SNAP_DIR = 'snapshots';
const FILE_DIR = 'files';

/** 2026-08-22_2247 — يُقرأ كتاريخ ويُرتَّب كنصّ. */
function stamp(d = new Date()) {
  const p2 = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`
       + `_${p2(d.getHours())}${p2(d.getMinutes())}`;
}

/** يقرأ الوقت من اسم الملف نفسه، فلا يعتمد على بيانات التخزين الوصفية. */
export function backupDate(name) {
  const m = /^(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})/.exec(name || '');
  if (!m) return null;
  return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
}

export const backups = {
  /** لقطة جديدة. `auto` تُعلّم النسخة التي أخذها النظام قبل حذفٍ جماعي. */
  async create({ auto = false } = {}) {
    const { data: snap, error } = await sb.rpc('admin_snapshot');
    if (error) throw error;

    const base = `${stamp()}${auto ? '-auto' : ''}`;
    const body = new Blob([JSON.stringify(snap)], { type: 'application/json' });
    const up = await sb.storage.from(BK)
      .upload(`${SNAP_DIR}/${base}.json`, body, { contentType: 'application/json', upsert: true });
    if (up.error) throw up.error;

    // الصور محاولةٌ حسنة النيّة: فشل نسخة لا يُسقط النسخة الاحتياطية كلّها.
    const paths = (snap.bookings || []).map((b) => b.receipt_path).filter(Boolean);
    let copied = 0;
    for (const path of paths) {
      try {
        const r = await sb.storage.from('receipts')
          .copy(path, `${FILE_DIR}/${base}/${path}`, { destinationBucket: BK });
        if (!r.error) copied += 1;
      } catch { /* صورة واحدة لا تُفسد اللقطة */ }
    }
    return { name: `${base}.json`, counts: snap.counts || {}, receipts_copied: copied,
             receipts_total: paths.length };
  },

  async list() {
    const { data, error } = await sb.storage.from(BK)
      .list(SNAP_DIR, { limit: 100, sortBy: { column: 'name', order: 'desc' } });
    if (error) throw error;
    return (data || [])
      .filter((f) => f.name.endsWith('.json'))
      .map((f) => ({
        name: f.name,
        base: f.name.replace(/\.json$/, ''),
        auto: f.name.includes('-auto'),
        at: backupDate(f.name),
        size: f.metadata?.size || 0,
      }));
  },

  async read(name) {
    const { data, error } = await sb.storage.from(BK).download(`${SNAP_DIR}/${name}`);
    if (error) throw error;
    return JSON.parse(await data.text());
  },

  /** يعيد الصفوف ثمّ الصور. الصور تُنسخ ولا تُستبدل: الموجود أحدث. */
  async restore(name, { includeSettings = false } = {}) {
    const snap = await this.read(name);
    const { data, error } = await sb.rpc('admin_restore_snapshot', {
      p_data: snap, p_include_settings: includeSettings,
    });
    if (error) throw error;

    const base = name.replace(/\.json$/, '');
    const paths = (snap.bookings || []).map((b) => b.receipt_path).filter(Boolean);
    let back = 0;
    for (const path of paths) {
      try {
        const r = await sb.storage.from(BK)
          .copy(`${FILE_DIR}/${base}/${path}`, path, { destinationBucket: 'receipts' });
        if (!r.error) back += 1;
      } catch { /* موجودة أصلًا، أو لم تُنسخ يوم اللقطة */ }
    }
    return { ...(data || {}), receipts_restored: back };
  },

  async remove(name) {
    const base = name.replace(/\.json$/, '');
    const { data: files } = await sb.storage.from(BK).list(`${FILE_DIR}/${base}/pending`, { limit: 1000 });
    const kids = (files || []).map((f) => `${FILE_DIR}/${base}/pending/${f.name}`);
    if (kids.length) { try { await sb.storage.from(BK).remove(kids); } catch { /* لاحقًا */ } }
    const { error } = await sb.storage.from(BK).remove([`${SNAP_DIR}/${name}`]);
    if (error) throw error;
  },

  async link(name, seconds = 300) {
    const { data, error } = await sb.storage.from(BK)
      .createSignedUrl(`${SNAP_DIR}/${name}`, seconds, { download: name });
    if (error) throw error;
    return data.signedUrl;
  },
};

/* ── رسائل التواصل ──────────────────────────────────────────────────────
   القوالب صارت صفوفًا في القاعدة تملكها إيمان، لا نصوصًا محفورة في الكود.
   والحقول بين قوسين معقوفين تُبدَّل هنا عند الإرسال: بدونها تكتب اسم كل
   عميلة بيدها في كل مرّة، وقالبٌ كهذا يُهجَر بعد ثالث استعمال. */

export const TEMPLATE_FIELDS = [
  '{الاسم}', '{التاريخ}', '{الوقت}', '{الخدمة}', '{الإجمالي}',
  '{العربون}', '{المتبقي}', '{الموقع}', '{رابط الحجز}', '{الاسم التجاري}',
];

export function fillTemplate(body, b = {}, extra = {}) {
  const items = b.booking_items || b.items || [];
  const due = Number(b.price || 0) - Number(b.deposit || 0);
  const map = {
    '{الاسم}':          b.client_name || '',
    '{التاريخ}':        b.the_date ? fmtDate(b.the_date) : '',
    '{الوقت}':          b.start_time ? fmtTime(b.start_time) : '',
    '{الخدمة}':         items.map((i) => i.service_name).filter(Boolean).join(' + '),
    '{الإجمالي}':       riyal(b.price || 0),
    '{العربون}':        riyal(b.deposit || 0),
    '{المتبقي}':        riyal(Math.max(due, 0)),
    '{الموقع}':         b.loc_text || '',
    '{رابط الحجز}':     extra.link || '',
    '{الاسم التجاري}':  extra.business || CFG.BUSINESS_NAME || '',
  };
  // الحقل غير المعروف يبقى كما هو بدل أن يُمحى: خطؤها يجب أن يُرى لا يُبتلع.
  return String(body || '').replace(/\{[^}]{1,24}\}/g, (m) => (m in map ? map[m] : m));
}

export const admin = {
  async signIn(email, password) {
    const { data, error } = await sb.auth.signInWithPassword({ email, password });
    if (error) throw error;
    return data;
  },
  signOut: () => sb.auth.signOut(),
  async session() {
    const { data } = await sb.auth.getSession();
    return data.session;
  },

  async bookings({ from, to, statuses, search, limit = 300 } = {}) {
    let q = sb.from('bookings')
      .select('*, booking_items(*)')
      .order('the_date', { ascending: true })
      .order('start_time', { ascending: true })
      .limit(limit);
    if (from) q = q.gte('the_date', from);
    if (to) q = q.lte('the_date', to);
    if (statuses?.length) q = q.in('status', statuses);
    if (search) {
      const phone = normalisePhone(search);
      q = phone ? q.eq('client_phone', phone) : q.ilike('client_name', `%${search}%`);
    }
    const { data, error } = await q;
    if (error) throw error;
    return data || [];
  },

  async booking(id) {
    const { data, error } = await sb.from('bookings')
      .select('*, booking_items(*)').eq('id', id).maybeSingle();
    if (error) throw error;
    return data;
  },

  async update(id, patch) {
    const { data, error } = await sb.from('bookings').update(patch).eq('id', id).select().maybeSingle();
    if (error) throw error;
    return data;
  },

  async setStatus(id, status, extra = {}) {
    const patch = { status, ...extra };
    if (status === 'confirmed') patch.confirmed_at = new Date().toISOString();
    if (status === 'done') patch.completed_at = new Date().toISOString();
    const row = await admin.update(id, patch);
    await admin.log(id, `status:${status}`);
    return row;
  },

  async log(bookingId, action, detail = null) {
    await sb.from('activity_log').insert({ booking_id: bookingId, actor: 'admin', action, detail });
  },

  /* الحجز وبنوده صفقةٌ واحدة في القاعدة. كانا طلبين، فكان انقطاعٌ بينهما
     يترك في الأجندة حجزًا بلا خدمات ولا سعر. والمفتاح يجعل الإعادة آمنة:
     إن كان الطلب قد وصل ونُفّذ وضاع جوابه، رُدّ الحجز نفسه لا حجزٌ ثانٍ. */
  async createBooking(row, items, idem = uuid()) {
    return retrying(async () => {
      const { data, error } = await sb.rpc('admin_create_booking', {
        p_booking: row, p_items: items, p_idem: idem,
      });
      if (error) throw error;
      return Array.isArray(data) ? data[0] : data;
    });
  },

  async replaceItems(bookingId, items, discountPerPerson = null) {
    return retrying(async () => {
      const { data, error } = await sb.rpc('admin_replace_items', {
        p_booking_id: bookingId, p_items: items,
        p_discount_per_person: discountPerPerson,
      });
      if (error) throw error;
      return Array.isArray(data) ? data[0] : data;
    });
  },

  async templates() {
    const { data, error } = await sb.from('message_templates')
      .select('*').eq('active', true).order('pinned', { ascending: false })
      .order('sort').order('created_at');
    if (error) throw error;
    return data || [];
  },
  async saveTemplate(row) {
    const { data, error } = await sb.from('message_templates').upsert(row).select().maybeSingle();
    if (error) throw error;
    return data;
  },
  async deleteTemplate(id) {
    // المدمجة تُخفى ولا تُحذف: حذفها يعني ضياع نصٍّ لا تملك استعادته.
    const { error } = await sb.from('message_templates').update({ active: false }).eq('id', id);
    if (error) throw error;
  },

  async services() {
    const { data, error } = await sb.from('services').select('*').order('sort');
    if (error) throw error;
    return data || [];
  },
  async saveService(row) {
    const { data, error } = await sb.from('services').upsert(row).select().maybeSingle();
    if (error) throw error;
    return data;
  },
  /* الحذف الجماعي: معاينة تعدّ ولا تمسّ شيئًا، ثم تنفيذ يحذف ويرجع
     مسارات الإيصالات لتُمحى من التخزين — القاعدة تمنع حذفها مباشرة. */
  async purgePreview(from = null, to = null) {
    const { data, error } = await sb.rpc('admin_purge_bookings',
      { p_from: from, p_to: to, p_dry: true });
    if (error) throw error;
    const row = Array.isArray(data) ? data[0] : data;
    return { count: Number(row?.affected || 0), receipts: row?.receipts || [] };
  },
  async purgeBookings(from = null, to = null) {
    const { data, error } = await sb.rpc('admin_purge_bookings',
      { p_from: from, p_to: to, p_dry: false });
    if (error) throw error;
    const row = Array.isArray(data) ? data[0] : data;
    const files = (row?.receipts || []).filter(Boolean);
    // فشل محو الملفات لا يُبطل الحذف — الحجوزات ذهبت، والملفات تصير يتيمة
    // ويلتقطها تنظيف اليتامى في الفتح التالي.
    if (files.length) { try { await sb.storage.from('receipts').remove(files); } catch { /* لاحقًا */ } }
    return { count: Number(row?.affected || 0), files: files.length };
  },
  async deleteService(id) {
    // Soft delete: existing bookings snapshot their own service details, but
    // keeping the row means historical reports still resolve the reference.
    const { error } = await sb.from('services').update({ active: false }).eq('id', id);
    if (error) throw error;
  },

  async rules() {
    const { data, error } = await sb.from('availability_rules')
      .select('*').order('weekday').order('start_time');
    if (error) throw error;
    return data || [];
  },
  async saveRule(row) {
    const { data, error } = await sb.from('availability_rules').upsert(row).select().maybeSingle();
    if (error) throw error;
    return data;
  },
  async deleteRule(id) {
    const { error } = await sb.from('availability_rules').delete().eq('id', id);
    if (error) throw error;
  },

  async overrides(from, to) {
    let q = sb.from('date_overrides').select('*').order('the_date');
    if (from) q = q.gte('the_date', from);
    if (to) q = q.lte('the_date', to);
    const { data, error } = await q;
    if (error) throw error;
    return data || [];
  },
  async saveOverride(row) {
    const { data, error } = await sb.from('date_overrides').upsert(row).select().maybeSingle();
    if (error) throw error;
    return data;
  },
  async deleteOverride(id) {
    const { error } = await sb.from('date_overrides').delete().eq('id', id);
    if (error) throw error;
  },

  async settings() {
    const { data, error } = await sb.from('settings').select('*').eq('id', 1).maybeSingle();
    if (error) throw error;
    return data;
  },
  async saveSettings(patch) {
    const { data, error } = await sb.from('settings')
      .update({ ...patch, updated_at: new Date().toISOString() }).eq('id', 1).select().maybeSingle();
    if (error) throw error;
    return data;
  },

  /** New requests arrive without a refresh. Realtime honours RLS, so only a
   *  signed-in admin ever receives these rows. */
  onBookingChange(handler) {
    const ch = sb.channel('bookings-live')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'bookings' },
          (payload) => handler(payload))
      .subscribe();
    return () => sb.removeChannel(ch);
  },

  /** Everything, as one JSON file. localStorage taught this system the hard
   *  way that a store with no export is a store you will eventually lose. */
  async exportAll() {
    const [bookings, items, services, rules, overrides, settings] = await Promise.all([
      sb.from('bookings').select('*'),
      sb.from('booking_items').select('*'),
      sb.from('services').select('*'),
      sb.from('availability_rules').select('*'),
      sb.from('date_overrides').select('*'),
      sb.from('settings').select('*'),
    ]);
    return {
      exported_at: new Date().toISOString(),
      schema: 1,
      bookings: bookings.data || [],
      booking_items: items.data || [],
      services: services.data || [],
      availability_rules: rules.data || [],
      date_overrides: overrides.data || [],
      settings: settings.data || [],
    };
  },
};

/* ── WhatsApp message templates ────────────────────────────────────────────
   One tap, already written. The previous system opened an empty chat and left
   the artist to type the same Arabic paragraph every time.
   ------------------------------------------------------------------------ */
export const templates = {
  confirm: (b, link) =>
    `أهلاً ${b.client_name} 🌸\nتم تأكيد موعدك مع ${CFG.BUSINESS_NAME}:\n\n`
    + `📅 ${fmtDate(b.the_date)}\n🕐 ${fmtTime(b.start_time)}\n`
    + `💄 ${(b.booking_items || []).map((i) => i.service_name).join(' + ')}\n`
    + `💰 الإجمالي: ${riyal(b.price)}${Number(b.deposit) > 0 ? `\n✅ العربون المستلم: ${riyal(b.deposit)}\n⏳ المتبقي: ${riyal(b.price - b.deposit)}` : ''}\n`
    + (link ? `\nلمتابعة حجزك:\n${link}` : '')
    + `\n\nبانتظارك 💗`,

  reminder: (b) =>
    `تذكير بموعدك غدًا مع ${CFG.BUSINESS_NAME} 🌸\n\n`
    + `📅 ${fmtDate(b.the_date)}\n🕐 ${fmtTime(b.start_time)}\n`
    + `${b.loc_text ? `📍 ${b.loc_text}\n` : ''}`
    + `${Number(b.price - b.deposit) > 0 ? `\nالمتبقي: ${riyal(b.price - b.deposit)}` : ''}`
    + `\n\nنراكِ غدًا 💗`,

  // العربون محسوب ومخزَّن مع الحجز، فلا يفترق ما يقوله القالب عمّا في اللوحة.
  deposit: (b) =>
    `أهلاً ${b.client_name} 🌸\nلتثبيت موعدك بتاريخ ${fmtDate(b.the_date)} الساعة ${fmtTime(b.start_time)}، `
    + `يلزم عربون ${riyal(Number(b.deposit_due || 0))} من إجمالي ${riyal(b.price)}.\n\nشاكرين لكِ 💗`,

  thanks: (b) =>
    `شكرًا لثقتك ${b.client_name} 🌸\nسعدنا بخدمتك اليوم.\n\n`
    + `إن أعجبك العمل نتشرف بتقييمك ومشاركة صورك معنا 💗`,

  reject: (b) =>
    `أهلاً ${b.client_name} 🌸\nنعتذر، موعد ${fmtDate(b.the_date)} الساعة ${fmtTime(b.start_time)} `
    + `غير متاح حاليًا.\n\nيسعدنا اقتراح موعد آخر يناسبك 💗`,

  driverDay: (bookings, dateStr) =>
    `خطة اليوم — ${fmtDate(dateStr)}\n\n`
    + bookings.map((b, i) =>
        `${i + 1}) ${fmtTime(b.start_time)} — ${b.client_name}\n`
        + `${b.loc_text ? `   ${b.loc_text}\n` : ''}`
        + `${b.loc_map ? `   ${b.loc_map}\n` : ''}`).join('\n'),

  driverOne: (b) =>
    `موقع العميلة: ${b.client_name}\n`
    + `الموعد: ${fmtDate(b.the_date)} — ${fmtTime(b.start_time)}\n`
    + `${b.loc_text ? `${b.loc_text}\n` : ''}${b.loc_map || ''}`,
};

/* ── Small UI utilities shared by both surfaces ────────────────────────── */

let toastHost = null;
export function toast(message, kind = '') {
  if (!toastHost) {
    toastHost = document.createElement('div');
    toastHost.className = 'toast-stack';
    toastHost.setAttribute('role', 'status');
    toastHost.setAttribute('aria-live', 'polite');
    document.body.appendChild(toastHost);
  }
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = message;
  toastHost.appendChild(el);
  // Each toast owns its own timer, so a burst queues instead of clobbering.
  setTimeout(() => {
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 260);
  }, 3200);
}

/** Opens a sheet with focus handling: Escape closes, focus is trapped while
 *  open and restored to whatever opened it. */
export function openSheet(el) {
  const opener = document.activeElement;
  el.classList.add('open');
  el.removeAttribute('hidden');
  document.body.style.overflow = 'hidden';
  /* الصفحة تتنحّى فيظهر خلف الورقة مشهدُ الساعة نفسه لا بطاقاتٌ مطموسة:
     تقرأ صاحبته التفاصيل وخلفها سماؤها. تعود الصفحة متى أُغلقت. */
  document.body.classList.add('sheeting');

  const focusables = () => el.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  setTimeout(() => focusables()[0]?.focus(), 60);

  function onKey(e) {
    if (e.key === 'Escape') { close(); return; }
    if (e.key !== 'Tab') return;
    const items = Array.from(focusables()).filter((n) => !n.disabled && n.offsetParent !== null);
    if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  function onClick(e) { if (e.target === el) close(); }

  function close() {
    el.classList.remove('open');
    document.body.style.overflow = '';
    document.body.classList.remove('sheeting');
    document.removeEventListener('keydown', onKey);
    el.removeEventListener('click', onClick);
    setTimeout(() => { el.setAttribute('hidden', ''); opener?.focus?.(); }, 260);
  }

  document.addEventListener('keydown', onKey);
  el.addEventListener('click', onClick);
  el._close = close;
  return close;
}

export function closeSheet(el) { el?._close?.(); }

export function download(filename, text, type = 'application/json') {
  const blob = new Blob([text], { type: `${type};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a);
  a.click();
  // Revoking synchronously cancels the download in some browsers.
  setTimeout(() => { a.remove(); URL.revokeObjectURL(url); }, 2000);
}

/** RFC 4180 CSV: quote every field, double inner quotes. A comma in an
 *  address used to shift every column after it. */
export function toCSV(rows, headers) {
  const q = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const head = headers.map((h) => q(h.label)).join(',');
  const body = rows.map((r) => headers.map((h) => q(h.get(r))).join(',')).join('\r\n');
  return `﻿${head}\r\n${body}`;
}
