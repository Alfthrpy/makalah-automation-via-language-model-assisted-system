/* Audit kontras (axe color-contrast) tiap halaman x kombinasi tema (OS terang/gelap x tema aplikasi terang/gelap/sistem).
 * Dipakai untuk melacak bug "teks tak terbaca saat ganti tema". Memakai mock API dari states.cjs (tanpa backend).
 *   VITE_AUTH_MODE tidak diisi (mode dev) -> pnpm --filter web exec vite --port 5174   (halaman privat memakai cookie dev)
 *   NODE_PATH=$(npm root -g) node apps/web/e2e/theme.cjs [baseURL=http://127.0.0.1:5174] [shotDir]
 * Keluaran: tabel jumlah pelanggaran per halaman x kombinasi; shotDir (opsional) menyimpan tangkapan layar kombinasi OS!=tema.
 * Catatan: halaman Clerk asli (/masuk, /daftar di mode Clerk) butuh VITE_AUTH_MODE=clerk + VITE_CLERK_PUBLISHABLE_KEY. */
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
const APP=path.join(__dirname,'..');
const BASE=process.argv[2]||'http://127.0.0.1:5174';
const SHOTS=process.argv[3]||'';
const src=fs.readFileSync(path.join(APP,'e2e/states.cjs'),'utf8');
const pre=src.slice(0,src.indexOf('const axe = async'));
const fakeReq=(m)=>m==='axe-core'?{}:require(m);
const lib=new Function('require','__dirname','process',pre+';return {mock,JOBS};')(Object.assign(fakeReq,{resolve:(m,o)=>m==='axe-core'?'x':require.resolve(m,o)}),path.join(APP,'e2e'),{argv:['','',BASE,'']});
const axePath=require.resolve('axe-core',{paths:[APP]});
const PAGES=[['landing','/',false],['masuk','/masuk',false],['daftar','/daftar',false],['ketentuan','/ketentuan',false],['privasi','/privasi',false],['panduan','/panduan',false],['panduan-artikel','/panduan/cara-cek-doi-referensi',false],['404','/tidak-ada',false],
 ['dasbor','/dasbor',true],['buat','/buat',true],['pengaturan','/pengaturan',true],['job-running','/job/jrunning',true],['job-error','/job/jerror',true],['job-queued','/job/jqueued',true]];
const COMBOS=[['OSterang+terang','light','light'],['OSgelap+terang','dark','light'],['OSterang+gelap','light','dark'],['OSgelap+gelap','dark','dark'],['OSgelap+system','dark','system'],['OSterang+system','light','system']];
(async()=>{
  const browser=await chromium.launch(); const rows=[]; const detail={};
  for(const [pn,url,authd] of PAGES){
    for(const [cn,scheme,stored] of COMBOS){
      const ctx=await browser.newContext({viewport:{width:390,height:844},colorScheme:scheme});
      const p=await ctx.newPage();
      await p.addInitScript(([k,v,a])=>{try{localStorage.setItem(k,v); if(a) localStorage.setItem('malas.dev.signedin','1');}catch(e){}},['malas.theme',stored,authd]);
      await lib.mock(p);
      await p.goto(BASE+url,{waitUntil:'networkidle'}).catch(()=>{});
      await p.waitForTimeout(700);
      await p.addScriptTag({path:axePath});
      const v=await p.evaluate(async()=>{const r=await window.axe.run(document,{runOnly:['color-contrast']});return r.violations.flatMap(x=>x.nodes.map(n=>({t:n.target.join(' ').slice(0,80),s:(n.any[0]&&n.any[0].message||'').slice(0,140)})));});
      rows.push([pn,cn,v.length]); detail[pn+'|'+cn]=v.slice(0,4);
      if(SHOTS&&['OSgelap+terang','OSterang+gelap'].includes(cn)) await p.screenshot({path:`${SHOTS}/pg_${pn}_${cn}.png`,fullPage:false});
      await ctx.close();
    }
  }
  await browser.close();
  const byPage={}; rows.forEach(([pn,cn,n])=>{(byPage[pn]??={})[cn]=n;});
  console.log('pelanggaran kontras (axe color-contrast) per halaman x kombinasi tema:');
  for(const pn of Object.keys(byPage)) console.log(pn.padEnd(16), COMBOS.map(c=>c[0]+'='+byPage[pn][c[0]]).join('  '));
  if(SHOTS) fs.writeFileSync(path.join(SHOTS,'audit-detail.json'),JSON.stringify(detail,null,1));
})();
