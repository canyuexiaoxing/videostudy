import {pathToFileURL,fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const root=fileURLToPath(new URL('../../../',import.meta.url));
const id='12345678-1234-1234-1234-123456789abc';
const segment={id:'t1',startMs:0,endMs:1000,text:'增长量等于现期减基期'};
const ref={sourceType:'transcript',sourceId:'t1',startMs:0,endMs:1000,quote:segment.text};
const complete={status:'completed',provider:'offline',modelId:'offline',promptVersion:'offline',createdAt:new Date().toISOString(),root:{id:'course',title:'模拟课程',startMs:0,endMs:1000,evidenceRefs:[ref],children:[{id:'formula',title:'增长量',startMs:0,endMs:1000,evidenceRefs:[ref],children:[],details:[]}],details:[]},examples:[],uncertainties:[]};
const result={segments:[segment],pageGroups:[],visualEvidence:[],language:'zh',mindMap:{...complete,status:'failed',root:{...complete.root,children:[]}}};
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
const outcomes=[];
try{
 for(const kind of ['map','course']){
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],posts=[];let release;
  let record={id,status:kind==='map'?'completed':'failed',error:kind==='course'?'模拟分析失败':null,result:kind==='map'?result:null};
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/**',async route=>{
   const req=route.request(),u=new URL(req.url()),p=u.pathname,headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'GET,POST,OPTIONS'};
   if(req.method()==='OPTIONS')return route.fulfill({status:204,headers});
   if(req.method()!=='GET'){
    posts.push(p);assert.equal(p,`/api/transcriptions/${id}/${kind==='map'?'mind-map':'retry'}`);
    await new Promise(resolve=>release=resolve);
    record={id,status:'completed',error:null,result:{...result,mindMap:complete}};
    return route.fulfill({json:kind==='map'?complete:{id,status:'queued'},headers});
   }
   if(p==='/api/transcriptions')return route.fulfill({json:[{id,status:record.status,name:'模拟失败课程',createdAt:new Date().toISOString()}],headers});
   if(p===`/api/transcriptions/${id}`)return route.fulfill({json:record,headers});
   if(p.endsWith('/overview'))return route.fulfill({json:{status:'not_requested'},headers});
   if(p.endsWith('/practice'))return route.fulfill({json:[],headers});
   if(p.endsWith('/chapters'))return route.fulfill({json:{status:'completed',result:{chapters:[]}},headers});
   return route.fulfill({json:{status:'not_requested'},headers});
  });
  await page.goto('http://127.0.0.1:5173/');await page.getByRole('tab',{name:'历史记录',exact:true}).click();
  await page.locator('.history-item').filter({hasText:id}).locator('.history-open').click();
  await page.getByRole('tab',{name:'思维导图',exact:true}).click();
  const retry=page.getByRole('button',{name:kind==='map'?'重新分析导图':'重新分析课程',exact:true});await retry.waitFor();assert.equal(posts.length,0);
  await retry.scrollIntoViewIfNeeded();await page.screenshot({path:root+`.local/qa/analysis-retry-${kind}-desktop.png`,fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.locator('.analysis-retry-card').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
  await retry.click();await page.waitForFunction(()=>document.querySelector('.analysis-retry-card button')?.disabled);assert(await retry.isDisabled());assert.equal(posts.length,1);
  await retry.evaluate(el=>el.click());assert.equal(posts.length,1);release();
  await page.waitForFunction(()=>document.querySelector('#app').__vue_app__._instance.setupState.mindMap?.status==='completed');
  assert.equal(await page.locator('.analysis-retry-card').count(),0);assert.deepEqual(errors,[]);outcomes.push({kind,endpoint:posts[0],duplicatePrevented:true,restored:true});await page.close();
 }
 console.log(JSON.stringify({outcomes,paidModelCalls:0}));
}finally{await browser.close()}
