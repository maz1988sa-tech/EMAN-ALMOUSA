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

  async createBooking(row, items) {
    const { data, error } = await sb.from('bookings')
      .insert({ ...row, source: 'admin' }).select().maybeSingle();
    if (error) throw error;
    const payload = items.map((it, i) => ({ ...it, booking_id: data.id, sort: i + 1 }));
    const { error: e2 } = await sb.from('booking_items').insert(payload);
    if (e2) throw e2;
    return data;
  },

  async replaceItems(bookingId, items) {
    const { error: delErr } = await sb.from('booking_items').delete().eq('booking_id', bookingId);
    if (delErr) throw delErr;
    if (!items.length) return;
    const { error } = await sb.from('booking_items')
      .insert(items.map((it, i) => ({ ...it, booking_id: bookingId, sort: i + 1 })));
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

  deposit: (b) =>
    `أهلاً ${b.client_name} 🌸\nلتثبيت موعدك بتاريخ ${fmtDate(b.the_date)} الساعة ${fmtTime(b.start_time)}، `
    + `يلزم عربون ${riyal(Math.round(b.price / 4))} من إجمالي ${riyal(b.price)}.\n\nشاكرين لكِ 💗`,

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
