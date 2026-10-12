import {pathToFileURL,fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));
 const estimates=[{x:.71,y:.75,width:.18,height:.25},{x:.74,y:.79,width:.13,height:.21},{x:.72,y:.78,width:.15,height:.22},{x:.735,y:.775,width:.145,height:.225}];
 await page.route('**/api/video-region-detections',async route=>{
  const data=route.request().postDataJSON();requests.push(data);
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({detections:data.frames.map((f,i)=>({timeMs:f.timeMs,status:'detected',region:estimates[i%4],precision:'estimated'}))})});
 });
 await page.goto('http://127.0.0.1:5173/');await page.locator('.workspace-entry').click();
 await page.locator('.workspace-empty input[type=file]').setInputFiles(fileURLToPath(new URL('../../../.local/qa/compat-h264-8s.mp4',import.meta.url)));
 await page.waitForFunction(()=>document.querySelector('.workspace-stage video')?.videoWidth>0&&!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia);
 const state=()=>page.evaluate(()=>JSON.parse(JSON.stringify(document.querySelector('#app').__vue_app__._instance.setupState.ignoredRegion)));
 await page.getByRole('button',{name:'开始框选',exact:true}).click();
 const box=await page.locator('.workspace-surface').boundingBox();await page.mouse.move(box.x+box.width*.7,box.y+box.height*.6);await page.mouse.down();await page.mouse.move(box.x+box.width*.9,box.y+box.height*.9);await page.mouse.up();
 const manual=await state();
 await page.locator('input[aria-label="预览进度"]').evaluate(el=>{el.value=2;el.dispatchEvent(new Event('input',{bubbles:true}))});
 async function scan(){await page.getByRole('button',{name:'AI 扫描全片',exact:true}).click();await page.getByRole('button',{name:'应用自动框选',exact:true}).waitFor();}
 async function edit(){await page.getByRole('button',{name:'手动调整候选框',exact:true}).click();const r=await page.locator('.workspace-region').boundingBox();await page.mouse.move(r.x+r.width*.4,r.y+r.height*.4);await page.mouse.down();await page.mouse.move(r.x+r.width*.4+12,r.y+r.height*.4-10);await page.mouse.up();}
 await scan();assert.deepEqual(await state(),manual);assert.equal(requests[0].frames.length,4);assert.match(await page.locator('.workspace-candidate').innerText(),/1 个区域节点/);
 await edit();assert.deepEqual(await state(),manual);
 await page.getByRole('button',{name:'放弃结果，保留原设置',exact:true}).click();assert.deepEqual(await state(),manual);
 await scan();await edit();await page.getByRole('button',{name:'应用自动框选',exact:true}).click();const saved=await state();assert.equal(saved.nodes.length,1);assert.equal(saved.nodes[0].timeMs,0);assert.notDeepEqual(saved,manual);assert.deepEqual(errors,[]);
 console.log('Fixed webcam jitter: four frames, one node. Editing remains candidate-only; discard preserves manual settings; apply saves corrected node at zero. No paid AI calls.');
}finally{await browser.close()}
