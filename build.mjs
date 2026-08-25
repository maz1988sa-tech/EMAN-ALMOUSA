/* بناء نسخة النشر.
 *
 * ما يصل متصفّح العميلة اليوم هو مصدرنا كما كتبناه: أسماء كاملة، وشروح
 * عربية تشرح سبب كل قرار. هذا يفيدنا نحن ولا يفيد أحدًا سواه — ومن أراد
 * نسخ العمل وجده مرتّبًا موثَّقًا. البناء يحوّله إلى جدار: أسماء مختصرة،
 * بلا شرح، وبلا فراغات. لا يمنع مصمِّمًا على السرقة، ويمنع من يمرّ.
 *
 * وفيه مكسب ثانٍ لا يقلّ: ملفّاتٌ أصغر تصل أسرع إلى جوّال العميلة.
 *
 * التشغيل:  node build.mjs        →  dist/
 *
 * إصدار node مثبَّت في .node-version حتى لا يختار خادم البناء إصدارًا
 * قديمًا لا تعمل عليه أدوات التصغير — عطلٌ لا يظهر إلا هناك.
 */
import { rm, mkdir, cp, readFile, writeFile, readdir, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, extname, relative } from 'node:path';
import * as esbuild from 'esbuild';
import { minify as minifyHtml } from 'html-minifier-terser';

const SRC = new URL('.', import.meta.url).pathname.replace(/\/$/, '');
const OUT = join(SRC, 'dist');

/* ما يُنسخ كما هو. المكتبة الخارجية مصغَّرة أصلًا، والخطوط والصور ثنائية،
   وإعادة ضغطها عبثٌ يطيل البناء بلا مقابل. */
const COPY_DIRS  = ['assets/fonts', 'assets/brand', 'assets/icons', 'assets/vendor'];
const COPY_FILES = [
  'manifest.webmanifest', 'manifest-admin.webmanifest',
  'assets/favicon.svg', 'assets/favicon-admin.svg',
  'assets/icon-192.svg', 'assets/icon-512.svg',
  'assets/icon-admin-192.svg', 'assets/icon-admin-512.svg',
];

/* ما يُصغَّر. الإعدادات تبقى مقروءة عمدًا: مفتاحها علنيّ بحكم التصميم،
   وإخفاؤه يوهم بسرّية غير قائمة — ويصعّب عليك تشخيص عطلٍ يومًا. */
const JS_FILES   = ['assets/db.js', 'assets/icons.js', 'sw.js'];
const CSS_FILES  = ['assets/client-theme.css', 'assets/theme.css', 'assets/fonts.css'];
const HTML_FILES = ['index.html', 'admin.html'];
const AS_IS      = ['assets/config.js'];

const kb = (n) => `${(n / 1024).toFixed(1)} كِب`;
const rows = [];

async function sizeOf(p) { return (await stat(p)).size; }

async function buildJs(rel) {
  const from = join(SRC, rel), to = join(OUT, rel);
  const before = await sizeOf(from);
  await esbuild.build({
    entryPoints: [from], outfile: to,
    minify: true, format: 'esm', target: 'es2022',
    legalComments: 'none', charset: 'utf8',
    // بلا حزم: الاستيرادات تحمل ?v= وتُخدَم ملفّاتٍ مستقلّة كما هي اليوم.
    bundle: false,
  });
  rows.push([rel, before, await sizeOf(to)]);
}

async function buildCss(rel) {
  const from = join(SRC, rel), to = join(OUT, rel);
  const before = await sizeOf(from);
  await esbuild.build({
    entryPoints: [from], outfile: to,
    minify: true, loader: { '.css': 'css' }, charset: 'utf8',
    legalComments: 'none',
  });
  rows.push([rel, before, await sizeOf(to)]);
}

async function buildHtml(rel) {
  const from = join(SRC, rel), to = join(OUT, rel);
  const src = await readFile(from, 'utf8');
  const out = await minifyHtml(src, {
    collapseWhitespace: true,
    conservativeCollapse: false,
    removeComments: true,
    removeRedundantAttributes: false,   // dir/type مقصودة، لا تُحذف
    keepClosingSlash: true,
    minifyCSS: true,
    minifyJS: { module: true, compress: true, mangle: true, format: { comments: false } },
    // العربية تبقى كما هي: أيّ ترميز للحروف يضخّم الملف ويصعّب المراجعة.
    customAttrAssign: [],
    sortAttributes: false,
    sortClassName: false,
  });
  await writeFile(to, out, 'utf8');
  rows.push([rel, Buffer.byteLength(src), Buffer.byteLength(out)]);
}

async function main() {
  await rm(OUT, { recursive: true, force: true });
  await mkdir(join(OUT, 'assets'), { recursive: true });

  for (const d of COPY_DIRS) {
    if (existsSync(join(SRC, d))) await cp(join(SRC, d), join(OUT, d), { recursive: true });
  }
  for (const f of [...COPY_FILES, ...AS_IS]) {
    if (existsSync(join(SRC, f))) await cp(join(SRC, f), join(OUT, f));
  }

  for (const f of CSS_FILES)  await buildCss(f);
  for (const f of JS_FILES)   await buildJs(f);
  for (const f of HTML_FILES) await buildHtml(f);

  // رؤوس النشر: تُقرأ من الجذر فتُطبَّق على كل طلب.
  await cp(join(SRC, '_headers'), join(OUT, '_headers'));

  let a = 0, b = 0;
  console.log('\n  الملف                          قبل        بعد      الوفر');
  console.log('  ' + '─'.repeat(58));
  for (const [f, x, y] of rows) {
    a += x; b += y;
    const pct = x ? Math.round((1 - y / x) * 100) : 0;
    console.log(`  ${f.padEnd(28)} ${kb(x).padStart(10)} ${kb(y).padStart(10)}   ${String(pct).padStart(3)}٪`);
  }
  console.log('  ' + '─'.repeat(58));
  console.log(`  ${'المجموع'.padEnd(28)} ${kb(a).padStart(10)} ${kb(b).padStart(10)}   ${String(Math.round((1 - b / a) * 100)).padStart(3)}٪\n`);
}

main().catch((e) => { console.error(e); process.exit(1); });
