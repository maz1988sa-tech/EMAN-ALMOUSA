// Screenshots a page from a directory at 2x, for design review.
// Usage: node dev/shoot_board.js <dir> <out.png> [page.html] [width] [height]
// ES modules and canvas need a real origin, so it serves the directory first.
const { chromium } = require('playwright-core');
const path=require('path'), fs=require('fs'), http=require('http');
const SP=process.argv[2], OUT=process.argv[3];
const PAGE=process.argv[4]||'theme_board.html';
const VW=+(process.argv[5]||1660), VH=+(process.argv[6]||1100);
function serve(root){return new Promise(r=>{const s=http.createServer((q,res)=>{
 const f=path.join(root,decodeURIComponent(q.url.split('?')[0]));
 fs.readFile(f,(e,b)=>{if(e){res.writeHead(404);res.end();return;}
 res.writeHead(200,{'Content-Type': f.endsWith('.js') ? 'application/javascript' : 'text/html; charset=utf-8'});res.end(b);});
}).listen(0,'127.0.0.1',()=>r(s));});}
(async()=>{
 const srv=await serve(SP);
 const b=await chromium.launch({
   executablePath:'/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell',
   args:['--no-sandbox','--disable-dev-shm-usage','--force-device-scale-factor=2']});
 const p=await b.newPage({viewport:{width:VW,height:VH},deviceScaleFactor:2});
 await p.goto(`http://127.0.0.1:${srv.address().port}/${PAGE}`);
 await p.waitForTimeout(2500);            // let Google Fonts land
 const fonts = await p.evaluate(()=>document.fonts.status);
 console.log('fonts:', fonts);
 await p.screenshot({path:OUT, fullPage:true});
 await b.close(); srv.close();
 console.log('saved', OUT);
})();
