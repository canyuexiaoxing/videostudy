import {chromium} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[],posts=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')posts.push(r.url())});
 await page.goto('http://127.0.0.1:5173/');
 await page.locator('.workspace-entry').click();
 await page.locator('.video-workspace').waitFor({state:'visible'});
 assert(await page.getByRole('heading',{name:'先选择一段视频'}).isVisible());
 assert(await page.getByRole('button',{name:'开始框选',exact:true}).isDisabled());
 const file='E:/workp/videostudy/.local/qa/compat-h264-8s.mp4';
 await page.locator('.workspace-empty input[type=file]').setInputFiles(file);
 await page.waitForFunction(()=>document.querySelector('.workspace-stage video')?.videoWidth>0&&!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia);
 await page.getByRole('button',{name:'开始框选',exact:true}).click();
 let box=await page.locator('.workspace-surface').boundingBox();assert(box?.width>0);
 const drag=async(x1,y1,x2,y2)=>{const b=await page.locator('.workspace-surface').boundingBox();await page.mouse.move(b.x+b.width*x1,b.y+b.height*y1);await page.mouse.down();await page.mouse.move(b.x+b.width*x2,b.y+b.height*y2,{steps:8});await page.mouse.up();};
 await drag(.72,.65,.94,.91);
 await page.getByRole('button',{name:'确认区域',exact:true}).click();
 await page.waitForFunction(()=>!!document.querySelector('#app').__vue_app__._instance.setupState.ignoredRegion);
 const state=()=>page.evaluate(()=>document.querySelector('#app').__vue_app__._instance.setupState.ignoredRegion);
 const saved=await state();assert(Math.abs(saved.x-.72)<.01);assert(Math.abs(saved.width-.22)<.01);
 await page.getByRole('button',{name:'关闭视频工作台'}).click();
 await page.locator('.workspace-entry').click();await page.locator('.workspace-region').waitFor({state:'visible'});
 await page.getByRole('button',{name:'重新框选',exact:true}).click();await drag(.1,.1,.3,.3);
 await page.getByRole('button',{name:'关闭视频工作台'}).click();assert.deepEqual(await state(),saved);
 await page.evaluate(()=>{
  const original=window.fetch;window.regionUploads=[];
  window.fetch=async(url,options)=>{
   if(String(url).endsWith('/transcriptions')&&options?.method==='POST'){
    window.regionUploads.push(Object.fromEntries([...options.body.entries()].filter(([k])=>k!=='file')));
    return new Response('{}',{status:503,headers:{'Content-Type':'application/json'}});
   }
   return original(url,options);
  };
 });
 await page.getByRole('button',{name:'开始分析',exact:true}).click();
 await page.waitForFunction(()=>window.regionUploads.length===1&&!document.querySelector('#app').__vue_app__._instance.setupState.isAnalysisPending);
 assert.deepEqual(JSON.parse(await page.evaluate(()=>window.regionUploads[0].ignoredRegion)),saved);
 // Selecting a different file must not reuse the prior video's mask.
 const bytes=await readFile(file);
 await page.locator('input[type=file]').first().setInputFiles({name:'other.mp4',mimeType:'video/mp4',buffer:Buffer.concat([bytes,Buffer.from([0])])});
 await page.waitForFunction(()=>!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia);
 assert.equal(await state(),null);
 await page.locator('input[type=file]').first().setInputFiles(file);
 await page.waitForFunction(()=>!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia);
 assert.deepEqual(await state(),saved);
 await page.locator('.workspace-entry').click();
 await page.locator('.video-workspace').screenshot({path:'C:/Users/Administrator/.codex/visualizations/2026/10/10/01a123b6-19aa-7d32-8d1e-83e31cc453a1/video-workspace.png'});
 await page.setViewportSize({width:390,height:844});
 assert(await page.locator('.video-workspace').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
 await page.getByRole('button',{name:'清除区域',exact:true}).click();assert.equal(await state(),null);
 await page.keyboard.press('Escape');await page.locator('.video-workspace').waitFor({state:'detached'});
 await page.getByRole('button',{name:'开始分析',exact:true}).click();
 await page.waitForFunction(()=>window.regionUploads.length===2);
 assert.equal(await page.evaluate(()=>window.regionUploads[1].ignoredRegion),undefined);
 assert.deepEqual(errors,[]);assert.equal(posts.length,0);
 console.log(JSON.stringify({emptyState:true,regionDrawing:true,confirmAndReopen:true,unconfirmedDiscarded:true,fileIsolation:true,sameFileRestore:true,clear:true,escapeCloses:true,mobileOverflow:false,multipartRegion:true,clearOmitsRegion:true,modelRequests:0,errors}));
}finally{await browser.close();}
