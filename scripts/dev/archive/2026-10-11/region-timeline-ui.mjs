import {chromium} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5173/');
 await page.locator('.workspace-entry').click();
 const file='E:/workp/videostudy/.local/qa/compat-h264-8s.mp4';
 await page.locator('.workspace-empty input[type=file]').setInputFiles(file);
 await page.waitForFunction(()=>document.querySelector('.workspace-stage video')?.videoWidth>0&&!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia);
 const state=()=>page.evaluate(()=>document.querySelector('#app').__vue_app__._instance.setupState.ignoredRegion);
 const seek=async(t)=>{await page.locator('input[aria-label="预览进度"]').evaluate((el,t)=>{el.value=t;el.dispatchEvent(new Event('input',{bubbles:true}))},t);await page.waitForFunction(t=>Math.abs(document.querySelector('.workspace-stage video').currentTime-t)<.01,t);await page.waitForTimeout(100);};
 const drag=async(x1,y1,x2,y2)=>{const b=await page.locator('.workspace-surface').boundingBox();await page.mouse.move(b.x+b.width*x1,b.y+b.height*y1);await page.mouse.down();await page.mouse.move(b.x+b.width*x2,b.y+b.height*y2,{steps:8});await page.mouse.up();};
 await seek(2);
 await page.getByRole('button',{name:'开始框选',exact:true}).click();await drag(.72,.65,.94,.91);
 let saved=await state();assert.equal(saved.nodes.length,1);assert.equal(saved.nodes[0].timeMs,0);const original=saved.nodes[0].region;
 await seek(4);
 await drag(.8,.8,.3,.3);saved=await state();assert.equal(saved.nodes.length,2);assert.equal(saved.nodes[1].timeMs,4000);const moved=saved.nodes[1].region;
 assert(Math.abs(moved.x-original.x)>.3);assert.equal(moved.width,original.width);
 // Resize at exactly the same time updates rather than appends.
 let b=await page.locator('.workspace-resize').boundingBox();await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();await page.mouse.move(b.x+b.width/2+25,b.y+b.height/2+15,{steps:5});await page.mouse.up();
 saved=await state();assert.equal(saved.nodes.length,2);assert(saved.nodes[1].region.width>moved.width);const resized=saved.nodes[1].region;
 await seek(6);await page.getByRole('button',{name:'重新框选',exact:true}).click();await drag(.1,.6,.35,.9);
 saved=await state();assert.deepEqual(saved.nodes.map(n=>n.timeMs),[0,4000,6000]);
 const rect=()=>page.locator('.workspace-region').evaluate(el=>({x:parseFloat(el.style.left)/100,y:parseFloat(el.style.top)/100,width:parseFloat(el.style.width)/100}));
 await seek(2);assert(Math.abs((await rect()).x-original.x)<.001);
 await seek(5);assert(Math.abs((await rect()).x-resized.x)<.001);
 await page.getByRole('button',{name:'删除区域节点 0:04',exact:true}).click();assert.deepEqual((await state()).nodes.map(n=>n.timeMs),[0,6000]);assert(Math.abs((await rect()).x-original.x)<.001);
 await page.getByRole('button',{name:'跳到区域节点 0:06',exact:true}).click();assert(Math.abs((await rect()).x-.1)<.001);
 saved=await state();await page.getByRole('button',{name:'关闭视频工作台'}).click();await page.locator('.workspace-entry').click();assert.deepEqual(await state(),saved);
 // Confirm actual analysis payload without sending any work to model services.
 await page.getByRole('button',{name:'关闭视频工作台'}).click();
 await page.evaluate(()=>{const original=window.fetch;window.regionUploads=[];window.fetch=async(url,options)=>{if(String(url).endsWith('/transcriptions')&&options?.method==='POST'){window.regionUploads.push(Object.fromEntries([...options.body.entries()].filter(([k])=>k!=='file')));return new Response('{}',{status:503,headers:{'Content-Type':'application/json'}})}return original(url,options)}});
 await page.getByRole('button',{name:'开始分析',exact:true}).click();await page.waitForFunction(()=>window.regionUploads.length===1&&!document.querySelector('#app').__vue_app__._instance.setupState.isAnalysisPending);
 assert.deepEqual(JSON.parse(await page.evaluate(()=>window.regionUploads[0].ignoredRegion)),saved);
 const bytes=await readFile(file);await page.locator('input[type=file]').first().setInputFiles({name:'other.mp4',mimeType:'video/mp4',buffer:Buffer.concat([bytes,Buffer.from([0])])});await page.waitForFunction(()=>!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia);assert.equal(await state(),null);
 await page.locator('input[type=file]').first().setInputFiles(file);await page.waitForFunction(()=>!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia);assert.deepEqual(await state(),saved);
 await page.locator('.workspace-entry').click();await page.waitForFunction(()=>document.querySelector('.workspace-stage video')?.videoWidth>0);
 await page.locator('.video-workspace').screenshot({path:'C:/Users/Administrator/.codex/visualizations/2026/10/10/01a123b6-19aa-7d32-8d1e-83e31cc453a1/region-timeline-workspace.png'});
 await page.setViewportSize({width:390,height:844});assert(await page.locator('.video-workspace').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
 await page.getByRole('button',{name:'清除全部节点',exact:true}).click();assert.equal(await state(),null);
 await page.keyboard.press('Escape');assert.deepEqual(errors,[]);
 console.log(JSON.stringify({firstAtZero:true,dragCreatesNode:true,resizeUpdatesSameTime:true,redrawCreatesNode:true,seekRestoresRegion:true,deleteRestoresPrevious:true,reopenAndFileRestore:true,multipartTimeline:true,mobileOverflow:false,clear:true,modelRequests:0,errors}));
}finally{await browser.close()}
