import {pathToFileURL,fileURLToPath} from 'node:url';
import {mkdirSync,writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const out=fileURLToPath(new URL('../../../.local/qa/person-workspace/',import.meta.url));mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
const id='11111111-1111-4111-8111-111111111111';
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],uploads=[];
 let releaseUpload;const gate=new Promise(resolve=>releaseUpload=resolve);
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;
  if(req.method()==='POST'&&path==='/api/transcriptions'){
   uploads.push(req.postDataBuffer().toString('latin1'));await gate;
   return route.fulfill({status:202,json:{id,status:'queued'}});
  }
  if(req.method()==='GET'&&path===`/api/transcriptions/${id}`)return route.fulfill({json:{id,status:'failed',error:'offline_ui_test'}});
  if(req.method()==='GET')return route.fulfill({json:[]});
  return route.fulfill({status:409,json:{error:'offline_test_no_writes'}});
 });
 await page.goto('http://127.0.0.1:5173/');await page.locator('.workspace-entry').click();
 await page.locator('.workspace-empty input[type=file]').setInputFiles(fileURLToPath(new URL('../../../.local/qa/compat-h264-8s.mp4',import.meta.url)));
 await page.waitForFunction(()=>document.querySelector('.workspace-stage video')?.videoWidth>0&&!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia);
 await page.evaluate(()=>{
  const state=document.querySelector('#app').__vue_app__._instance.setupState;
  state.saveAnalysisRegion({nodes:[{timeMs:0,region:{x:.1,y:.1,width:.8,height:.7}},{timeMs:4000,region:{x:.2,y:.15,width:.7,height:.65}}]});
  state.saveIgnoredRegion({nodes:[{timeMs:0,region:{x:.65,y:.55,width:.2,height:.15}},{timeMs:4000,region:null}]});
 });
 await page.getByRole('button',{name:'人物过滤',exact:true}).click();
 const saved=await page.evaluate(()=>JSON.stringify([document.querySelector('#app').__vue_app__._instance.setupState.analysisRegion,document.querySelector('#app').__vue_app__._instance.setupState.ignoredRegion]));
 assert.equal(await page.locator('[data-readonly-region=analysis]').count(),1);assert.equal(await page.locator('[data-readonly-region=ignore]').count(),1);
 assert.equal(await page.locator('[data-readonly-region=analysis]').evaluate(el=>getComputedStyle(el).pointerEvents),'none');
 assert.equal(await page.locator('.workspace-resize').count(),0);
 await page.locator('input[aria-label="预览进度"]').evaluate(el=>{el.value=5;el.dispatchEvent(new Event('input',{bubbles:true}))});
 await page.waitForFunction(()=>document.querySelector('[data-readonly-region=analysis]')?.style.left==='20%');
 assert.equal(await page.locator('[data-readonly-region=ignore]').count(),0);
 await page.locator('input[aria-label="预览进度"]').evaluate(el=>{el.value=0;el.dispatchEvent(new Event('input',{bubbles:true}))});
 await page.waitForFunction(()=>document.querySelector('[data-readonly-region=analysis]')?.style.left==='10%');
 assert.equal(await page.locator('[data-readonly-region=ignore]').count(),1);
 assert.equal(await page.evaluate(()=>JSON.stringify([document.querySelector('#app').__vue_app__._instance.setupState.analysisRegion,document.querySelector('#app').__vue_app__._instance.setupState.ignoredRegion])),saved);
 const toggle=page.getByRole('switch',{name:'排除人物动作'});
 assert.equal(await toggle.getAttribute('aria-checked'),'false');await toggle.focus();await page.keyboard.press('Space');assert.equal(await toggle.getAttribute('aria-checked'),'true');
 await page.getByRole('button',{name:'关闭视频工作台'}).click();await page.locator('.workspace-entry').click();await page.getByRole('button',{name:'人物过滤',exact:true}).click();assert.equal(await toggle.getAttribute('aria-checked'),'true');
 await page.waitForFunction(()=>{const video=document.querySelector('.workspace-stage video');return video&&video.readyState>=2&&!video.seeking});
 await page.locator('dialog').screenshot({path:out+'desktop.png'});
 await page.evaluate(()=>{void document.querySelector('#app').__vue_app__._instance.setupState.runTranscription()});
 await page.waitForFunction(()=>document.querySelector('#app').__vue_app__._instance.setupState.analysisState==='uploading');
 await page.waitForTimeout(100);assert.equal(uploads.length,1);assert.match(uploads[0],/name="personSelectionMode"\r\n\r\nadjacent/);
 await toggle.click();assert.equal(await toggle.getAttribute('aria-checked'),'false');assert.match(await page.locator('.workspace-person .workspace-scope').innerText(),/当前任务继续沿用/);
 assert.match(uploads[0],/name="personSelectionMode"\r\n\r\nadjacent/);releaseUpload();
 await page.waitForFunction(()=>!document.querySelector('#app').__vue_app__._instance.setupState.isAnalysisPending);
 await page.setViewportSize({width:390,height:844});await page.locator('dialog').screenshot({path:out+'mobile.png'});
 const widths=await page.locator('dialog').evaluate(el=>({client:el.clientWidth,scroll:el.scrollWidth}));assert(widths.scroll<=widths.client+2,'mobile horizontal overflow');
 assert.deepEqual(errors,[]);writeFileSync(out+'ui-results.json',JSON.stringify({passed:true,uploads:uploads.length,paidCalls:0,checks:['saved include/exclude overlays','readonly overlays','timed region preview','default off','keyboard switch','per-video restoration','multipart adjacent','pending task snapshot','mobile no horizontal overflow'],errors},null,2));
 console.log('Person workspace UI passed: toggle, persistence, upload snapshot, mobile. No real server writes or paid calls.');
}finally{await browser.close()}
