import {pathToFileURL,fileURLToPath} from 'node:url';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('../../../',import.meta.url));
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const id=process.argv[2];if(!/^[a-f0-9-]{36}$/.test(id||''))throw Error('course UUID required');
const record=await (await fetch(`http://127.0.0.1:18080/api/transcriptions/${id}`)).json();
if(process.argv[3])record.result.mindMap=JSON.parse(await readFile(process.argv[3],'utf8'));
const before=JSON.stringify(record);assert(record.result.mindMap.root.children.length);
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
const folder=root+'.local/qa/map-outline-quality/'+id;await mkdir(folder,{recursive:true});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1100}});const posts=[],errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;
  if(req.method()==='OPTIONS')return route.fulfill({status:204});
  if(req.method()!=='GET'){posts.push(path);return route.fulfill({status:503,json:{error:'offline_only'}})}
  if(path==='/api/transcriptions')return route.fulfill({json:[{id,status:'completed',name:'保存课程的离线导图验证',createdAt:new Date().toISOString()}]});
  if(path===`/api/transcriptions/${id}`)return route.fulfill({json:record});
  if(path.endsWith('/chapters'))return route.fulfill({json:{status:'completed',result:{chapters:[]}}});
  if(path.endsWith('/practice'))return route.fulfill({json:[]});
  return route.fulfill({json:{status:'not_requested'}});
 });
 await page.goto('http://127.0.0.1:5173/');await page.getByRole('tab',{name:'历史记录',exact:true}).click();
 await page.locator('.history-item').filter({hasText:id}).locator('.history-open').click();
 await page.getByRole('tab',{name:'思维导图',exact:true}).click();
 await page.locator('.mind-map-panel .smm-node').first().waitFor();
 const metrics=await page.evaluate(()=>{
  const state=document.querySelector('#app').__vue_app__._instance.setupState;
  const list=root=>{const a=[];const walk=n=>{a.push(n);n.children.forEach(walk)};walk(root);return a};
  const before=list(state.rawMindMap.root),after=list(state.mindMap.root);
  const originalIds=new Set();const all=n=>{originalIds.add(n.id);n.children.forEach(all);(n.details??[]).forEach(all)};all(state.rawMindMap.root);
  const generic=/^(?:方法|公式|法则|结论)(?:[一二三四五六七八九十\d]+)?$/;
  const opaque=nodes=>nodes.filter(n=>!n.children.length && generic.test(n.title)).length;
  return {beforeNodes:before.length,afterNodes:after.length,maxTitleBefore:Math.max(...before.map(n=>n.title.length)),maxTitleAfter:Math.max(...after.map(n=>n.title.length)),lookupStepVisible:after.some(n=>n.title.startsWith('③根据')),idsPreserved:after.every(n=>originalIds.has(n.id)),opaqueBefore:opaque(before),opaqueAfter:opaque(after),methodActionsVisible:after.some(n=>n.title.includes('方法一：先减再加')),comparisonsVisible:after.some(n=>n.title.includes('比较带符号'))};
 });
 assert.equal(metrics.idsPreserved,true);
 if(process.argv[3]){assert.equal(metrics.beforeNodes,metrics.afterNodes);assert.equal(metrics.opaqueAfter,0);assert(metrics.methodActionsVisible);assert(metrics.comparisonsVisible);}
 await page.locator('.mind-map-panel').screenshot({path:folder+'/panel.png'});
 await page.getByRole('button',{name:'放大查看',exact:true}).click();await page.waitForTimeout(350);await page.screenshot({path:folder+'/expanded.png'});
 assert.equal(posts.length,0);assert.deepEqual(errors,[]);assert.equal(JSON.stringify(record),before);
 await writeFile(folder+'/ui-summary.json',JSON.stringify({...metrics,paidModelCalls:0},null,2));console.log(JSON.stringify(metrics));
}finally{await browser.close()}
