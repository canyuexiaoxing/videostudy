import {chromium} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));
 const A={x:.7,y:.6,width:.2,height:.3},B={x:.1,y:.1,width:.2,height:.2};let region=A,mode='detected';
 await page.route('**/api/video-region-detections',async route=>{const data=route.request().postDataJSON();requests.push(data);if(mode==='delay')await new Promise(r=>setTimeout(r,1200));try{await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({detections:data.frames.map(f=>({timeMs:f.timeMs,status:mode==='delay'?'detected':mode,region:['detected','delay'].includes(mode)?region:null}))})})}catch{}});
 await page.goto('http://127.0.0.1:5173/');await page.locator('.workspace-entry').click();await page.locator('.workspace-empty input[type=file]').setInputFiles('E:/workp/videostudy/.local/qa/compat-h264-8s.mp4');
 await page.waitForFunction(()=>document.querySelector('.workspace-stage video')?.videoWidth>0&&!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia);
 const state=()=>page.evaluate(()=>document.querySelector('#app').__vue_app__._instance.setupState.ignoredRegion);
 const seek=async t=>{await page.locator('input[aria-label="预览进度"]').evaluate((el,t)=>{el.value=t;el.dispatchEvent(new Event('input',{bubbles:true}))},t);await page.waitForFunction(t=>Math.abs(document.querySelector('.workspace-stage video').currentTime-t)<.01,t)};
 await seek(2);await page.getByRole('button',{name:'AI 识别当前区域',exact:true}).click();await page.getByRole('button',{name:'应用当前区域',exact:true}).waitFor();
 assert.equal(requests.length,1);assert.equal(requests[0].frames.length,1);assert.equal(requests[0].frames[0].timeMs,2000);assert.equal(await state(),null);
 await page.getByRole('button',{name:'应用当前区域',exact:true}).click();assert.deepEqual((await state()).nodes,[{timeMs:0,region:A}]);
 await page.evaluate(A=>{document.querySelector('#app').__vue_app__._instance.setupState.ignoredRegion={nodes:[{timeMs:0,region:A},{timeMs:6000,region:null}]}},A);
 region=B;await seek(4);await page.getByRole('button',{name:'AI 识别当前区域',exact:true}).click();await page.getByRole('button',{name:'应用当前区域',exact:true}).waitFor();
 assert.equal(requests[1].frames.length,1);assert.equal(requests[1].frames[0].timeMs,4000);await seek(5);await page.getByRole('button',{name:'应用当前区域',exact:true}).click();
 let saved=await state();assert.deepEqual(saved.nodes.map(n=>n.timeMs),[0,4000,6000]);assert.deepEqual(saved.nodes[1].region,B);
 for(const status of ['absent','uncertain']){mode=status;await page.getByRole('button',{name:'AI 识别当前区域',exact:true}).click();await page.locator('.workspace-error[role=alert]').waitFor();assert.equal(await page.getByRole('button',{name:'应用当前区域',exact:true}).count(),0);assert.deepEqual(await state(),saved)}
 mode='delay';const count=requests.length;await page.getByRole('button',{name:'AI 识别当前区域',exact:true}).click();while(requests.length===count)await page.waitForTimeout(40);await page.getByRole('button',{name:'取消识别',exact:true}).click();await page.waitForTimeout(1400);assert.equal(await page.getByRole('button',{name:'应用当前区域',exact:true}).count(),0);assert.deepEqual(await state(),saved);
 assert.deepEqual(errors,[]);console.log(JSON.stringify({singleFrame:true,currentTimePinned:true,previewBeforeApply:true,firstDefaultsToZero:true,laterPreservesFuture:true,absentAndUncertainPreserve:true,cancelPreserves:true,paidCalls:0,errors}));
}finally{await browser.close()}
