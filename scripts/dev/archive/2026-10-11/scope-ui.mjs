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
 const map={status:'completed',provider:'deepseek',promptVersion:'grounded-mind-map-v3-core-examples',root:{...leaf,id:'course',title:'课程知识导图',children:[{...leaf,id:'topic',title:'增长量计算',children:[{...leaf,id:'detail',title:'公式细节',children:[leaf]},{...leaf,id:'condition',title:'适用条件'}]}]},examples:[example]};
 await page.route(`**/api/transcriptions/${id}`,route=>route.fulfill({json:{id,status:'completed',result:{language:'zh',segments,visualEvidence:[],pageGroups:[],mindMap:map}}}));
 await page.route('**/api/**',route=>route.request().url().endsWith('/'+id)?route.fallback():route.fulfill({json:[]}));
 await page.goto('http://127.0.0.1:5173/');
 await page.locator('input[type=file]').first().setInputFiles('E:/workp/videostudy/.local/qa/compat-h264-8s.mp4');
 await page.waitForFunction(()=>!!document.querySelector('#app').__vue_app__._instance.setupState.selectedFingerprint&&!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia);
 await page.evaluate(id=>{const s=document.querySelector('#app').__vue_app__._instance.setupState;localStorage.setItem(`analysisMedia:${id}`,JSON.stringify({name:s.selectedFile.name,size:s.selectedFile.size,fingerprint:s.selectedFingerprint}));s.existingJobId=id;},id);
 await page.getByRole('button',{name:'读取结果',exact:true}).click(); await page.locator('.example-timeline').waitFor();

 await page.getByRole('tab',{name:'AI 练习',exact:true}).click();
 const scope=page.locator('.practice-settings select').first(); await scope.waitFor();
 assert.deepEqual(await scope.locator('option').evaluateAll(opts=>opts.map(o=>o.value)),['','topic']);
 await page.evaluate(()=>{const s=document.querySelector('#app').__vue_app__._instance.setupState;s.selectedMindNode=s.mindMap.root.children[0].children[0].children[0]});
 await page.waitForFunction(()=>document.querySelector('.practice-settings select')?.value==='topic');
 let payload;
 await page.route(`**/api/transcriptions/${id}/practice`,route=>{if(route.request().method()==='POST'){payload=route.request().postDataJSON();return route.fulfill({json:{id:'fixture',title:'增长量计算',status:'completed',questions:[]}})}return route.fulfill({json:[]})});
 await page.getByRole('button',{name:'生成练习',exact:true}).click();
 await page.waitForTimeout(150);assert.equal(payload.nodeId,'topic');
 await page.evaluate(()=>{const s=document.querySelector('#app').__vue_app__._instance.setupState;s.selectedMindNode=null;s.mindMap={...s.mindMap,root:{...s.mindMap.root,children:[]}}});
 await page.waitForFunction(()=>document.querySelector('.practice-settings select')?.value==='');
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({branchOptions:true,leafSelectsAncestor:true,requestUsesTopic:true,mapChangeResetsScope:true,realModelCalls:0}));
}finally{await browser.close();}



