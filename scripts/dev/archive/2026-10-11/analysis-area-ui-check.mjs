import {chromium} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:5173/');
 await page.locator('.workspace-entry').click();await page.locator('.workspace-empty input[type=file]').setInputFiles('E:/workp/videostudy/.local/qa/compat-h264-8s.mp4');
 await page.waitForFunction(()=>document.querySelector('.workspace-stage video')?.videoWidth>0&&!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia);
 const state=()=>page.evaluate(()=>{const s=document.querySelector('#app').__vue_app__._instance.setupState;return {analysis:s.analysisRegion,ignored:s.ignoredRegion}});
 const draw=async(a,b,c,d)=>{await page.getByRole('button',{name:/^(开始框选|重新框选)$/}).click();const r=await page.locator('.workspace-surface').boundingBox();await page.mouse.move(r.x+r.width*a,r.y+r.height*b);await page.mouse.down();await page.mouse.move(r.x+r.width*c,r.y+r.height*d,{steps:6});await page.mouse.up()};
 await page.getByRole('button',{name:'分析区域',exact:true}).click();await draw(.2,.2,.7,.7);
 let s=await state();assert.equal(s.analysis.nodes[0].timeMs,0);
 await page.getByRole('button',{name:'忽略区域',exact:true}).click();await draw(.8,.8,.95,.95);
 assert.equal(await page.locator('.workspace-region').count(),2);assert(await page.getByText('忽略区域位于分析范围外，当前不生效。').isVisible());
 await draw(.6,.6,.8,.8);assert(await page.getByText('只分析绿色框内内容，并排除与蓝色框重叠的部分。').isVisible());
 s=await state();await draw(.1,.1,.85,.85);assert.deepEqual(await state(),s);assert(await page.locator('.workspace-error').isVisible());
 await page.getByRole('button',{name:'关闭视频工作台'}).click();
 await page.evaluate(()=>{const orig=window.fetch;window.regionUploads=[];window.fetch=async(u,o)=>{if(String(u).endsWith('/transcriptions')&&o?.method==='POST'){window.regionUploads.push(o.body.get('ignoredRegion'));return new Response('{}',{status:503})}return orig(u,o)}});
 await page.getByRole('button',{name:'开始分析',exact:true}).click();await page.waitForFunction(()=>window.regionUploads.length===1);assert.deepEqual(JSON.parse(await page.evaluate(()=>window.regionUploads[0])),{analysisRegion:s.analysis,ignoredRegion:s.ignored});
 await page.locator('.workspace-entry').click();await page.getByRole('button',{name:'分析区域',exact:true}).click();await page.getByRole('button',{name:'清除分析范围',exact:true}).click();assert.equal((await state()).analysis,null);assert.deepEqual((await state()).ignored,s.ignored);
 await page.setViewportSize({width:390,height:844});assert(await page.locator('.video-workspace').evaluate(el=>el.scrollWidth<=el.clientWidth+1));assert.deepEqual(errors,[]);
 console.log('Analysis/include + ignore overlap, outside hint, full coverage guard, actual multipart payload, independent clear and mobile layout passed; no model requests.');
}finally{await browser.close()}
