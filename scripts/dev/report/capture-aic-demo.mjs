import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const q=path.join(root,'.local/qa/aic-open-release-2026-10-25');
const {createServer}=await import(pathToFileURL(path.join(root,'desktop/node_modules/vite/dist/node/index.js')).href);
const pw=process.env.FRAMEWISE_PLAYWRIGHT_MODULE;
const {chromium}=await import(pw?pathToFileURL(path.resolve(pw)).href:'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');
const fixture=JSON.parse(await fs.readFile(path.join(q,'ui-fixture.json'),'utf8')),job=fixture.job,id=job.id;
const question={id:'demo-q1',nodeTitle:'增长率',kind:'single',title:'增长率核对',prompt:'某商品从100件增加到120件，增长率是多少？',options:['10%','20%','25%','30%'],scenario:'adapted'};
const set={id:'authored-demo',title:'自制样例：增长率',status:'completed',questions:[question]};
const errors=[],api=[],external=[],unknown=[];
const server=await createServer({root:path.join(root,'desktop'),configFile:path.join(root,'desktop/vite.config.ts'),server:{host:'127.0.0.1',port:0}});
await server.listen();const port=server.httpServer.address().port;
const browser=await chromium.launch({executablePath:process.env.FRAMEWISE_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1500,height:1050},deviceScaleFactor:1});
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async r=>{
  const u=new URL(r.request().url()),p=u.pathname;
  if(!['127.0.0.1','localhost'].includes(u.hostname)){if(u.protocol==='http:'||u.protocol==='https:'){external.push(u.origin);return r.abort();}return r.continue();}
  if(!p.startsWith('/api/'))return r.continue();
  api.push({path:p,method:r.request().method()});
  const json=x=>r.fulfill({json:x,headers:{'Access-Control-Allow-Origin':'*'}});
  if(p==='/api/transcriptions')return json([{id,originalFilename:'Framewise-demo.mp4',name:'自制教学样例：增长量与增长率',status:'completed',createdAt:'2026-10-25T00:00:00Z'}]);
  if(p===('/api/transcriptions/'+id))return json(job);
  if(p.endsWith('/media'))return json(fixture.identity);
  if(p.includes('/frames/')){const t=Number(p.split('/').at(-1));return r.fulfill({body:await fs.readFile(path.join(q,'slide'+Math.min(2,Math.floor(t/10000))+'.png')),contentType:'image/png',headers:{'Access-Control-Allow-Origin':'*'}});}
  if(p.endsWith('/subtitles'))return json({status:'not_requested'});
  if(p.endsWith('/chapters'))return json({status:'completed',result:{chapters:[]}});
  if(p.endsWith('/overview'))return json({status:'not_requested'});
  if(p.endsWith('/practice'))return json([set]);
  if(p.endsWith('/practice/authored-demo'))return json(set);
  if(p.endsWith('/sessions'))return json({id:'authored-session',feedback:[]});
  if(p.endsWith('/answers')){
   const choice=r.request().postDataJSON().selectedIndex;
   return json({questionId:question.id,selectedIndex:choice,answerIndex:1,correct:choice===1,explanation:'先求增长量：120 - 100 = 20件；再用增长量除以基期量：20 / 100 = 20%。',takeaway:'增长率的分母是基期量。',selectedReason:choice===1?'':'应先求增长量，再除以100。',citations:job.result.mindMap.root.children[1].evidenceRefs});
  }
  if(p.includes('/compatibility/'))return r.fulfill({status:404,json:{error:'not_found'},headers:{'Access-Control-Allow-Origin':'*'}});
  unknown.push(p);return json({status:'not_requested'});
 });
 await page.goto('http://127.0.0.1:'+port);
 await page.locator('.file-picker input').setInputFiles(path.join(q,'Framewise-demo.mp4'));
 await page.locator('.player-stage video, .video-frame video, video').first().waitFor();
 await page.getByRole('button',{name:'视频工作台',exact:true}).click();
 const dialog=page.locator('.video-workspace[open]');
 await dialog.getByRole('button',{name:'分析区域',exact:true}).click();
 await dialog.getByRole('button',{name:'开始框选',exact:true}).waitFor({state:'visible'});
 await page.waitForFunction(()=>document.querySelector('.workspace-stage video')?.videoWidth>0);
 await dialog.getByRole('button',{name:'开始框选',exact:true}).click();
 const box=await dialog.locator('.workspace-surface').boundingBox();assert(box);
 await page.mouse.move(box.x+box.width*.035,box.y+box.height*.025);await page.mouse.down();
 await page.mouse.move(box.x+box.width*.96,box.y+box.height*.9,{steps:12});await page.mouse.up();
 await dialog.locator('.workspace-node').first().waitFor();
 await page.screenshot({path:path.join(q,'01-workspace.png')});await dialog.screenshot({path:path.join(q,'01-workspace-detail.png')});
 await dialog.getByRole('button',{name:'关闭视频工作台',exact:true}).click();
 await page.getByRole('tab',{name:'历史记录',exact:true}).click();await page.locator('.history-open').first().click();
 await page.locator('.smm-node').first().waitFor();await page.getByRole('button',{name:'适应画布',exact:true}).first().click();
 await page.waitForTimeout(600);await page.screenshot({path:path.join(q,'02-map.png')});await page.locator('.mind-map-panel').screenshot({path:path.join(q,'02-map-detail.png')});
 await page.locator('.smm-node').filter({hasText:/^增长率$/}).first().click();
 await page.waitForFunction(()=>document.querySelector('video')?.currentTime>=9.9);
 await page.locator('video').first().evaluate(v=>v.pause());
 const seek=await page.locator('video').first().evaluate(v=>v.currentTime);
 assert(seek>=9.9&&seek<12,'node should seek to the authored 10s segment');
 await page.getByRole('tab',{name:'字幕原文',exact:true}).click();
 await page.getByRole('tabpanel',{name:'字幕原文',exact:true}).getByText('增长量 = 120 - 100 = 20 件；增长率 = 增长量 / 基期量；20 / 100 = 20%',{exact:false}).first().waitFor();
 await page.waitForTimeout(650);await page.screenshot({path:path.join(q,'03-evidence.png')});
 await page.getByRole('tab',{name:'AI 练习',exact:true}).click();
 await page.locator('.practice-option input').nth(0).click();
 await page.getByText('答错了，看看解题思路',{exact:true}).waitFor();
 await page.locator('.practice-feedback').scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(q,'04-practice.png')});await page.locator('.practice-feedback').screenshot({path:path.join(q,'04-practice-detail.png')});
 assert.equal(await page.locator('.practice-review .review-play').isEnabled(),true);
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);assert.deepEqual(unknown,[]);
 const result={source:'running Vue application with authored preloaded API fixtures',endToEndModelMeasurement:false,paidModelCalls:0,realBackendWrites:0,externalRequests:external,errors,unknownRoutes:unknown,checks:{regionSaved:true,mapRendered:true,evidenceSeekSeconds:seek,practiceFeedback:true,reviewEnabled:true},api};
 await fs.writeFile(path.join(q,'ui-check.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify({...result,api:api.length}));
}finally{await browser.close();await server.close();}
