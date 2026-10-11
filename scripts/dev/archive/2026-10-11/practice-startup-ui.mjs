import {chromium} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const id='22222222-2222-4222-8222-222222222222';
try{
 const page=await browser.newPage();const requests=[],errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(id=>{
  localStorage.setItem('lastAnalysisId',id);
  localStorage.setItem('analysisHistory:v1',JSON.stringify([{id,name:'历史课程',status:'completed',addedAt:new Date().toISOString()}]));
 },id);
 await page.route('http://127.0.0.1:18080/**',async route=>{
  const path=new URL(route.request().url()).pathname;requests.push(path);let data={};
  const ref={sourceId:'s1',startMs:0,endMs:1000,quote:'课程内容'};
  if(path.endsWith('/practice'))data=[{id:'set',title:'历史题库',status:'completed'}];
  else if(path.endsWith('/practice/set'))data={id:'set',title:'历史题库',status:'completed',questions:[{id:'q',nodeTitle:'知识点',kind:'single',title:'历史题目标记',prompt:'历史题目内容',options:['A','B','C','D']}]};
  else if(path.endsWith('/sessions'))data={id:'session',feedback:[]};
  else if(path.endsWith('/transcriptions/'+id))data={id,status:'completed',result:{language:'zh',segments:[{id:'s1',startMs:0,endMs:1000,text:'课程内容'}],pageGroups:[],visualEvidence:[],mindMap:{status:'completed',root:{id:'root',title:'课程',startMs:0,endMs:1000,evidenceRefs:[ref],children:[]}}}};
  else if(path.endsWith('/subtitles'))data={status:'not_requested'};
  else if(path.endsWith('/chapters'))data={status:'completed',result:{chapters:[]}};
  else if(path.endsWith('/overview'))data={status:'completed',result:{status:'empty'}};
  await route.fulfill({json:data});
 });
 await page.goto('http://127.0.0.1:5173/');await page.waitForTimeout(400);
 assert.equal(await page.locator('#analysis-id').inputValue(),'','startup must not activate old analysis');
 assert.equal(requests.filter(p=>p.includes('/practice')).length,0,'no practice API call before opening a course');
 assert.equal(await page.locator('#tab-practice input[type=radio]').count(),0,'no automatic demonstration questions');
 // Typing an id is only a draft, not opening a course.
 await page.locator('#analysis-id').fill(id);await page.waitForTimeout(200);
 assert.equal(requests.filter(p=>p.includes('/practice')).length,0);
 await page.evaluate(()=>{const s=document.querySelector('#app').__vue_app__._instance.setupState;return s.openHistory({id:'22222222-2222-4222-8222-222222222222',name:'历史课程',status:'completed'});});
 await page.waitForFunction(()=>document.querySelector('#tab-practice')?.textContent.includes('历史题目内容'));
 assert(requests.some(p=>p.endsWith('/practice')));
 await page.reload();await page.waitForTimeout(300);
 assert.equal(await page.locator('#analysis-id').inputValue(),'');
 assert.equal(await page.locator('#tab-practice input[type=radio]').count(),0);
 assert.deepEqual(errors,[]);console.log(JSON.stringify({startupEmpty:true,noPrematurePracticeFetch:true,historyRestoresQuestions:true,reloadEmpty:true,errors}));
}finally{await browser.close();}
