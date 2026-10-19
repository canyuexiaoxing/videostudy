import {_electron} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';import path from 'node:path';import {fileURLToPath} from 'node:url';import {readFile,mkdir,writeFile} from 'node:fs/promises';import {createHash} from 'node:crypto';import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),out=path.join(root,'.local/qa/overview-chat');await mkdir(out,{recursive:true});
const packaged=process.env.FRAMEWISE_CHAT_PACKAGED==='1',latest=packaged?JSON.parse(await readFile(path.join(root,'.local/releases/latest.json'),'utf8')):null,env={...process.env};delete env.ELECTRON_RUN_AS_NODE;
const file=path.join(root,'.local/qa/timeline-preview/test.webm'),bytes=await readFile(file),length=Buffer.alloc(8);length.writeBigUInt64BE(BigInt(bytes.length));const fingerprint=createHash('sha256').update(length).update(bytes.subarray(0,65536)).update(bytes.subarray(Math.max(0,bytes.length-65536))).digest('hex'),identity={size:bytes.length,fingerprint};
const course='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',other='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',key='a'.repeat(64);const histories=new Map([[course,[]],[other,[]]]);let legacy=true,migrated=false,fail=true,ids=[];
const app=await _electron.launch({executablePath:latest?.exe||path.join(root,'desktop/node_modules/electron/dist/electron.exe'),args:[...(!packaged?[path.join(root,'desktop')]:[]),'--user-data-dir='+path.join(out,'profile-'+Date.now())],env});
try{
 const page=await app.firstWindow();page.on('pageerror',error=>console.error('PAGE_ERROR',error.message));
 await page.route('**/api/**',async route=>{
  const url=new URL(route.request().url()),parts=url.pathname.split('/'),id=parts[3],method=route.request().method();let json={status:'not_requested'};
  if(url.pathname.endsWith('/media')){
   if(method==='PUT'){assert.equal(route.request().postDataJSON().bindingSource,'legacy_auto');migrated=true;legacy=false;return route.fulfill({json:identity})}
   return legacy?route.fulfill({status:410,json:{error:'original_media_unavailable'}}):route.fulfill({json:identity});
  }
  if(url.pathname.endsWith('/overview/chat')){
   const messages=histories.get(id);
   if(method==='POST'){
    const body=route.request().postDataJSON();ids.push(body.requestId);assert.equal(body.contextKey,key);
    if(fail){fail=false;return route.fulfill({status:502,json:{error:'overview_chat_failed'}})}
    messages.push({role:'user',content:body.message},{role:'assistant',content:'按照老师的方法，这一步先整理方程，再代入初始条件。',citations:[{sourceId:'s1',startMs:5000,endMs:10000,quote:'本课真实讲解'}]});
    return route.fulfill({json:{reply:'answered',citations:[]}});
   }
   return route.fulfill({json:{status:'ready',contextKey:key,contextMode:'original',messages}});
  }
  if(url.pathname.endsWith('/overview'))return route.fulfill({json:{id,status:'completed',result:{status:'completed',headline:'ORIGINAL_PRIVATE_INPUT',summary:[{text:'本课程介绍',citations:[]}],notes:[],objectives:[],keyPoints:[],pitfalls:[],highlights:[],conversationId:id}}});
  if(url.pathname==='/api/transcriptions')json=[course,other].map((id,index)=>({id,name:index?'测试课程乙':'测试课程甲',status:'completed',createdAt:'2026-10-19T00:00:00Z'}));
  else if(url.pathname==='/api/transcriptions/'+id)json={id,status:'completed',result:{language:'zh',segments:[{id:'s1',startMs:5000,endMs:10000,text:'本课真实讲解'}],visualEvidence:[],pageGroups:[],mindMap:{status:'completed',root:{id:'r',title:id===course?'测试课程甲':'测试课程乙',startMs:0,endMs:10000,children:[],evidenceRefs:[]}}}};
  return route.fulfill({json});
 });
 await page.reload({waitUntil:'networkidle'});
 await page.evaluate(({course,identity})=>localStorage.setItem('analysisMedia:'+course,JSON.stringify({...identity,name:'legacy.webm'})),{course,identity});
 await page.locator('.app-header input[type=file]').setInputFiles(file);await page.waitForFunction(()=>document.querySelector('video')?.readyState>=2);
 async function open(name){await page.getByRole('tab',{name:'历史记录',exact:true}).click();await page.locator('.history-open').filter({hasText:name}).click();await page.locator('.overview-chat textarea:not(:disabled)').waitFor()}
 await open('测试课程甲');await page.waitForFunction(course=>JSON.parse(localStorage.getItem('analysisMedia:'+course)).bindingSource==='server',course);assert.ok(migrated);await page.getByText('已自动关联本课',{exact:true}).waitFor();
 const positions=await page.evaluate(()=>['.video-overview','.overview-chat','.results-panel'].map(selector=>document.querySelector(selector).getBoundingClientRect().top));assert.ok(positions[0]<positions[1]&&positions[1]<positions[2]);assert.equal(await page.locator('.overview-chat .chat-message').count(),0);assert.ok(!(await page.locator('.overview-chat').innerText()).includes('ORIGINAL_PRIVATE_INPUT'));
 const input=page.locator('.overview-chat textarea');await input.fill('按老师的方法再讲细一点');await page.locator('.overview-chat button[type=submit]').click();await page.locator('.overview-chat .chat-error').waitFor();assert.equal(await input.inputValue(),'按老师的方法再讲细一点');await page.locator('.overview-chat button[type=submit]').click();await page.locator('.overview-chat .chat-message.assistant').waitFor();assert.equal(ids[0],ids[1]);assert.equal(await input.inputValue(),'');
 await page.locator('.overview-chat .chat-citations button').click();await page.waitForFunction(()=>document.querySelector('video')?.currentTime>=4.9);await page.locator('video').first().evaluate(v=>v.pause());
 await input.fill('尚未发送的甲课程问题');await open('测试课程乙');assert.equal(await page.locator('.overview-chat .chat-message').count(),0);assert.equal(await page.locator('.overview-chat textarea').inputValue(),'');await open('测试课程甲');assert.equal(await page.locator('.overview-chat .chat-message').count(),2);assert.equal(await page.locator('.overview-chat textarea').inputValue(),'尚未发送的甲课程问题');
 await page.reload({waitUntil:'networkidle'});await open('测试课程甲');assert.equal(await page.locator('.overview-chat .chat-message').count(),2);await page.locator('.overview-chat').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'course-chat'+(packaged?'-packaged':'')+'.png')});
 await writeFile(path.join(out,'verification'+(packaged?'-packaged':'')+'.json'),JSON.stringify({version:latest?.version,packaged,legacyCacheMigrates:true,backendIdentityCachedLocally:true,automaticMediaAssociation:true,positionBetweenOverviewAndEvidence:true,initialInputHidden:true,failedSendPreservesDraft:true,retryUsesSameRequestId:true,courseIsolation:true,conversationRestoredAfterReload:true,citationActuallySeeks:true,paidModelCalls:0},null,2));console.log('Course chat and local-first cache verified.');
}finally{await app.close()}
