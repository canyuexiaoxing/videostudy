import {pathToFileURL,fileURLToPath} from 'node:url';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const mock=JSON.parse(readFileSync(fileURLToPath(new URL('../../../.local/qa/grouped-course-mock.json',import.meta.url)),'utf8'));
mock.result.mindMap.status='completed';const id=mock.id, requests=[],sets=new Map(),errors=[];
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{
  const req=route.request(),u=new URL(req.url());
  if(req.method()!=='GET'){
   if(u.pathname===`/api/transcriptions/${id}/practice`){
    const body=req.postDataJSON();requests.push(body);
    const set={id:`offline_set_${requests.length}`,title:'离线模拟练习',questions:[],status:body.mode==='map_context'?'failed':'completed',error:body.mode==='map_context'?'practice_map_context_missing':null,practiceMode:body.mode};sets.set(set.id,set);return route.fulfill({json:set,status:202});
   }
   throw new Error('Offline QA forbids unexpected writes: '+u.pathname);
  }
  if(u.pathname==='/api/transcriptions')return route.fulfill({json:[{id,status:'completed',name:null,createdAt:new Date().toISOString()}]});
  if(u.pathname===`/api/transcriptions/${id}`)return route.fulfill({json:mock});
  if(u.pathname.endsWith('/practice'))return route.fulfill({json:[]});
  if(u.pathname.includes('/practice/'))return route.fulfill({json:sets.get(u.pathname.split('/').at(-1))});
  if(u.pathname.endsWith('/overview'))return route.fulfill({json:{status:'not_requested'}});
  if(u.pathname.endsWith('/chapters'))return route.fulfill({json:{status:'completed',result:{chapters:[]}}});
  if(u.pathname.includes('/frames/'))return route.fulfill({status:404,body:'Missing QA fixture'});
  return route.fulfill({json:{status:'unsupported'}});
 });
 await page.goto('http://127.0.0.1:5173/');
 await page.getByRole('tab',{name:'历史记录',exact:true}).click();
 await page.locator('.history-item').filter({hasText:id}).locator('.history-open').click();
 await page.getByRole('tab',{name:'AI 练习',exact:true}).click();
 assert.equal(await page.getByRole('button',{name:'相关资料出题',exact:true}).getAttribute('aria-pressed'),'true');
 await page.getByRole('button',{name:'生成练习',exact:true}).click();
 await page.getByRole('button',{name:'生成练习',exact:true}).waitFor();
 await page.waitForFunction(()=>!document.querySelector('.practice-primary').disabled);
 assert.equal(requests[0].mode,'related_materials');
 await page.getByRole('button',{name:'沿用导图上下文',exact:true}).click();
 await page.getByRole('button',{name:'生成练习',exact:true}).click();
 await page.getByText('这门课未保存导图上下文，请重新生成导图，或选择相关资料出题。',{exact:true}).waitFor();
 assert.equal(requests[1].mode,'map_context');assert.equal(requests.length,2);
 await page.screenshot({path:fileURLToPath(new URL('../../../.local/qa/practice-modes-desktop.png',import.meta.url)),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 assert(await page.locator('.practice-mode-options').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
 await page.screenshot({path:fileURLToPath(new URL('../../../.local/qa/practice-modes-mobile.png',import.meta.url)),fullPage:true});
 assert.deepEqual(errors,[]);console.log(JSON.stringify({twoModes:true,defaultMode:'related_materials',requestModes:requests.map(r=>r.mode),oldRecordErrorVisible:true,mobilePassed:true,paidModelCalls:0}));
} finally {await browser.close()}
