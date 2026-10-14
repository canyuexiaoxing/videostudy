import {pathToFileURL,fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const root=fileURLToPath(new URL('../../../',import.meta.url));
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
const question={id:'q1',nodeTitle:'增长量计算',kind:'single',title:'增长量',prompt:'体重从160斤增加到192斤，增长量是多少？',options:['20%','32斤','160斤','192斤']};
const set={id:'set1',title:'增长量计算',status:'completed',questions:[question]};
const feedback={questionId:'q1',selectedIndex:0,answerIndex:1,correct:false,explanation:'增长量等于现期减基期，即192－160＝32斤。',takeaway:'增长量表示增加的数量；增长率表示增加的比例。',selectedReason:'你选择的是增长率。',citations:[]};
const errors=[],messages=[];let posts=0;
const source=await (await fetch('http://127.0.0.1:5173/src/AiPractice.vue')).text();
const vuePath=source.match(/from "([^"]*deps\/vue.js[^"]*)"/)[1];
try{
 const page=await browser.newPage({viewport:{width:1100,height:1150}});page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/qa-question-chat',route=>route.fulfill({contentType:'text/html; charset=utf-8',body:`<html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;background:#f5f7ff;font-family:Arial,'Microsoft YaHei',sans-serif}#test{max-width:780px;margin:24px auto;background:white;border-radius:16px}button,textarea,select{font-family:inherit}*{box-sizing:border-box}</style></head><body><main id="test"></main><script type="module">import {createApp} from '${vuePath}';import Component from '/src/AiPractice.vue';createApp(Component,{courseId:'offline',ready:true}).mount('#test');</script></body></html>`}));
 await page.route('**/api/**',async route=>{
  const r=route.request(),p=new URL(r.url()).pathname;
  if(r.method()==='OPTIONS')return route.fulfill({status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'GET,POST,OPTIONS'}});
  if(p.endsWith('/chat')){
   if(r.method()==='POST'){posts++;messages.push({role:'user',content:r.postDataJSON().message},{role:'assistant',content:'20% 是增长率；这道题要求增长量，应计算 192－160＝32斤。'});return route.fulfill({headers:{'Access-Control-Allow-Origin':'*'},json:{}})}
   return route.fulfill({headers:{'Access-Control-Allow-Origin':'*'},json:messages});
  }
  if(p.endsWith('/sessions'))return route.fulfill({headers:{'Access-Control-Allow-Origin':'*'},json:{id:'session1',feedback:[feedback]}});
  if(r.method()!=='GET')throw Error('Unexpected write in QA: '+p);
  return route.fulfill({headers:{'Access-Control-Allow-Origin':'*'},json:p.endsWith('/practice')?[set]:set});
 });
 await page.goto('http://127.0.0.1:5173/qa-question-chat');
 const toggle=page.locator('.practice-chat-toggle');await toggle.waitFor({timeout:10000}).catch(async e=>{console.log(errors,await page.locator('body').innerText());throw e});
 assert.equal(await toggle.getAttribute('aria-expanded'),'false');assert(await toggle.getByText('打开答疑',{exact:false}).isVisible());
 await toggle.scrollIntoViewIfNeeded();await page.screenshot({path:root+'.local/qa/question-chat-entry.png',fullPage:true});
 await toggle.click();await page.getByText('哪里没想明白？从这里开始').waitFor();
 await page.screenshot({path:root+'.local/qa/question-chat-desktop.png',fullPage:true});
 const input=page.getByLabel('你的问题或解题思路',{exact:true}),send=page.getByRole('button',{name:'发送问题 →',exact:true});
 assert(await send.isDisabled());await input.fill('为什么20%不对？');assert(await send.isEnabled());await send.click();await page.getByText('20% 是增长率；这道题要求增长量，应计算 192－160＝32斤。',{exact:true}).waitFor();assert.equal(posts,1);
 await page.setViewportSize({width:390,height:844});await toggle.scrollIntoViewIfNeeded();
 assert(await page.locator('.practice-chat-entry').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.screenshot({path:root+'.local/qa/question-chat-mobile.png',fullPage:true});
 await toggle.click();assert.equal(await page.locator('.question-chat').count(),0);await toggle.click();await page.getByText('20% 是增长率；这道题要求增长量，应计算 192－160＝32斤。',{exact:true}).waitFor();
 assert.deepEqual(errors,[]);console.log(JSON.stringify({visibleEntry:true,expandCollapse:true,mockSend:true,reopenHistory:true,mobileOverflow:false,paidModelCalls:0}));
}finally{await browser.close()}
