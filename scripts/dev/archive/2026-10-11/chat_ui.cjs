const {chromium}=require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1280,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const course='22222222-2222-4222-8222-222222222222';
 const refs=[{sourceId:'s1',startMs:1000,endMs:2000,quote:'分母使用基期'}];
 const qs=[1,2].map(i=>({id:`q${i}`,nodeTitle:'增长率',kind:'single',title:`题${i}`,prompt:`第${i}道测试：增长率是多少？`,options:['10%','20%','30%','40%']}));
 const feedback=qs.map(q=>({questionId:q.id,selectedIndex:0,answerIndex:1,correct:false,explanation:'除以基期',takeaway:'基期',selectedReason:'误用现期',citations:refs}));
 const histories={q1:[],q2:[]};const savedRequests=new Map();let posts=0,fail=false,delayed=false,lose=false;
 await page.route('http://127.0.0.1:18080/**',async route=>{
  const req=route.request(),url=req.url();let body={};let status=200;
  if(url.includes('/chat')){
   const q=url.includes('/q1/')?'q1':'q2';
   if(req.method()==='POST'){
    posts++;if(fail){status=502;body={error:'chat_provider_failed'};fail=false}
    else {const input=req.postDataJSON();body={reply:`${q}：请解释分母选择`,citations:refs};if(!savedRequests.has(input.requestId)){histories[q].push({role:'user',content:input.message},{role:'assistant',content:body.reply,citations:refs});savedRequests.set(input.requestId,body)}if(lose){lose=false;await route.abort();return}if(delayed)await new Promise(r=>setTimeout(r,400));}
   }else body=histories[q];
  }else if(url.endsWith('/practice'))body=[{id:'set',title:'增长率',status:'completed'}];
  else if(url.endsWith('/practice/set'))body={id:'set',title:'增长率',status:'completed',questions:qs};
  else if(url.endsWith('/sessions'))body={id:'session',feedback};
  else if(url.endsWith('/transcriptions/'+course))body={id:course,status:'completed',result:{language:'zh',segments:refs.map(r=>({id:r.sourceId,startMs:r.startMs,endMs:r.endMs,text:r.quote})),visualEvidence:[],pageGroups:[],mindMap:{status:'completed',root:{id:'root',title:'增长率',startMs:1000,endMs:2000,evidenceRefs:refs,children:[]}}}};
  else if(url.includes('/subtitles'))body={status:'not_requested'};
  else if(url.endsWith('/chapters'))body={status:'completed',result:{chapters:[]}};
  else if(url.endsWith('/overview'))body={status:'completed',result:{status:'empty'}};
  await route.fulfill({status,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify(body)});
 });
 try{
  await page.goto('http://127.0.0.1:5173/');await page.locator('#analysis-id').fill(course);
  await page.locator('#analysis-id').locator('..').locator('button').click();
  await page.locator('[aria-controls=tab-practice]').click();
  const entry=page.locator('.practice-chat-entry>button');await entry.waitFor();await entry.click();
  await page.locator('.chat-empty').waitFor();assert.equal(posts,0);
  await page.locator('.question-chat textarea').fill('我为什么除以现期？');await page.locator('.chat-actions button').click();
  await page.getByText('q1：请解释分母选择',{exact:true}).waitFor();assert.equal(posts,1);
  assert.equal(await page.locator('.chat-citations button').isDisabled(),true);
  await page.locator('.practice-steps button').nth(1).click();await entry.click();await page.locator('.chat-empty').waitFor();
  await page.locator('.question-chat textarea').fill('第二题疑问');await page.locator('.chat-actions button').click();
  await page.getByText('q2：请解释分母选择',{exact:true}).waitFor();
  await page.locator('.practice-steps button').first().click();await entry.click();await page.getByText('q1：请解释分母选择',{exact:true}).waitFor();
  assert.equal(await page.getByText('q2：请解释分母选择',{exact:true}).count(),0);assert.equal(posts,2);
  fail=true;await page.locator('.question-chat textarea').fill('保留失败草稿');await page.locator('.chat-actions button').click();await page.locator('.chat-error').waitFor();
  assert.equal(await page.locator('.question-chat textarea').inputValue(),'保留失败草稿');
  await page.locator('.chat-actions button').click();await page.waitForFunction(()=>document.querySelector('.question-chat textarea').value==='');
  lose=true;await page.locator('.question-chat textarea').fill('响应丢失的同一请求');await page.locator('.chat-actions button').click();await page.locator('.chat-error').waitFor();
  await page.getByRole('button',{name:'重新读取'}).click();await page.getByText('响应丢失的同一请求',{exact:true}).waitFor();const messageCount=await page.locator('.chat-message').count();
  await page.locator('.chat-actions button').click();await page.waitForFunction(()=>document.querySelector('.question-chat textarea').value==='');assert.equal(await page.locator('.chat-message').count(),messageCount);
  delayed=true;await page.locator('.question-chat textarea').fill('切题中的请求');await page.locator('.chat-actions button').click();
  await page.locator('.practice-steps button').nth(1).click();await entry.click();await page.getByText('q2：请解释分母选择',{exact:true}).waitFor();
  await page.waitForTimeout(600);assert.equal(await page.getByText('切题中的请求',{exact:true}).count(),0);
  await page.reload();await page.locator('[aria-controls=tab-practice]').click();await entry.click();await page.getByText('q1：请解释分母选择',{exact:true}).first().waitFor();
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(100);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.locator('.question-chat').scrollIntoViewIfNeeded();
  await page.screenshot({path:'C:/Users/Administrator/.codex/visualizations/2026/10/10/01a123b6-19aa-7d32-8d1e-83e31cc453a1/question-chat-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);console.log(JSON.stringify({independentQuestions:true,reloadRestores:true,noAutoAI:true,failedDraftRetained:true,staleResponseIgnored:true,unmatchedMediaDisabled:true,mobileOverflow:false,errors}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
