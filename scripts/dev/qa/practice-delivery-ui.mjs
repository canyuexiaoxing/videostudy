import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const {createServer}=await import(pathToFileURL(path.join(root,'desktop/node_modules/vite/dist/node/index.js')).href);
const {chromium}=await import('file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');
const server=await createServer({root:path.join(root,'desktop'),configFile:path.join(root,'desktop/vite.config.ts'),server:{host:'127.0.0.1',port:5199,strictPort:true}});
await server.listen();const browser=await chromium.launch({channel:'msedge',headless:true});
try{
 const mock=JSON.parse(await fs.readFile(path.join(root,'.local/qa/grouped-course-mock.json'),'utf8'));mock.result.mindMap.status='completed';const id=mock.id;
 const q={id:'q1',nodeTitle:'增长率',kind:'single',title:'计算题',prompt:'从100增加到120，增长率是多少？',options:['10%','20%','30%','40%'],validation:{calculationMissing:true,calculationChecked:false}};
 let set={id:'offline-set',title:'模拟练习',status:'completed',requestedCount:10,generatedCount:6,rejectedCount:1,shortfallCount:5,fillAttempts:1,fillStatus:'failed',questions:Array.from({length:5},(_,i)=>({...q,id:`q${i}`}))};
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{
  const u=new URL(route.request().url());const p=u.pathname;
  if(p.endsWith('/sessions'))return route.fulfill({json:{id:'session',feedback:[]}});
  if(p.endsWith('/practice/offline-set'))return route.fulfill({json:set});
  if(p.endsWith('/practice'))return route.fulfill({json:[set]});
  if(p==='/api/transcriptions')return route.fulfill({json:[{id,name:null,status:'completed',createdAt:new Date().toISOString()}]});
  if(p===`/api/transcriptions/${id}`)return route.fulfill({json:mock});
  if(p.endsWith('/overview'))return route.fulfill({json:{status:'not_requested'}});
  if(p.endsWith('/chapters'))return route.fulfill({json:{status:'completed',result:{chapters:[]}}});
  return route.fulfill({json:{status:'unsupported'}});
 });
 async function open(){await page.goto('http://127.0.0.1:5199/');await page.getByRole('tab',{name:'历史记录',exact:true}).click();await page.locator('.history-open').first().click();await page.getByRole('tab',{name:'AI 练习',exact:true}).click();}
 await open();await page.getByText('模型共返回 6 题',{exact:false}).waitFor();await page.getByText('题量为大致参考，以实际生成的有效题目为准。',{exact:true}).waitFor();assert.equal(await page.getByText('仍缺',{exact:false}).count(),0);assert.equal(await page.getByRole('option',{name:'多一些练习',exact:true}).count(),1);await page.getByText('本题未提供可自动核算的算式，请结合解析核对答案。',{exact:true}).waitFor();
 set={...set,questions:[],generatedCount:2,rejectedCount:2,shortfallCount:10};await open();await page.getByText('模型共返回 2 题',{exact:false}).waitFor();await page.getByText('本次没有可用题目，可以重新生成。',{exact:false}).waitFor();
 set={...set,questions:[q],generatedCount:null,requestedCount:null,rejectedCount:1};await open();await page.getByText('1 道题未通过检查，已剔除。',{exact:true}).waitFor();assert.equal(await page.getByText('模型共返回',{exact:false}).count(),0);
 assert.deepEqual(errors,[]);await fs.writeFile(path.join(root,'.local/qa/native-delivery/practice-ui-result.json'),JSON.stringify({checks:9,passed:true,paidModelCalls:0}));console.log('practice UI: 9 checks passed');
}finally{await browser.close();await server.close();}
