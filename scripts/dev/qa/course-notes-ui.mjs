import {pathToFileURL,fileURLToPath} from 'node:url';
import {readFileSync,readdirSync} from 'node:fs';
import {join} from 'node:path';
import assert from 'node:assert/strict';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const mock=JSON.parse(readFileSync(fileURLToPath(new URL('../../../.local/qa/grouped-course-mock.json',import.meta.url)),'utf8'));
const id=mock.id, url=`http://127.0.0.1:18080/api/transcriptions/${id}`;
const before=await (await fetch(url)).json();
const map=mock.result.mindMap;map.status='completed';
map.examples=mock.result.segments.slice(0,2).map((s,i)=>({id:`verified_example_${i}`,title:`模拟独立例题 ${i+1}`,startMs:s.startMs,endMs:s.endMs,children:[],evidenceRefs:[{sourceType:'transcript',sourceId:s.id,startMs:s.startMs,endMs:s.endMs,quote:s.text}]}));
const framesRoot=fileURLToPath(new URL('../../../.local/keyframes/',import.meta.url));
const fixturePath=readdirSync(framesRoot).map(d=>join(framesRoot,d)).flatMap(d=>readdirSync(d).filter(f=>f.endsWith('.jpg')).slice(0,1).map(f=>join(d,f)))[0];
const screenshot=readFileSync(fixturePath);
let overviewReady=false;
const frame=mock.result.mindMap.root.children[0].evidenceRefs.find(ref=>ref.sourceType==='image').startMs;
const notes={status:'completed',headline:'增长量课程',summary:[{text:'这节课介绍增长量的概念、计算方法与典型例题。'}],notes:[{title:'一、增长量计算',anchor:{startMs:1000},image:{startMs:frame},points:[{label:'核心概念',text:'在基期基础上增加的数量。'}],children:[{title:'1. 给基期、增长率',anchor:{startMs:26000},image:null,points:[{label:'公式',text:'增长量＝基期×增长率'},{label:'易错点',text:'注意增长率的单位。'}],children:[]}]},{title:'二、例题解析',anchor:{startMs:56000},image:null,points:[{label:'解题要点',text:'先判断已知条件，再选计算方法。'}],children:[]}]};
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}), errors=[], mutations=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{
  const req=route.request(),u=new URL(req.url());
  if(req.method()!=='GET'){mutations.push(u.pathname);return route.fulfill({status:409,body:'offline test blocks writes'})}
  if(u.pathname.includes('/frames/'))return route.fulfill({contentType:'image/jpeg',body:screenshot});
  if(u.pathname==='/api/transcriptions')return route.fulfill({json:[{id,status:'completed',name:null,createdAt:new Date().toISOString()}]});
  if(u.pathname.endsWith('/overview'))return route.fulfill({json:overviewReady?{status:'completed',result:notes}:{status:'processing'}});
  if(u.pathname===`/api/transcriptions/${id}`)return route.fulfill({json:mock});
  return route.continue();
 });
 await page.goto('http://127.0.0.1:5173/');
 await page.getByRole('button',{name:'高级选项',exact:true}).click();
 assert.equal(await page.getByRole('button',{name:'原流程',exact:true}).getAttribute('aria-pressed'),'true');
 await page.getByRole('button',{name:'分组后汇总',exact:true}).click();
 assert.equal(await page.locator('.mode-picker select').inputValue(),'both');assert(await page.locator('.mode-picker select').isDisabled());
 await page.getByRole('tab',{name:'历史记录',exact:true}).click();
 await page.locator('.history-item').filter({hasText:id}).locator('.history-open').click();
 await page.waitForFunction(()=>document.querySelector('#app').__vue_app__._instance.setupState.mindMap?.root.children.length>0);
 await page.getByRole('tab',{name:'思维导图',exact:true}).click();
 await page.locator('.video-overview summary').click();
 await page.getByText('正在生成 AI 课程笔记…',{exact:true}).waitFor();
 assert(await page.getByRole('button',{name:'适应画布',exact:true}).isVisible());
 overviewReady=true;
 await page.getByText('一、增长量计算',{exact:true}).waitFor();
 assert.equal(await page.locator('.note-time').count(),3);
 await page.getByRole('button',{name:'回看1. 给基期、增长率 00:26',exact:true}).click();
 assert.equal(await page.evaluate(()=>document.querySelector('#app').__vue_app__._instance.setupState.currentPlaybackMs),26000);
 await page.locator('.note-image').waitFor();
 await page.waitForFunction(()=>[...document.querySelectorAll('.note-image')].some(img=>img.complete&&img.naturalWidth>0));
 await page.screenshot({path:fileURLToPath(new URL('../../../.local/qa/course-notes-desktop.png',import.meta.url)),fullPage:true});
 const metrics=await page.evaluate(()=>{
  const state=document.querySelector('#app').__vue_app__._instance.setupState;
  const concept=state.mindMap.root.children[0];state.selectMindMapNode(concept);
  return {concepts:state.mindMap.root.children.length,details:concept.details.length,examples:state.exampleTimeline.length};
 });
 assert.equal(metrics.concepts,1);assert.equal(metrics.examples,2);assert(metrics.details>0);
 const layout=await page.locator('.mind-map-panel').evaluate(el=>{
  const canvas=el.querySelector('.map-canvas-shell'),details=el.querySelector('.mind-source');
  return {canvasBeforeDetails:!!(canvas.compareDocumentPosition(details)&Node.DOCUMENT_POSITION_FOLLOWING),canvasHeight:canvas.getBoundingClientRect().height};
 });
 assert(layout.canvasBeforeDetails);assert(layout.canvasHeight>=380);

 await page.locator('.knowledge-details summary').first().click();
 await page.locator('.mind-evidence-image').first().waitFor();
 await page.waitForFunction(()=>[...document.querySelectorAll('.mind-evidence-image')].some(img=>img.complete&&img.naturalWidth>0));
 assert.equal(await page.getByText('需核对：离线模拟输出，不用于证明实际提炼准确率').count(),0);
 await page.getByRole('button',{name:'放大查看',exact:true}).click();await page.locator('.expanded-map-dialog[open]').waitFor();await page.getByRole('button',{name:'关闭',exact:true}).click();
 await page.setViewportSize({width:390,height:844});assert(await page.locator('.knowledge-details').first().evaluate(el=>el.scrollWidth<=el.clientWidth+1));
 await page.screenshot({path:fileURLToPath(new URL('../../../.local/qa/course-notes-mobile.png',import.meta.url)),fullPage:true});
 assert.deepEqual(errors,[]);assert.deepEqual(mutations,[]);
 const after=await (await fetch(url)).json();assert.deepEqual(after,before);
 console.log(JSON.stringify({notesHierarchy:true,oneTimestampPerHeading:true,mainMapUsableWhileNotesProcessing:true,...metrics,defaultOptInFalse:true,realImageDisplayed:true,expandedMap:true,mobilePassed:true,historyUnchanged:true,paidModelCalls:0}));
}finally{await browser.close()}
