// Reproduces the client's sequence against the mock: book, then reload.
const { chromium } = require('playwright-core');
const path=require('path'), fs=require('fs'), http=require('http');
const MIME={'.html':'text/html','.js':'application/javascript','.css':'text/css','.svg':'image/svg+xml','.json':'application/json','.webmanifest':'application/manifest+json'};
const ROOT='/home/user/EMAN-ALMOUSA';
function serve(root){return new Promise(r=>{const s=http.createServer((q,res)=>{
 const f=path.join(root,decodeURIComponent(q.url.split('?')[0]));
 fs.readFile(f,(e,b)=>{if(e){res.writeHead(404);res.end();return;}
 res.writeHead(200,{'Content-Type':MIME[path.extname(f)]||'application/octet-stream'});res.end(b);});
}).listen(0,'127.0.0.1',()=>r(s));});}

(async()=>{
 const srv=await serve(ROOT);
 const base=`http://127.0.0.1:${srv.address().port}/`;
 const browser=await chromium.launch({
   executablePath:'/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell',
   args:['--no-sandbox','--disable-dev-shm-usage']});
 const ctx=await browser.newContext({viewport:{width:430,height:900}});
 await ctx.route('**/assets/vendor/supabase.js', route =>
   route.fulfill({contentType:'application/javascript',
                  body:fs.readFileSync(path.join(ROOT,'dev/mock-supabase.js'),'utf8')}));
 const page=await ctx.newPage();
 page.on('pageerror',e=>console.log('[pageerror]',String(e).slice(0,200)));

 await page.goto(base+'index.html');
 await page.waitForTimeout(900);

 const where = async () => (await page.locator('#view h2').first().textContent().catch(()=>'?')).trim();
 const click = async (label, sel) => {
   const el = page.locator(sel).first();
   if (await el.count() === 0) { console.log(`  ! ${label}: no match — now at "${await where()}"`); return false; }
   const enabled = await el.isEnabled().catch(()=>false);
   if (!enabled) { console.log(`  ! ${label}: disabled — now at "${await where()}"`); return false; }
   await el.click(); await page.waitForTimeout(600);
   console.log(`  ok ${label} -> "${await where()}"`);
   return true;
 };

 // The service picker is a set of +/- counters, so add one of the first service.
 const plus = page.locator('#view button', { hasText: /^\+$/ }).first();
 if (await plus.count()) { await plus.click(); await page.waitForTimeout(400); }
 else console.log('  ! no + button found');
 await click('continue', '#view button:has-text("متابعة"), #view button:has-text("التالي")');
 await click('day',      '#view .day:not([disabled]), #view button[data-date]');
 await click('slot',     '#view .slot:not([disabled]), #view button[data-slot]');
 await click('continue2','#view button:has-text("متابعة"), #view button:has-text("التالي")');

 await page.waitForSelector('#f-name', { timeout: 5000 });
 await page.fill('#f-name', 'نورة العتيبي');
 await page.fill('#f-phone', '0501234567');
 await page.waitForTimeout(300);
 console.log('  form fields:', await page.evaluate(()=>[...document.querySelectorAll('#view input,#view textarea')].map(e=>`${e.tagName}[${e.type||''}] id=${e.id||'-'} val="${e.value}"`)));
 console.log('  buttons:', await page.evaluate(()=>[...document.querySelectorAll('#view button')].map(e=>`id=${e.id||'-'} disabled=${e.disabled} :: ${e.innerText.trim().slice(0,20)}`)));
 await page.waitForTimeout(200);
 await click('submit', '#submit');
 await page.waitForTimeout(1000);

 const urlAfter = page.url().replace(base,'/');
 const refText  = await page.locator('#view .ref').first().textContent().catch(()=>null);
 console.log('\nAfter booking');
 console.log('  URL :', urlAfter);
 console.log('  ref :', (refText||'—').trim());

 await page.reload();
 await page.waitForTimeout(1200);
 const urlReload = page.url().replace(base,'/');
 const head = await page.locator('#view h2').first().textContent().catch(()=>null);
 console.log('\nAfter reload');
 console.log('  URL     :', urlReload);
 console.log('  heading :', (head||'—').trim());

 const ok = urlReload.includes('?t=');
 console.log('\n' + (ok ? 'PASS — the reload kept the booking'
                        : 'FAIL — the reload lost the booking'));
 await page.screenshot({path:'/var/tmp/after-reload.png',fullPage:true});
 await browser.close(); srv.close();
 process.exitCode = ok ? 0 : 1;
})();
