import {chromium} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],posts=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')posts.push(r.url())});
 const id='a5732f77-8f9b-452a-b838-7506f84ac0fa';
 const segments=[{id:'s1',startMs:1000,endMs:1900,text:'增长量等于现期减基期'},{id:'s2',startMs:5000,endMs:6500,text:'例题一，现期120，基期100'}];
 const ref=s=>({sourceType:'transcript',sourceId:s.id,startMs:s.startMs,endMs:s.endMs,quote:s.text});
 const leaf={id:'core_1',title:'增长量＝现期－基期',startMs:1000,endMs:1900,evidenceRefs:[ref(segments[0])],children:[]};
 const example={id:'example_0_0',title:'增长量计算例题',startMs:5000,endMs:6500,evidenceRefs:[ref(segments[1])],children:[]};
 const map={status:'completed',provider:'deepseek',promptVersion:'grounded-mind-map-v3-core-examples',root:{...leaf,id:'course',title:'课程知识导图',children:[leaf]},examples:[example]};
 await page.route(`**/api/transcriptions/${id}`,route=>route.fulfill({json:{id,status:'completed',result:{language:'zh',segments,visualEvidence:[],pageGroups:[],mindMap:map}}}));
 await page.route('**/api/**',route=>route.request().url().endsWith('/'+id)?route.fallback():route.fulfill({status:404,json:{error:'qa_no_other_calls'}}));
 await page.goto('http://127.0.0.1:5173/');
 await page.locator('input[type=file]').first().setInputFiles('E:/workp/videostudy/.local/qa/compat-h264-8s.mp4');
 await page.waitForFunction(()=>!!document.querySelector('#app').__vue_app__._instance.setupState.selectedFingerprint&&!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia);
 await page.evaluate(id=>{const s=document.querySelector('#app').__vue_app__._instance.setupState;localStorage.setItem(`analysisMedia:${id}`,JSON.stringify({name:s.selectedFile.name,size:s.selectedFile.size,fingerprint:s.selectedFingerprint}));s.existingJobId=id;},id);
 await page.getByRole('button',{name:'读取结果',exact:true}).click();

 page.setDefaultTimeout(8000);
 const opener=page.getByRole('button',{name:'放大查看',exact:true});
 await opener.click();
 const dialog=page.getByRole('dialog',{name:'课程思维导图'});
 await dialog.waitFor();
 const desktop=await dialog.boundingBox(); assert(desktop.width>1200 && desktop.height>750);
 const canvas=dialog.locator('.mind-map-canvas');
 await canvas.locator('svg').first().waitFor();
 assert((await canvas.boundingBox()).width>1100 && (await canvas.boundingBox()).height>600);
 await dialog.getByRole('button',{name:'聚焦主题',exact:true}).click();
 await dialog.getByRole('button',{name:'展开全部',exact:true}).click();
 await dialog.getByRole('button',{name:'放大导图',exact:true}).click();
 await dialog.getByRole('button',{name:'适应画布',exact:true}).click();
 await page.screenshot({path:'C:/Users/Administrator/.codex/visualizations/2026/10/10/01a123b6-19aa-7d32-8d1e-83e31cc453a1/map-dialog-desktop.png'});
 await page.keyboard.press('Escape'); await dialog.waitFor({state:'detached'});
 assert(await opener.evaluate(el=>el===document.activeElement));
 await opener.click(); await dialog.getByRole('button',{name:'关闭',exact:true}).click(); await dialog.waitFor({state:'detached'});
 await opener.click(); await dialog.getByText('增长量＝现期－基期',{exact:true}).first().click(); await dialog.waitFor({state:'detached'}); await page.waitForFunction(()=>document.querySelector('#app').__vue_app__._instance.setupState.selectedMindNode?.id==='core_1'); await page.setViewportSize({width:390,height:844}); await opener.click();
 const mobile=await dialog.boundingBox(); assert(mobile.width<=390 && mobile.height<=844);
 assert((await canvas.boundingBox()).height>400);
 await page.evaluate(()=>{document.querySelector('#app').__vue_app__._instance.setupState.mindMap=null});
 await dialog.waitFor({state:'detached'});
 assert.equal(posts.length,0);assert.deepEqual(errors,[]);
 console.log(JSON.stringify({largeCanvas:true,controls:true,escapeAndFocus:true,closeButton:true,mobile:true,courseResetCloses:true,modelRequests:0}));
}finally{await browser.close();}

