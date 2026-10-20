import fs from 'node:fs/promises';import path from 'node:path';import {fileURLToPath,pathToFileURL} from 'node:url';import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const {createServer}=await import(pathToFileURL(path.join(root,'desktop/node_modules/vite/dist/node/index.js')).href);const {chromium}=await import('file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');
const server=await createServer({root:path.join(root,'desktop'),configFile:path.join(root,'desktop/vite.config.ts'),server:{host:'127.0.0.1',port:5198,strictPort:true}});await server.listen();const browser=await chromium.launch({channel:'msedge',headless:true});
try{
 const fixture=JSON.parse(await fs.readFile(path.join(root,'.local/qa/grouped-course-mock.json'),'utf8'));const a=fixture.id,b='11111111-2222-4333-8444-555555555555';
 const page=await browser.newPage({viewport:{width:1440,height:1100}});const errors=[],writes=[],reads=[];let fail=0,delayA=false,delayed=0;
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(({a,b})=>{
  window.__testPhase='starting';window.framewiseDesktop={status:async()=>({phase:window.__testPhase,apiOrigin:'http://127.0.0.1:18080',settings:{hasKey:true},models:{state:'ready'}})};
  localStorage.setItem('analysisHistory:v1',JSON.stringify([{id:a,name:'测试课程A',status:'completed',addedAt:new Date().toISOString()},{id:b,name:'测试课程B',status:'completed',addedAt:new Date().toISOString()}]));
 },{a,b});
 await page.route('**/api/**',async route=>{
  const req=route.request(),p=new URL(req.url()).pathname;
  if(req.method()!=='GET'){writes.push(p);return route.fulfill({status:500,json:{error:'QA unexpected write'}})}
  if(p==='/api/transcriptions')return route.fulfill({json:[{id:a,name:'测试课程A',createdAt:new Date().toISOString(),status:'completed'},{id:b,name:'测试课程B',createdAt:new Date().toISOString(),status:'completed'}]});
  if(p===`/api/transcriptions/${a}`||p===`/api/transcriptions/${b}`){
   const id=p.split('/').at(-1);reads.push(id);
   if(id===b&&fail-->0)return route.fulfill({status:503,body:'unavailable'});
   if(id===a&&delayA){delayed++;await new Promise(resolve=>setTimeout(resolve,2200))}
   const mock=structuredClone(fixture);mock.id=id;try{return await route.fulfill({json:mock})}catch{return}
  }
  if(p.endsWith('/media'))return route.fulfill({status:410,json:{error:'missing'}});
  if(p.endsWith('/chapters'))return route.fulfill({json:{status:'completed',result:{chapters:[]}}});
  if(p.endsWith('/practice'))return route.fulfill({json:[]});
  return route.fulfill({json:{status:'not_requested'}});
 });
 await page.goto('http://127.0.0.1:5198/');await page.locator('.runtime-dialog').getByRole('button',{name:'关闭',exact:true}).click();
 async function open(name){await page.getByRole('tab',{name:'历史记录',exact:true}).click();await page.locator('.history-open').filter({hasText:name}).click()}
 async function readAgain(){await page.locator('.analysis-settings').evaluate(el=>el.open=true);await page.getByRole('button',{name:'读取结果',exact:true}).click()}
 const done=()=>page.locator('.analysis-progress strong').filter({hasText:'分析完成'}).waitFor();
 await open('测试课程A');await page.getByText('本机服务启动中，正在等待读取课程…',{exact:true}).first().waitFor();
 await open('测试课程B');assert.deepEqual(reads,[]);await page.evaluate(()=>{window.__testPhase='ready';window.dispatchEvent(new CustomEvent('framewise-runtime-state',{detail:{phase:'ready',apiOrigin:'http://127.0.0.1:18080'}}))});await done();assert(!reads.includes(a));
 const preserved=await page.locator('.results-panel .section-title span').innerText();
 fail=3;await readAgain();await page.getByRole('button',{name:'重试读取（不会重新分析）',exact:true}).waitFor();assert.equal(await page.locator('.results-panel .section-title span').innerText(),preserved);
 fail=0;await page.getByRole('button',{name:'重试读取（不会重新分析）',exact:true}).click();await done();
 delayA=true;await open('测试课程A');await page.waitForFunction(()=>document.querySelector('#analysis-id')?.value!==undefined);for(let i=0;i<60&&delayed===0;i++)await new Promise(resolve=>setTimeout(resolve,100));assert(delayed>0);await open('测试课程B');await done();await new Promise(resolve=>setTimeout(resolve,2500));assert.equal(await page.locator('#analysis-id').inputValue(),b);
 await page.evaluate(()=>{window.__testPhase='error'});await readAgain();await page.getByRole('button',{name:'重试读取（不会重新分析）',exact:true}).waitFor();await page.evaluate(()=>{window.__testPhase='ready';window.dispatchEvent(new CustomEvent('framewise-runtime-state',{detail:{phase:'ready',apiOrigin:'http://127.0.0.1:18080'}}))});await done();
 assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);const result={slowStartupRecovery:true,switchWhileWaiting:true,temporaryFailureBounded:true,existingResultsPreserved:true,manualReadRetry:true,staleResponseIgnored:true,readyEventRecovery:true,writeRequests:writes.length,paidModelCalls:0};
 await fs.writeFile(path.join(root,'.local/qa/native-delivery/course-read-ui-result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close();await server.close()}
