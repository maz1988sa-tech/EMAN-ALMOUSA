// فحص إيصال العربون: يقرأ الصورة المرفوعة ويسجّل ما رآه فيها.
//
// الدالة لا تحكم بقبول الحجز ولا ترفضه — تسجّل الأرقام والكلمات التي
// عثرت عليها في جدول receipt_scans، وقرار القبول يبقى في create_booking
// حيث يُحسب العربون الحقيقي من قاعدة البيانات. المتصفّح لا يُصدَّق في
// مبلغ ولا في نتيجة، فلا يستطيع أن يمرّر صورة بادّعاء أنها فُحصت.
import 'jsr:@supabase/functions-js/edge-runtime.d.ts';
import { createClient } from 'jsr:@supabase/supabase-js@2';

const PATH_RE = /^pending\/[0-9a-f-]{36}\.(jpg|jpeg|png|webp|heic|pdf)$/;
const MAX_BYTES = 1024 * 1024;             // حدّ مزوّد القراءة المجاني

/* كلمات تدلّ على أن الصورة إيصال تحويل لا لقطة عشوائية. */
const KEYWORDS = [
  'تحويل', 'حواله', 'حوالة', 'حولت', 'حوّلت', 'محول', 'تحويلات',
  'مبلغ', 'المبلغ', 'ريال', 'سعودي', 'عمليه', 'عملية', 'ناجحه', 'ناجحة',
  'مدفوع', 'سداد', 'دفع', 'ايصال', 'إيصال', 'اشعار', 'إشعار',
  'المستفيد', 'مستفيد', 'حساب', 'ايبان', 'آيبان', 'مرجع', 'رقم العملية',
  'بنك', 'الراجحي', 'الاهلي', 'الأهلي', 'الانماء', 'الإنماء', 'البلاد',
  'الجزيره', 'الجزيرة', 'ساب', 'العربي', 'stc', 'urpay', 'alrajhi', 'snb',
  'transfer', 'transaction', 'amount', 'paid', 'payment', 'receipt',
  'successful', 'success', 'sar', 'iban', 'beneficiary',
];

const AR = '٠١٢٣٤٥٦٧٨٩', FA = '۰۱۲۳۴۵۶۷۸۹';
const toLatin = (s: string) =>
  s.replace(/[٠-٩۰-۹]/g, (d) => {
    const i = AR.indexOf(d);
    return String(i >= 0 ? i : FA.indexOf(d));
  });

/** يستخرج المبالغ المحتملة. يستبعد ما لا يصلح مبلغًا: الآيبان، أرقام
 *  الجوال، أرقام العمليات — كل سلسلة تتجاوز ستّ خانات صحيحة. ويميّز
 *  ما جاور رمز عملة أو حمل كسرين عشريين، فهو الأقرب إلى مبلغ حقيقي. */
function extractAmounts(raw: string) {
  const t = toLatin(raw).replace(/[٬⁦-⁩‎‏]/g, '');
  const numbers: number[] = [], strong: number[] = [];
  const re = /(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d{1,7})(?:[.٫](\d{1,2}))?(?![\d])/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(t)) !== null) {
    const intPart = m[1].replace(/,/g, '');
    if (intPart.length > 6) continue;                    // آيبان أو رقم عملية
    const val = Number(intPart) + (m[2] ? Number(`0.${m[2]}`) : 0);
    if (!isFinite(val) || val <= 0 || val > 1_000_000) continue;
    numbers.push(val);
    const around = t.slice(Math.max(0, m.index - 14), m.index + m[0].length + 14).toLowerCase();
    if (m[2] || /ر\.?\s?س|ريال|sar|﷼|sr\b/.test(around)) strong.push(val);
  }
  return {
    numbers: [...new Set(numbers)].sort((a, b) => b - a).slice(0, 40),
    strong:  [...new Set(strong)].sort((a, b) => b - a).slice(0, 20),
  };
}

const found = (t: string) => {
  const low = toLatin(t).toLowerCase();
  return [...new Set(KEYWORDS.filter((k) => low.includes(k)))].slice(0, 20);
};

async function ocr(key: string, bytes: Uint8Array, ext: string) {
  const type = ext === 'pdf' ? 'application/pdf'
             : ext === 'png' ? 'image/png'
             : ext === 'webp' ? 'image/webp' : 'image/jpeg';
  const form = new FormData();
  form.append('file', new Blob([bytes], { type }), `receipt.${ext}`);
  form.append('language', 'ara');
  form.append('OCREngine', '1');
  form.append('scale', 'true');
  form.append('isOverlayRequired', 'false');
  const res = await fetch('https://api.ocr.space/parse/image', {
    method: 'POST', headers: { apikey: key }, body: form,
  });
  if (!res.ok) throw new Error(`ocr_http_${res.status}`);
  const j = await res.json();
  if (j.IsErroredOnProcessing) {
    throw new Error(String(j.ErrorMessage?.[0] ?? j.ErrorMessage ?? 'ocr_error'));
  }
  return (j.ParsedResults ?? []).map((r: { ParsedText?: string }) => r.ParsedText ?? '').join('\n');
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
    const { path } = await req.json().catch(() => ({ path: null }));
    if (typeof path !== 'string' || !PATH_RE.test(path)) {
      return reply({ ok: false, reason: 'bad_path' }, 400);
    }

    const db = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
      { auth: { persistSession: false } },
    );

    // بلا مفتاح قراءة يبقى الفحص معطّلًا ويمرّ الحجز كما كان — التفعيل
    // بإضافة المفتاح وقلب المفتاح في الإعدادات، لا بتعديل الشيفرة.
    const key = Deno.env.get('OCR_API_KEY');
    if (!key) {
      await db.from('receipt_scans').upsert({ path, engine: 'none' });
      return reply({ ok: true, skipped: true, reason: 'no_key' });
    }

    const dl = await db.storage.from('receipts').download(path);
    if (dl.error || !dl.data) return reply({ ok: false, reason: 'not_found' }, 404);
    const bytes = new Uint8Array(await dl.data.arrayBuffer());
    if (bytes.byteLength > MAX_BYTES) {
      await db.from('receipt_scans').upsert({ path, engine: 'too_large' });
      return reply({ ok: false, reason: 'too_large' });
    }

    const ext = path.split('.').pop()!.toLowerCase();
    let text = '';
    try {
      text = await ocr(key, bytes, ext);
    } catch (e) {
      await db.from('receipt_scans').upsert({ path, engine: 'failed' });
      return reply({ ok: false, reason: 'ocr_failed', detail: String(e) });
    }

    const { numbers, strong } = extractAmounts(text);
    const keywords = found(text);
    await db.from('receipt_scans').upsert({
      path,
      numbers: strong.length ? strong : numbers,
      all_numbers: numbers,
      keywords,
      text_len: text.trim().length,
      engine: 'ocrspace',
    });

    return reply({
      ok: true, keywords, numbers: strong.length ? strong : numbers,
      textLen: text.trim().length,
    });
  } catch (e) {
    return reply({ ok: false, reason: 'server_error', detail: String(e) }, 500);
  }
});
