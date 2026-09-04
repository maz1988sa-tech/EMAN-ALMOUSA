// فحص إيصال العربون: يقرأ الصورة المرفوعة ويسجّل ما رآه فيها.
//
// الحكم ليس هنا بل في receipt_state داخل القاعدة، حيث يُحسب العربون من
// الخدمات لا مما أرسله المتصفّح. وهذه تقرأ وتسجّل فقط.
//
// وشرطان يجتمعان هناك: آيبان صاحبة العمل، ومبلغٌ يبلغ العربون. كانت
// الكلمات وحدها تكفي، ففاتورة سينما فيها SAR ورقمٌ كبير مرّت. فصار
// الآيبان شرطًا لا قرينة — وهو الدليل الذي لا تحمله صورةٌ من مكانٍ آخر.
//
// ملاحظة على اللغة: المفتاح المجاني لدى مزوّد القراءة لا يقبل العربية
// (يردّ E201 على language=ara مهما كان المحرّك). فالقراءة تجري بالمحرّك ٣
// الذي يكتشف النصّ تلقائيًا ويقرأ الأرقام اللاتينية بدقّة — وهي ما يهمّنا.
// وعوّضنا غياب العربية بدليل لا لغة له: الآيبان. إيصال تحويل حقيقي إلى
// حساب صاحبة العمل يحمل آيبانها، وهو أقوى دلالة من كلمة «تحويل».
import 'jsr:@supabase/functions-js/edge-runtime.d.ts';
import { createClient } from 'jsr:@supabase/supabase-js@2';

const PATH_RE = /^pending\/[0-9a-f-]{36}\.(jpg|jpeg|png|webp|heic|pdf)$/;
const MAX_BYTES = 1024 * 1024;
const IBAN_TAIL_DEFAULT = 6;  // يُضبَط من الإعدادات: أقصر يسامح خطأ القراءة، وأطول يشدّد

/* كلمات تدلّ على إيصال. العربية تُبقى لأن المحرّك ٣ يلتقط بعضها،
   واللاتينية هي الأوثق ما دامت العربية غير مدعومة. */
const KEYWORDS = [
  'تحويل', 'حواله', 'حوالة', 'حولت', 'مبلغ', 'ريال', 'سعودي', 'عملية',
  'مدفوع', 'سداد', 'ايصال', 'إيصال', 'المستفيد', 'حساب', 'مرجع', 'بنك',
  'الراجحي', 'الاهلي', 'الانماء', 'البلاد',
  'transfer', 'transaction', 'trx', 'amount', 'paid', 'payment', 'receipt',
  'successful', 'success', 'completed', 'sar', 'sr', 'iban', 'beneficiary',
  'reference', 'ref', 'balance', 'rajhi', 'alrajhi', 'snb', 'ncb', 'inma',
  'alinma', 'albilad', 'riyad', 'anb', 'sab', 'stc', 'urpay', 'bank',
];

const AR = '٠١٢٣٤٥٦٧٨٩', FA = '۰۱۲۳۴۵۶۷۸۹';
const toLatin = (s: string) =>
  s.replace(/[٠-٩۰-۹]/g, (d) => {
    const i = AR.indexOf(d);
    return String(i >= 0 ? i : FA.indexOf(d));
  });

/** المبالغ المحتملة. تُستبعد السلاسل التي تتجاوز ستّ خانات صحيحة —
 *  الآيبان ورقم العملية ورقم الجوال — ويُميَّز ما جاور عملة أو حمل كسورًا. */
function extractAmounts(raw: string) {
  const t = toLatin(raw).replace(/[٬⁦-⁩‎‏]/g, '');
  const numbers: number[] = [], strong: number[] = [];
  const re = /(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d{1,7})(?:[.٫](\d{1,2}))?(?![\d])/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(t)) !== null) {
    const intPart = m[1].replace(/,/g, '');
    if (intPart.length > 6) continue;
    const val = Number(intPart) + (m[2] ? Number(`0.${m[2]}`) : 0);
    if (!isFinite(val) || val <= 0 || val > 1_000_000) continue;
    numbers.push(val);
    const around = t.slice(Math.max(0, m.index - 16), m.index + m[0].length + 16).toLowerCase();
    if (m[2] || /ر\.?\s?س|ريال|sar|﷼|\bsr\b/.test(around)) strong.push(val);
  }
  return {
    numbers: [...new Set(numbers)].sort((a, b) => b - a).slice(0, 40),
    strong:  [...new Set(strong)].sort((a, b) => b - a).slice(0, 20),
  };
}

const found = (t: string) => {
  const low = toLatin(t).toLowerCase();
  return [...new Set(KEYWORDS.filter((k) => low.includes(k)))].slice(0, 24);
};

/** هل يحمل النصّ آيبان صاحبة العمل؟ تُجرَّد كل الفواصل والمسافات من
 *  الجانبين، ثم يُبحث عن ذيل الآيبان — فلا يضرّ خطأ قراءة في أوّله. */
function ibanSeen(text: string, iban: string | null, tail: number) {
  if (!iban) return false;
  const want = toLatin(iban).replace(/\D/g, '');
  if (want.length < tail) return false;
  const hay = toLatin(text).replace(/\D/g, '');
  return hay.includes(want.slice(-tail));
}

async function ocr(key: string, bytes: Uint8Array, ext: string) {
  const type = ext === 'pdf' ? 'application/pdf'
    : ext === 'png' ? 'image/png'
    : ext === 'webp' ? 'image/webp' : 'image/jpeg';
  const form = new FormData();
  form.append('apikey', key);
  // المحرّك قبل اللغة: الخدمة تتحقّق من اللغة مقابل المحرّك السائد لحظة قراءتها.
  form.append('OCREngine', '3');
  form.append('scale', 'true');
  form.append('detectOrientation', 'true');
  form.append('isOverlayRequired', 'false');
  form.append('file', new Blob([bytes], { type }), `receipt.${ext}`);
  const res = await fetch('https://api.ocr.space/parse/image', {
    method: 'POST', headers: { apikey: key }, body: form,
  });
  const raw = await res.text();
  if (!res.ok) throw new Error(`http_${res.status}: ${raw.slice(0, 300)}`);
  let j: Record<string, unknown>;
  try { j = JSON.parse(raw); } catch { throw new Error(`bad_json: ${raw.slice(0, 300)}`); }
  if (j.IsErroredOnProcessing) {
    const em = j.ErrorMessage;
    throw new Error(`ocr: ${Array.isArray(em) ? em.join(' | ') : String(em ?? j.ErrorDetails ?? 'unknown')}`);
  }
  const results = (j.ParsedResults ?? []) as Array<{ ParsedText?: string }>;
  return results.map((r) => r.ParsedText ?? '').join('\n');
}

Deno.serve(async (req) => {
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
    'Content-Type': 'application/json',
  };
  if (req.method === 'OPTIONS') return new Response('ok', { headers: cors });

  const reply = (body: Record<string, unknown>, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: cors });

  try {
    const payload = await req.json().catch(() => ({}));
    const path = payload?.path;
    if (typeof path !== 'string' || !PATH_RE.test(path)) {
      return reply({ ok: false, reason: 'bad_path' }, 400);
    }

    const db = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
      { auth: { persistSession: false } },
    );

    const key = Deno.env.get('OCR_API_KEY');
    if (!key) {
      await db.from('receipt_scans').upsert({ path, engine: 'none', error: 'OCR_API_KEY not set' });
      return reply({ ok: true, skipped: true, reason: 'no_key' });
    }

    const dl = await db.storage.from('receipts').download(path);
    if (dl.error || !dl.data) return reply({ ok: false, reason: 'not_found' }, 404);
    const bytes = new Uint8Array(await dl.data.arrayBuffer());
    if (bytes.byteLength > MAX_BYTES) {
      await db.from('receipt_scans').upsert({ path, engine: 'too_large', error: `${bytes.byteLength} bytes` });
      return reply({ ok: false, reason: 'too_large' });
    }

    const ext = path.split('.').pop()!.toLowerCase();
    let text = '';
    try {
      text = await ocr(key, bytes, ext);
    } catch (e) {
      const detail = String(e instanceof Error ? e.message : e).slice(0, 500);
      console.error('ocr_failed', detail);
      await db.from('receipt_scans').upsert({ path, engine: 'failed', error: detail });
      return reply({ ok: false, reason: 'ocr_failed', detail });
    }

    const { data: cfg } = await db.from('settings')
      .select('iban, receipt_iban_digits').eq('id', 1).maybeSingle();
    const tail = Math.min(24, Math.max(5, Number(cfg?.receipt_iban_digits) || IBAN_TAIL_DEFAULT));
    const iban_hit = ibanSeen(text, cfg?.iban ?? null, tail);
    const { numbers, strong } = extractAmounts(text);
    const keywords = found(text);

    await db.from('receipt_scans').upsert({
      path,
      numbers: strong.length ? strong : numbers,
      all_numbers: numbers,
      keywords,
      iban_hit,
      text_len: text.trim().length,
      engine: 'ocrspace',
      error: null,
      // النصّ الخام يُحفظ مقصوصًا: يُغني عن تخمين سبب الرفض حين تشتكي عميلة.
      raw_text: text.trim().slice(0, 4000) || null,
    });

    // ما يعود إلى المتصفّح لا يحمل حكمًا: الحكم في القاعدة، والمتصفّح
    // يسألها عنه. فلا يتعلّم أحدٌ من الجواب أيَّ شرطٍ سقط.
    return reply({ ok: true, textLen: text.trim().length });
  } catch (e) {
    return reply({ ok: false, reason: 'server_error', detail: String(e) }, 500);
  }
});
