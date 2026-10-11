import {chromium} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));
 let mode='normal';
 const A={x:.7,y:.6,width:.2,height:.3},B={x:.1,y:.1,width:.2,height:.2};
 await page.route('**/api/video-region-detections',async route=>{
  const data=route.request().postDataJSON();requests.push(data);
  if(mode==='delay')await new Promise(r=>setTimeout(r,1500));
  if(mode==='failure'){await route.fulfill({status:503,contentType:'application/json',body:'{}'});return}
  try{await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({detections:data.frames.map(f=>({timeMs:f.timeMs,status:mode==='unknown'?'uncertain':'detected',region:mode==='unknown'?null:f.timeMs<4000?A:B}))})})}catch{}
 });
 await page.goto('http://127.0.0.1:5173/');await page.locator('.workspace-entry').click();
 await page.locator('.workspace-empty input[type=file]').setInputFiles('E:/workp/videostudy/.local/qa/compat-h264-8s.mp4');
 await page.waitForFunction(()=>document.querySelector('.workspace-stage video')?.videoWidth>0&&!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia);
 const state=()=>page.evaluate(()=>document.querySelector('#app').__vue_app__._instance.setupState.ignoredRegion);
 await page.getByRole('button',{name:'开始框选',exact:true}).click();
 const box=await page.locator('.workspace-surface').boundingBox();await page.mouse.move(box.x+box.width*.7,box.y+box.height*.6);await page.mouse.down();await page.mouse.move(box.x+box.width*.9,box.y+box.height*.9);await page.mouse.up();
 const manual=await state();
 await page.locator('input[aria-label="预览进度"]').evaluate(el=>{el.value=2;el.dispatchEvent(new Event('input',{bubbles:true}))});
 await page.getByRole('button',{name:'AI 扫描全片',exact:true}).click();await page.getByRole('button',{name:'应用自动框选',exact:true}).waitFor();
 assert.deepEqual(await state(),manual);assert.equal(requests[0].frames.length,4);const times=requests[0].frames.map(f=>f.timeMs);assert.equal(times[0],0);assert(times[1]>2500&&times[1]<2800);assert(times[2]>5200&&times[2]<5500);assert(times[3]>7800);
 for(const f of requests[0].frames)assert(f.image.startsWith('data:image/jpeg;base64,')&&f.image.length>1000);
 assert(Math.abs(await page.locator('.workspace-stage video').evaluate(v=>v.currentTime)-2)<.01);
 await page.locator('.video-workspace').screenshot({path:'C:/Users/Administrator/.codex/visualizations/2026/10/10/01a123b6-19aa-7d32-8d1e-83e31cc453a1/auto-region-preview.png'});
 await page.getByRole('button',{name:'应用自动框选',exact:true}).click();let saved=await state();assert.equal(saved.nodes.length,2);assert.deepEqual(saved.nodes[0].region,A);assert.deepEqual(saved.nodes[1].region,B);
 await page.getByRole('button',{name:'跳到区域节点 0:00',exact:true}).click();assert(Math.abs(await page.locator('.workspace-region').evaluate(e=>parseFloat(e.style.left)) -70)<.01);
 mode='delay';const n=requests.length;await page.getByRole('button',{name:'AI 扫描全片',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.workspace-state').textContent.includes('正在扫描'));while(requests.length===n)await page.waitForTimeout(50);
 await page.getByRole('button',{name:'取消扫描',exact:true}).click();await page.waitForTimeout(1800);assert.equal(await page.getByRole('button',{name:'应用自动框选',exact:true}).count(),0);assert.deepEqual(await state(),saved);
 mode='failure';await page.getByRole('button',{name:'AI 扫描全片',exact:true}).click();await page.locator('.workspace-error[role=alert]').waitFor();assert.deepEqual(await state(),saved);
 mode='unknown';await page.getByRole('button',{name:'AI 扫描全片',exact:true}).click();await page.getByRole('button',{name:'应用自动框选',exact:true}).waitFor();assert((await page.locator('.workspace-candidate').innerText()).includes('无法确定'));
 await page.setViewportSize({width:390,height:844});assert(await page.locator('.video-workspace').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
 await page.getByRole('button',{name:'放弃结果，保留原设置',exact:true}).click();assert.deepEqual(await state(),saved);
 mode='delay';await page.getByRole('button',{name:'AI 扫描全片',exact:true}).click();await page.getByRole('button',{name:'关闭视频工作台'}).click();await page.waitForTimeout(1800);assert.deepEqual(await state(),saved);
 assert.deepEqual(errors,[]);console.log(JSON.stringify({fourRealFrames:true,independentPlayback:true,previewBeforeApply:true,applyNodes:true,cancelIgnoresLateReply:true,providerFailurePreservesSettings:true,unknownExplicit:true,discardPreserves:true,closeCancels:true,mobileOverflow:false,paidModelCalls:0,errors}));
}finally{await browser.close()}
