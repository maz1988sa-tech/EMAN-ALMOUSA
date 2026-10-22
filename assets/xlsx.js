/* ملفّ Excel حقيقيّ (‎.xlsx‎) بلا مكتبة.
 *
 * لماذا لا CSV كالتصدير القائم: Excel يقرأ رقم الجوال ٩٦٦٥٠١٢٣٤٥٦٧ عددًا
 * فيكتبه 9.665E+11، ويقرأ العربية في CSV بترميزٍ خاطئ على بعض الأجهزة،
 * ولا يعرف أنّ الورقة من اليمين. وملفّ xlsx يحمل ذلك كلّه صريحًا: الجوال
 * نصٌّ، والتاريخ تاريخٌ يُرتَّب، والورقة RTL، والصفّ الأوّل مثبّت ومرشِّح.
 *
 * والملفّ أرشيف ZIP من خمسة ملفّات XML. يُخزَّن بلا ضغط (الطريقة صفر) —
 * Excel يقبله، والحجم هنا كيلوبايتات — فلا يلزم إلّا CRC32. ومكتبةٌ كاملة
 * (SheetJS نحو ميغابايت) لهذا وحده إضافةُ اعتمادٍ بلا حاجة.
 */

const enc = new TextEncoder();

/* محارف لا يقبلها XML 1.0 أصلًا — نصٌّ لصقته عميلةٌ من تطبيقٍ آخر قد
   يحملها، فيرفض Excel الملفّ كلَّه بسببها. */
const BAD = /[\u0000-\u0008\u000B\u000C\u000E-\u001F￾￿]/g;
const x = (s) => String(s ?? '').replace(BAD, '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function colName(i) {
  let s = ''; i += 1;
  while (i > 0) { const m = (i - 1) % 26; s = String.fromCharCode(65 + m) + s; i = Math.floor((i - 1) / 26); }
  return s;
}

/* تاريخ Excel عددُ أيامٍ منذ ٣٠ ديسمبر ١٨٩٩ — يُحسب من التقويم لا من الساعة،
   فلا يُزيحه فرقُ التوقيت يومًا. */
function serial(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
  if (!m) return null;
  return (Date.UTC(+m[1], +m[2] - 1, +m[3]) - Date.UTC(1899, 11, 30)) / 86400000;
}

/* الأنماط بالترتيب: ٠ افتراضيّ · ١ ترويسة · ٢ تاريخ · ٣ عدد · ٤ نصّ */
const STYLE = { head: 1, date: 2, number: 3, money: 3, text: 4 };
const STYLES_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy-mm-dd"/></numFmts>
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFF2E7DE"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="5">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>`;

function cell(ref, v, type, head) {
  if (head) return `<c r="${ref}" t="inlineStr" s="${STYLE.head}"><is><t>${x(v)}</t></is></c>`;
  if (v === null || v === undefined || v === '') return `<c r="${ref}" s="${STYLE[type] || 0}"/>`;
  if (type === 'number' || type === 'money') {
    const n = Number(v);
    return Number.isFinite(n) ? `<c r="${ref}" s="${STYLE[type]}"><v>${n}</v></c>` : cell(ref, v, 'text');
  }
  if (type === 'date') {
    const n = serial(v);
    return n === null ? cell(ref, v, 'text') : `<c r="${ref}" s="${STYLE.date}"><v>${n}</v></c>`;
  }
  return `<c r="${ref}" t="inlineStr" s="${STYLE.text}"><is><t xml:space="preserve">${x(v)}</t></is></c>`;
}

function sheetXml(columns, rows, rtl) {
  const last = colName(columns.length - 1);
  const head = `<row r="1">${columns.map((c, i) => cell(`${colName(i)}1`, c.label, 'text', true)).join('')}</row>`;
  const body = rows.map((r, ri) => `<row r="${ri + 2}">${
    columns.map((c, i) => cell(`${colName(i)}${ri + 2}`, r[i], c.type || 'text')).join('')}</row>`).join('');
  const cols = columns.map((c, i) =>
    `<col min="${i + 1}" max="${i + 1}" width="${c.width || 14}" customWidth="1"/>`).join('');
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<dimension ref="A1:${last}${rows.length + 1}"/>
<sheetViews><sheetView workbookViewId="0"${rtl ? ' rightToLeft="1"' : ''}><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
<sheetFormatPr defaultRowHeight="15"/>
<cols>${cols}</cols>
<sheetData>${head}${body}</sheetData>
<autoFilter ref="A1:${last}${rows.length + 1}"/>
</worksheet>`;
}

const CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();
function crc32(b) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < b.length; i += 1) c = CRC[(c ^ b[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}

/* ZIP بلا ضغط. والتاريخ في الرأس ١ يناير ١٩٨٠ — أقدمُ ما يقبله DOS؛
   الصفر يُقرأ تاريخًا فاسدًا عند بعض الأدوات. */
function zip(files) {
  const DOS_DATE = (0 << 9) | (1 << 5) | 1;
  const parts = []; const central = []; let off = 0;
  for (const f of files) {
    const name = enc.encode(f.name); const data = f.data; const crc = crc32(data);
    const h = new DataView(new ArrayBuffer(30));
    h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0, true);
    h.setUint16(8, 0, true); h.setUint16(10, 0, true); h.setUint16(12, DOS_DATE, true);
    h.setUint32(14, crc, true); h.setUint32(18, data.length, true); h.setUint32(22, data.length, true);
    h.setUint16(26, name.length, true); h.setUint16(28, 0, true);
    parts.push(new Uint8Array(h.buffer), name, data);
    const c = new DataView(new ArrayBuffer(46));
    c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true);
    c.setUint16(8, 0, true); c.setUint16(10, 0, true); c.setUint16(12, 0, true);
    c.setUint16(14, DOS_DATE, true); c.setUint32(16, crc, true); c.setUint32(20, data.length, true);
    c.setUint32(24, data.length, true); c.setUint16(28, name.length, true);
    c.setUint32(42, off, true);
    central.push(new Uint8Array(c.buffer), name);
    off += 30 + name.length + data.length;
  }
  const cdSize = central.reduce((n, p) => n + p.length, 0);
  const e = new DataView(new ArrayBuffer(22));
  e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true);
  e.setUint16(10, files.length, true); e.setUint32(12, cdSize, true); e.setUint32(16, off, true);
  const all = [...parts, ...central, new Uint8Array(e.buffer)];
  const out = new Uint8Array(all.reduce((n, p) => n + p.length, 0));
  let p = 0; for (const a of all) { out.set(a, p); p += a.length; }
  return out;
}

/** columns: [{ label, type: 'text'|'number'|'money'|'date', width }]
 *  rows:    [[قيمة لكلّ عمود]]  →  Uint8Array لملفّ ‎.xlsx‎ */
export function buildXlsx({ sheet = 'Sheet1', columns, rows, rtl = true }) {
  /* اسم الورقة: ٣١ حرفًا وبلا []:*?/\ — قاعدة Excel لا خيار. */
  const name = String(sheet).replace(/[[\]:*?/\\]/g, ' ').slice(0, 31) || 'Sheet1';
  const last = colName(columns.length - 1);
  const files = [
    ['[Content_Types].xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>`],
    ['_rels/.rels', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`],
    ['xl/workbook.xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="${x(name)}" sheetId="1" r:id="rId1"/></sheets>
<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">'${x(name.replace(/'/g, "''"))}'!$A$1:$${last}$${rows.length + 1}</definedName></definedNames>
</workbook>`],
    ['xl/_rels/workbook.xml.rels', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`],
    ['xl/styles.xml', STYLES_XML],
    ['xl/worksheets/sheet1.xml', sheetXml(columns, rows, rtl)],
  ];
  return zip(files.map(([n, s]) => ({ name: n, data: enc.encode(s) })));
}

export const XLSX_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
