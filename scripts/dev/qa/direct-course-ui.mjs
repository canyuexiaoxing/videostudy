import {pathToFileURL,fileURLToPath} from 'node:url';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const mock=JSON.parse(readFileSync(fileURLToPath(new URL('../../../.local/qa/direct-course-mock.json',import.meta.url)),'utf8'));
const id=mock.id, writes=[], errors=[];
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/api/**',async route=>{
  const req=route.request(),u=new URL(req.url());
  if(req.method()!=='GET'){
   writes.push({path:u.pathname,mode:u.searchParams.get('mindMapMode'),body:req.postData()});
   if(u.pathname.endsWith('/mind-map'))return route.fulfill({json:mock.result.mindMap});
   if(u.pathname==='/api/transcriptions')return route.fulfill({status:202,json:mock});
   return route.fulfill({status:409,body:'offline test blocks writes'});
  }
  if(u.pathname===`/api/transcriptions/${id}`)return route.fulfill({json:mock});
  if(u.pathname.endsWith('/chapters'))return route.fulfill({json:{status:'completed',result:{chapters:[]}}});
  if(u.pathname.endsWith('/overview'))return route.fulfill({json:{status:'completed',result:{status:'empty'}}});
  return route.continue();
 });
 await page.goto('http://127.0.0.1:5173/');
 await page.getByRole('button',{name:'高级选项',exact:true}).click();
 assert.equal(await page.getByRole('button',{name:'原流程',exact:true}).getAttribute('aria-pressed'),'true');
 await page.getByRole('button',{name:'整课图文直生成',exact:true}).click();
 assert.equal(await page.locator('.mode-picker select').inputValue(),'both');assert(await page.locator('.mode-picker select').isDisabled());
 await page.getByRole('button',{name:'原流程',exact:true}).click();assert(await page.locator('.mode-picker select').isEnabled());
 await page.getByRole('button',{name:'整课图文直生成',exact:true}).click();
 // Exercise actual upload FormData without sending a file or provider request to the server.
 await page.evaluate(async()=>{
  const state=document.querySelector('#app').__vue_app__._instance.setupState;
  state.selectedFile=new File(['offline video placeholder'],'lesson.mp4',{type:'video/mp4'});
  await state.runTranscription();
 });
 assert.equal(writes.filter(w=>w.path==='/api/transcriptions').length,1);
 assert.match(writes[0].body,/name="mindMapMode"\r\n\r\ndirect/);
 await page.evaluate(async()=>{await document.querySelector('#app').__vue_app__._instance.setupState.generateExistingMindMap(true)});
 assert.equal(writes.filter(w=>w.path.endsWith('/mind-map'))[0].mode,'direct');
 assert.equal(writes.filter(w=>w.path.endsWith('/overview')).length,0);
 await page.screenshot({path:fileURLToPath(new URL('../../../.local/qa/direct-course-desktop.png',import.meta.url)),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 assert(await page.locator('.map-mode-row').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
 await page.screenshot({path:fileURLToPath(new URL('../../../.local/qa/direct-course-mobile.png',import.meta.url)),fullPage:true});
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({threeModes:true,uploadMode:'direct',manualRefreshMode:'direct',mobilePassed:true,paidModelCalls:0}));
}finally{await browser.close()}
