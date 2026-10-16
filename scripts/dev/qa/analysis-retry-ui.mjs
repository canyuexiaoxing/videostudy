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
 for(const kind of ['map','partial','regenerate','regenerate-failure','course']){
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],posts=[];let release;
  let record={id,status:kind!=='course'?'completed':'failed',error:kind==='course'?'模拟分析失败':null,result:kind.startsWith('regenerate')?{...result,mindMap:complete}:kind==='partial'?{...result,mindMap:{...complete,status:'failed',uncertainties:['节点来源校验失败：节点缺少实际来源（children[1]），已拒绝；节点：幂级数求导公式']}}:kind!=='course'?result:null};
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/**',async route=>{
   const req=route.request(),u=new URL(req.url()),p=u.pathname,headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'GET,POST,OPTIONS'};
   if(req.method()==='OPTIONS')return route.fulfill({status:204,headers});
   if(req.method()!=='GET'){
    if(kind.startsWith('regenerate'))assert.equal(u.searchParams.get('refresh'),'true');
    posts.push(p);assert.equal(p,`/api/transcriptions/${id}/${kind!=='course'?'mind-map':'retry'}`);
    await new Promise(resolve=>release=resolve);
    if(kind==='regenerate-failure')return route.fulfill({status:502,json:{error:'mind_map_generation_failed'},headers});
    record={id,status:'completed',error:null,result:{...result,mindMap:complete}};
    return route.fulfill({json:kind!=='course'?complete:{id,status:'queued'},headers});
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
  if(kind==='partial'){
   assert.match(await page.locator('.analysis-retry-card').innerText(),/导图部分生成/);
   const details=page.locator('.map-failure-details');await details.waitFor();
   assert.equal(await details.getAttribute('open'),null);
   await details.locator('summary').click();assert.match(await details.innerText(),/children\[1\].*幂级数求导公式/);
  }
  const retry=page.getByRole('button',{name:kind.startsWith('regenerate')?'重新生成导图':kind!=='course'?'重新分析导图':'重新分析课程',exact:true});await retry.waitFor();assert.equal(posts.length,0);
  await retry.scrollIntoViewIfNeeded();await page.screenshot({path:root+`.local/qa/analysis-retry-${kind}-desktop.png`,fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.locator(kind.startsWith('regenerate')?'.mind-map-heading-actions':'.analysis-retry-card').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
  await retry.click();await page.waitForFunction(()=>document.querySelector('.analysis-retry-card button:disabled, .regenerate-map-button:disabled'));assert(await retry.isDisabled());assert.equal(posts.length,1);
  if(kind.startsWith('regenerate'))assert.equal(await page.locator('.mind-map-panel .smm-node').count()>0,true);
  await retry.evaluate(el=>el.click());assert.equal(posts.length,1);release();
  await page.waitForFunction(()=>document.querySelector('#app').__vue_app__._instance.setupState.mindMap?.status==='completed' && !document.querySelector('#app').__vue_app__._instance.setupState.generatingMindMap);
  if(kind==='regenerate-failure'){assert(await retry.isEnabled());assert.equal(await page.locator('.mind-map-panel .smm-node').count()>0,true);assert.match(await page.locator('#app').innerText(),/导图生成失败/);}
  await page.evaluate(()=>{const s=document.querySelector('#app').__vue_app__._instance.setupState;s.selectedMindNode=s.mindMap.root.children[0]});
  await page.waitForTimeout(50);assert.equal(await page.locator('.mind-source').count(),0);
  assert.equal(await page.locator('.analysis-retry-card').count(),0);assert.deepEqual(errors,[]);outcomes.push({kind,endpoint:posts[0],duplicatePrevented:true,restored:true});await page.close();
 }
 console.log(JSON.stringify({outcomes,paidModelCalls:0}));
}finally{await browser.close()}
