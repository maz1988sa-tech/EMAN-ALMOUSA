const { chromium } = require('playwright-core');
const path=require('path'), fs=require('fs'), http=require('http');
const ROOT='/home/user/EMAN-ALMOUSA';
const MIME={'.html':'text/html','.js':'application/javascript','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2','.webmanifest':'application/manifest+json'};
(async()=>{
  const srv=http.createServer((q,r)=>{const f=path.join(ROOT,decodeURIComponent(q.url.split('?')[0]));
    fs.readFile(f,(e,b)=>{if(e){r.writeHead(404);r.end();return;}r.writeHead(200,{'Content-Type':MIME[path.extname(f)]||'application/octet-stream'});r.end(b);});}).listen(0,'127.0.0.1');
  await new Promise(r=>srv.on('listening',r));
  const base=`http://127.0.0.1:${srv.address().port}/`;
  const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome',args:['--no-sandbox']});
  const ctx=await b.newContext({viewport:{width:420,height:900},deviceScaleFactor:2,colorScheme:'dark'});
  await ctx.route('**/assets/vendor/supabase.js',r=>r.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.join(ROOT,'dev/mock-supabase.js'),'utf8')}));
  for (const [n,u,signed] of [['dark-client','index.html',false],['dark-admin','admin.html',true]]) {
    const p=await ctx.newPage();
    if(signed) await p.addInitScript(()=>{window.__MOCK_SIGNED_IN__=true;});
    await p.goto(base+u); await p.waitForTimeout(1600);
    // Confirm the body actually painted a dark ground rather than inheriting one.
    const bg=await p.evaluate(()=>getComputedStyle(document.body).backgroundColor);
    const fg=await p.evaluate(()=>getComputedStyle(document.body).color);
    console.log(n,'body bg:',bg,' color:',fg);
    await p.screenshot({path:`/var/tmp/shots/${n}.png`,fullPage:false});
    await p.close();
  }
  await b.close(); srv.close();
})();
