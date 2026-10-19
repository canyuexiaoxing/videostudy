import {_electron} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';import path from 'node:path';import {fileURLToPath} from 'node:url';import {readFile,mkdir,writeFile} from 'node:fs/promises';import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),out=path.join(root,'.local/qa/math-figures');await mkdir(out,{recursive:true});const questions=JSON.parse(await readFile(path.join(out,'fixtures.json'),'utf8'));
const packaged=process.env.FRAMEWISE_MATH_PACKAGED==='1',latest=packaged?JSON.parse(await readFile(path.join(root,'.local/releases/latest.json'),'utf8')):null,env={...process.env};delete env.ELECTRON_RUN_AS_NODE;
const course='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',set='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',session='cccccccc-cccc-4ccc-8ccc-cccccccccccc';let chat=[];const fontFailures=[];
const app=await _electron.launch({executablePath:latest?.exe||path.join(root,'desktop/node_modules/electron/dist/electron.exe'),args:[...(!packaged?[path.join(root,'desktop')]:[]),'--user-data-dir='+path.join(out,'profile-'+Date.now())],env});
try{
 const page=await app.firstWindow();page.on('response',r=>{if(/\.woff2?(\?|$)/.test(r.url())&&r.status()!==200)fontFailures.push(r.url())});
 await page.route('**/api/**',route=>{
  const req=route.request(),url=new URL(req.url()),method=req.method();let json={status:'not_requested'};
  if(url.pathname.endsWith('/media'))return route.fulfill({status:410,json:{error:'original_media_unavailable'}});
  if(url.pathname.includes('/practice')){
   if(url.pathname.endsWith('/chat')){if(method==='POST'){const body=req.postDataJSON();chat=[{role:'user',content:body.message},{role:'assistant',content:String.raw`按老师的方法：\[I=\frac{U}{R}=2\,\mathrm{A}\]`,citations:[]}];return route.fulfill({json:{reply:'ok',citations:[]}})}return route.fulfill({json:chat})}
   if(url.pathname.endsWith('/answers')){const body=req.postDataJSON(),q=questions.find(q=>q.id===body.questionId);return route.fulfill({json:{questionId:q.id,selectedIndex:body.selectedIndex,answerIndex:q.answerIndex,correct:body.selectedIndex===q.answerIndex,explanation:q.explanation,selectedReason:q.distractorReasons[body.selectedIndex],takeaway:q.takeaway,citations:q.citations}})}
   if(url.pathname.endsWith('/sessions'))return route.fulfill({json:{id:session,feedback:[]}});
   if(url.pathname.endsWith('/practice'))return route.fulfill({json:[{id:set,title:'公式与绘图测试',status:'completed'}]});
   const publicQuestions=questions.map(({answerIndex,explanation,distractorReasons,takeaway,calculation,...q})=>q);return route.fulfill({json:{id:set,title:'公式与绘图测试',status:'completed',questions:publicQuestions}})
  }
  if(url.pathname.endsWith('/overview/chat'))return route.fulfill({json:{status:'ready',contextKey:'a'.repeat(64),contextMode:'original',messages:[{role:'assistant',content:String.raw`课程对话公式 \(E=\frac{1}{2}mv^2\)`,citations:[]}]}});
  if(url.pathname.endsWith('/overview'))return route.fulfill({json:{status:'completed',result:{status:'completed',headline:'公式课程',summary:[],notes:[],objectives:[],keyPoints:[],pitfalls:[],highlights:[]}}});
  if(url.pathname==='/api/transcriptions')json=[{id:course,name:'公式绘图验证课程',status:'completed',createdAt:'2026-10-19T00:00:00Z'}];
  if(url.pathname==='/api/transcriptions/'+course)json={id:course,status:'completed',result:{language:'zh',segments:[{id:'s1',startMs:0,endMs:10000,text:'测试课程依据'}],pageGroups:[],visualEvidence:[],mindMap:{status:'completed',root:{id:'n1',title:'公式与图形测试',startMs:0,endMs:10000,children:[],evidenceRefs:[{sourceType:'transcript',sourceId:'s1',startMs:0,endMs:10000,quote:'测试课程依据'}]}}}};
  return route.fulfill({json});
 });
 await page.reload({waitUntil:'networkidle'});await page.getByRole('tab',{name:'历史记录',exact:true}).click();await page.locator('.history-open').filter({hasText:'公式绘图验证课程'}).click();await page.getByRole('tab',{name:'AI 练习',exact:true}).click();await page.locator('.practice-question').waitFor();
 assert.equal(await page.locator('.practice-question .katex').count(),5);
 const checked=[];
 for(let i=0;i<questions.length;i++){
  await page.locator('.practice-steps button').nth(i).click();const q=questions[i];
  if(q.diagram){await page.locator('.practice-question .practice-figure').waitFor();const svg=await page.locator('.practice-question .practice-figure').innerHTML();assert.ok(!/NaN|Infinity/.test(svg));
   await page.locator('.practice-question .practice-figure button').click();await page.locator('dialog.practice-chart-dialog[open]').waitFor();assert.ok(!/NaN|Infinity/.test(await page.locator('dialog.practice-chart-dialog[open]').innerHTML()));
   if(['function','function-pole','geometry','circle','circuit','circuit-components','circuit-symbols','pie'].includes(q.title))await page.locator('dialog.practice-chart-dialog').screenshot({path:path.join(out,q.title+(packaged?'-packaged':'')+'.png')});
   await page.locator('dialog.practice-chart-dialog button').filter({hasText:'关闭'}).click();checked.push(q.title)
  }
  if(q.title==='latex-matrix'){assert.ok(await page.locator('.practice-question legend .katex').count()>=2);await page.locator('.practice-question').screenshot({path:path.join(out,'latex'+(packaged?'-packaged':'')+'.png')})}
  if(q.title==='latex-fallback'){await page.locator('.practice-question .math-error').waitFor();assert.ok((await page.locator('.practice-question legend').innerText()).includes('unknowncommand'))}
  if(q.title==='latex-long'){const widths=await page.locator('.practice-question').evaluate(e=>({outer:e.clientWidth,scroll:e.scrollWidth,formula:e.querySelector('.math-formula')?.clientWidth,formulaScroll:e.querySelector('.math-formula')?.scrollWidth}));assert.ok(widths.scroll<=widths.outer+3,JSON.stringify(widths));assert.ok(widths.formulaScroll>widths.formula);}
 }
 await page.locator('.practice-steps button').nth(0).click();await page.locator('.practice-question input[type=radio]').first().click();await page.locator('.practice-feedback .katex').first().waitFor();await page.locator('.practice-chat-toggle').click();await page.locator('.question-chat textarea:not(:disabled)').fill('请再解释一下公式');await page.locator('.question-chat button[type=submit]').click();await page.locator('.question-chat .chat-message.assistant .katex').waitFor();
 await page.evaluate(()=>document.fonts.ready);assert.ok(await page.evaluate(()=>[...document.fonts].filter(f=>f.family.includes('KaTeX')&&f.status==='loaded').length)>0);assert.deepEqual(fontFailures,[]);
 await page.locator('.overview-chat .katex').waitFor({state:'attached'});
 for(const width of [1024,390]){await page.setViewportSize({width,height:900});await page.locator('.practice-steps button').last().click();const bounds=await page.evaluate(()=>({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));assert.ok(bounds.scroll<=bounds.width+3,JSON.stringify(bounds));}
 await page.locator('.practice-question').screenshot({path:path.join(out,'long-mobile'+(packaged?'-packaged':'')+'.png')});
 await writeFile(path.join(out,'verification'+(packaged?'-packaged':'')+'.json'),JSON.stringify({version:latest?.version,packaged,checkedDiagrams:checked,latexPromptOptionsExplanationAndChat:true,overviewChatMath:true,narrowLayoutNoPageOverflow:true,offlineFontsLoaded:true,invalidLatexKeepsText:true,longFormulaScrolls:true,paidModelCalls:0},null,2));console.log('Math, diagrams, zoom, answer feedback, chat and offline fonts verified.');
}finally{await app.close()}
