import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
const a='0af262c2-ed83-4f68-b246-ea7e6e290d92', b='65894cb5-9404-4bdd-a10b-a4bdcdd4d5fc', stale='2cb69c81-67ad-4dc9-b29e-f5cb96b62e63';
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 let rows=[{id:a,name:'课程A.mp4',status:'completed',createdAt:'2026-10-12T00:00:00Z'},{id:b,name:null,status:'expired',createdAt:'2026-10-11T00:00:00Z'}],fail=false,delayed=false,started=false,release;
 await page.route('**/api/transcriptions',async route=>{const snapshot=[...rows];if(delayed){delayed=false;started=true;await new Promise(r=>release=r)}await route.fulfill({status:fail?503:200,contentType:'application/json',body:JSON.stringify(snapshot)}).catch(()=>{})});
 await page.route('**/api/transcriptions/*',async route=>{if(route.request().method()==='DELETE'){rows=rows.filter(r=>!route.request().url().endsWith(r.id));await route.fulfill({status:204})}else await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({id:a,status:'completed',result:{language:'zh',segments:[],visualEvidence:[],pageGroups:[]}})})});
 await page.addInitScript(stale=>{localStorage.setItem('analysisHistory:v1',JSON.stringify([{id:stale,name:'旧缓存',status:'completed',addedAt:'2025-01-01'}]))},stale);
 await page.goto('http://127.0.0.1:5173/');await page.getByRole('tab',{name:'历史记录',exact:true}).click();
 await page.waitForFunction(()=>document.querySelectorAll('.history-item').length===2);assert(await page.getByText('课程A.mp4',{exact:true}).isVisible());assert.equal(await page.getByText('旧缓存',{exact:true}).count(),0);
 await page.locator('.history-item').filter({hasText:'已过期'}).locator('.history-open').click();assert(await page.getByRole('alert').filter({hasText:'此任务已过期'}).isVisible());assert(await page.locator('.history-delete').first().isEnabled());
 fail=true;await page.getByRole('button',{name:'刷新历史',exact:true}).click();await page.getByRole('alert').filter({hasText:'无法同步服务器历史'}).waitFor();assert.equal(await page.locator('.history-item').count(),2);fail=false;
 delayed=true;await page.getByRole('button',{name:'刷新历史',exact:true}).click();while(!started)await page.waitForTimeout(10);
 await page.locator('.history-item').filter({hasText:'课程A.mp4'}).getByRole('button',{name:/永久删除/}).click();
 await page.waitForFunction(()=>document.querySelectorAll('.history-item').length===1);release();await page.waitForTimeout(200);assert.equal(await page.locator('.history-item').count(),1);
 await page.evaluate(()=>localStorage.clear());await page.reload();await page.getByRole('tab',{name:'历史记录',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('.history-item').length===1);assert(await page.getByText('已过期',{exact:true}).isVisible());
 await page.setViewportSize({width:390,height:844});assert(await page.locator('#tab-history').evaluate(el=>el.scrollWidth<=el.clientWidth+1));assert.deepEqual(errors,[]);
 const output=new URL('../../../.local/qa/',import.meta.url);await mkdir(output,{recursive:true});await page.screenshot({path:new URL('history-sync.png',output).pathname.slice(1)});
 console.log('Server membership, stale cache removal, offline preservation, deletion with delayed refresh, clean-browser restore and mobile layout passed; no real task deletion or AI calls.');
}finally{await browser.close()}
