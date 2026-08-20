// Renders the two surfaces against dev/mock-supabase.js and saves screenshots.
// Usage: node dev/shots.js [outDir]
const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');
const http = require('http');

// ES modules will not load over file:// — the pages need a real origin.
const MIME = { '.html':'text/html', '.js':'application/javascript', '.css':'text/css',
               '.svg':'image/svg+xml', '.json':'application/json', '.webmanifest':'application/manifest+json' };
function serve(root) {
  return new Promise(resolve => {
    const srv = http.createServer((req, res) => {
      const file = path.join(root, decodeURIComponent(req.url.split('?')[0]));
      fs.readFile(file, (err, buf) => {
        if (err) { res.writeHead(404); res.end('not found'); return; }
        res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
        res.end(buf);
      });
    }).listen(0, '127.0.0.1', () => resolve(srv));
  });
}

const ROOT = path.resolve(__dirname, '..');
const OUT = path.resolve(process.argv[2] || '/var/tmp/shots');
const CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

const SHOTS = [
  { name: 'client-1-services', url: 'index.html' },
  { name: 'admin-1-home',    url: 'admin.html', signedIn: true },
  { name: 'admin-2-agenda',  url: 'admin.html', signedIn: true, act: async p => {
      await p.click('[data-tab="agenda"]'); await p.waitForTimeout(400); } },
  { name: 'admin-3-hours',   url: 'admin.html', signedIn: true, act: async p => {
      await p.click('[data-tab="hours"]'); await p.waitForTimeout(400); } },
  { name: 'admin-4-settings',url: 'admin.html', signedIn: true, act: async p => {
      await p.click('[data-tab="settings"]'); await p.waitForTimeout(400); } },
  { name: 'admin-5-detail',  url: 'admin.html', signedIn: true, act: async p => {
      await p.click('[data-open]'); await p.waitForTimeout(600); } },
  { name: 'admin-6-login',   url: 'admin.html' },
  { name: 'client-2-when',     url: 'index.html', act: async p => {
      await p.click('[data-inc="s1"]'); await p.click('#toStep2');
      await p.waitForSelector('.slot'); } },
  { name: 'client-3-details',  url: 'index.html', act: async p => {
      await p.click('[data-inc="s1"]'); await p.click('[data-inc="s2"]');
      await p.click('#toStep2'); await p.waitForSelector('.slot');
      await p.click('.slot'); await p.waitForSelector('#f-name'); } },
  { name: 'client-4-tracking', url: 'index.html?t=tok-3' },
];

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const srv = await serve(ROOT);
  const base = `http://127.0.0.1:${srv.address().port}/`;
  const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({
    viewport: { width: 420, height: 900 }, deviceScaleFactor: 2, locale: 'ar-SA',
  });

  // Serve the mock in place of the real client bundle.
  await ctx.route('**/assets/vendor/supabase.js', route =>
    route.fulfill({ contentType: 'application/javascript',
                    body: fs.readFileSync(path.join(ROOT, 'dev/mock-supabase.js'), 'utf8') }));

  const errors = [];
  for (const shot of SHOTS) {
    const page = await ctx.newPage();
    if (shot.signedIn) await page.addInitScript(() => { window.__MOCK_SIGNED_IN__ = true; });
    page.on('console', m => { if (m.type() === 'error') errors.push(`[${shot.name}] ${m.text()}`); });
    page.on('pageerror', e => errors.push(`[${shot.name}] PAGEERROR ${e.message}`));
    await page.goto(base + shot.url);
    await page.waitForTimeout(1400);
    if (shot.act) { try { await shot.act(page); } catch (e) { errors.push(`[${shot.name}] ACT ${e.message}`); } }
    await page.waitForTimeout(700);
    await page.screenshot({ path: path.join(OUT, shot.name + '.png'), fullPage: true });
    await page.close();
  }
  await browser.close();
  srv.close();
  if (errors.length) { console.log('CONSOLE ERRORS:\n' + errors.join('\n')); process.exitCode = 1; }
  else console.log('clean — no console errors');
})();
