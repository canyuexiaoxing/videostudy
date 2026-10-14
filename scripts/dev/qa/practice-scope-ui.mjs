import {pathToFileURL,fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const root=fileURLToPath(new URL('../../../',import.meta.url));
const source=await (await fetch('http://127.0.0.1:5173/src/AiPractice.vue')).text();
const vuePath=source.match(/from "([^"]*deps\/vue.js[^"]*)"/)[1];
const leaf=(id,title)=>({id,title,children:[],details:[{id:id+'_condition',title:'适用条件',children:[]}]});
const map={root:{id:'root',title:'增长量课程',children:[{id:'formula',title:'增长量公式',children:[leaf('formula1','现期减基期'),leaf('formula2','基期乘增长率')]},{id:'calculation',title:'增长量计算',children:[leaf('base_rate','给基期、增长率'),leaf('current_base','给现期、基期')]},leaf('comparison','增长量比较')]}};
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
const errors=[],requests=[];let current;
try{
 const page=await browser.newPage({viewport:{width:1100,height:850}});page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/qa-practice-scope',route=>route.fulfill({contentType:'text/html; charset=utf-8',body:`<html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;background:#f5f7ff;font-family:Arial,'Microsoft YaHei',sans-serif}#test{max-width:780px;margin:24px auto;background:white;border-radius:16px}*{box-sizing:border-box}</style></head><body><main id="test"></main><script type="module">import {createApp} from '${vuePath}';import Component from '/src/AiPractice.vue';createApp(Component,{courseId:'offline',ready:true,mindMap:${JSON.stringify(map)}}).mount('#test');</script></body></html>`}));
 await page.route('**/api/**',async route=>{
  const req=route.request(),p=new URL(req.url()).pathname,headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'GET,POST,OPTIONS'};
  if(req.method()==='OPTIONS')return route.fulfill({status:204,headers});
  if(req.method()==='POST'){assert(p.endsWith('/practice'));requests.push(req.postDataJSON());current={id:'offline_set',title:'模拟练习',status:'completed',questions:[]};return route.fulfill({json:current,headers});}
  return route.fulfill({json:p.endsWith('/practice')?[]:current,headers});
 });
 await page.goto('http://127.0.0.1:5173/qa-practice-scope');
 const summary=page.locator('.scope-menu summary');await summary.click();
 assert.equal(await page.locator('.scope-choice:visible').count(),3);
 assert.equal(await page.getByRole('button',{name:'给基期、增长率',exact:true}).count(),0);
 await page.locator('.scope-choice').filter({hasText:'增长量计算'}).click();assert((await summary.innerText()).includes('增长量计算'));
 await page.getByRole('button',{name:'生成练习',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.practice-primary').disabled);assert.equal(requests[0].nodeId,'calculation');
 await summary.click();await page.getByRole('button',{name:'展开增长量计算',exact:true}).click();
 assert.equal(await page.getByRole('button',{name:'收起增长量计算',exact:true}).getAttribute('aria-expanded'),'true');
 assert.equal(await page.getByRole('button',{name:'适用条件',exact:true}).count(),0);
 await page.screenshot({path:root+'.local/qa/practice-scope-desktop.png',fullPage:true});
 await page.locator('.scope-choice').filter({hasText:'给现期、基期'}).click();assert((await summary.innerText()).includes('给现期、基期'));
 await page.getByRole('button',{name:'生成练习',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.practice-primary').disabled);assert.equal(requests[1].nodeId,'current_base');
 await summary.click();await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:root+'.local/qa/practice-scope-mobile.png',fullPage:true});
 await page.getByRole('button',{name:'整课范围 · 随机出题',exact:false}).click();assert((await summary.innerText()).includes('整课范围 · 随机出题'));
 for(const [level,phrase] of [['basic','基础巩固'],['application','应用练习'],['advanced','进阶挑战']]){
  await page.getByLabel('难度',{exact:true}).selectOption(level);assert.equal(await page.getByLabel('难度',{exact:true}).locator('option:checked').innerText(),phrase);assert.equal(await page.locator('.difficulty-description').count(),0);
  await page.getByRole('button',{name:'生成练习',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.practice-primary').disabled);assert.equal(requests.at(-1).difficulty,level);
 }
 assert.deepEqual(errors,[]);console.log(JSON.stringify({defaultTopModules:3,expandWithoutSelecting:true,moduleRequest:requests[0].nodeId,subrangeRequest:requests[1].nodeId,wholeCourseSelection:true,mobileOverflow:false,paidModelCalls:0}));
}finally{await browser.close()}
