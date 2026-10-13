import {pathToFileURL,fileURLToPath} from 'node:url';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const mock=JSON.parse(readFileSync(fileURLToPath(new URL('../../../.local/qa/grouped-course-mock.json',import.meta.url)),'utf8'));
const id=mock.id, url=`http://127.0.0.1:18080/api/transcriptions/${id}`;
const before=await (await fetch(url)).json();
const map=mock.result.mindMap;map.status='completed';
map.examples=mock.result.segments.slice(0,2).map((s,i)=>({id:`verified_example_${i}`,title:`模拟独立例题 ${i+1}`,startMs:s.startMs,endMs:s.endMs,children:[],evidenceRefs:[{sourceType:'transcript',sourceId:s.id,startMs:s.startMs,endMs:s.endMs,quote:s.text}]}));
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}), errors=[], mutations=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{
  const req=route.request(),u=new URL(req.url());
  if(req.method()!=='GET'){mutations.push(u.pathname);return route.fulfill({status:409,body:'offline test blocks writes'})}
  if(u.pathname===`/api/transcriptions/${id}`)return route.fulfill({json:mock});
  return route.continue();
 });
 await page.goto('http://127.0.0.1:5173/');
 await page.getByRole('button',{name:'高级选项',exact:true}).click();
 assert.equal(await page.getByRole('button',{name:'原流程',exact:true}).getAttribute('aria-pressed'),'true');
 await page.getByRole('button',{name:'分组后汇总',exact:true}).click();
 assert.equal(await page.locator('.mode-picker select').inputValue(),'both');assert(await page.locator('.mode-picker select').isDisabled());
 await page.getByRole('tab',{name:'历史记录',exact:true}).click();
 await page.locator('.history-item').filter({hasText:id}).locator('.history-open').click();
 await page.waitForFunction(()=>document.querySelector('#app').__vue_app__._instance.setupState.mindMap?.root.children.length>0);
 await page.getByRole('tab',{name:'思维导图',exact:true}).click();
 const metrics=await page.evaluate(()=>{
  const state=document.querySelector('#app').__vue_app__._instance.setupState;
  const concept=state.mindMap.root.children[0];state.selectMindMapNode(concept);
  return {concepts:state.mindMap.root.children.length,details:concept.details.length,examples:state.exampleTimeline.length};
 });
 assert.equal(metrics.concepts,1);assert.equal(metrics.examples,2);assert(metrics.details>0);
 const layout=await page.locator('.mind-map-panel').evaluate(el=>{
  const canvas=el.querySelector('.map-canvas-shell'),details=el.querySelector('.mind-source');
  return {canvasBeforeDetails:!!(canvas.compareDocumentPosition(details)&Node.DOCUMENT_POSITION_FOLLOWING),canvasHeight:canvas.getBoundingClientRect().height};
 });
 assert(layout.canvasBeforeDetails);assert(layout.canvasHeight>=380);

 await page.locator('.knowledge-details summary').first().click();
 await page.locator('.mind-evidence-image').first().waitFor();
 await page.waitForFunction(()=>[...document.querySelectorAll('.mind-evidence-image')].some(img=>img.complete&&img.naturalWidth>0));
 assert.equal(await page.getByText('需核对：离线模拟输出，不用于证明实际提炼准确率').count(),0);
 await page.getByRole('button',{name:'放大查看',exact:true}).click();await page.locator('.expanded-map-dialog[open]').waitFor();await page.getByRole('button',{name:'关闭',exact:true}).click();

 await page.evaluate(()=>{document.body.style.minHeight='2200px';window.scrollTo(0,300)});
 await page.locator('.mind-map-panel').evaluate(el=>el.style.transform='translateY(650px)');
 await page.getByRole('button',{name:'适应画布',exact:true}).evaluate(el=>el.click());
 const fitMetrics=await page.locator('.mind-map-canvas').first().evaluate(el=>{
 const rect=el.getBoundingClientRect();const nodes=[...el.querySelectorAll('.smm-node')].map(n=>n.getBoundingClientRect());
 return {canvas:{x:rect.x,y:rect.y,w:rect.width,h:rect.height},nodes:nodes.map(r=>({x:r.x,y:r.y,w:r.width,h:r.height})),visible:nodes.filter(r=>r.left>=rect.left-1&&r.right<=rect.right+1&&r.top>=rect.top-1&&r.bottom<=rect.bottom+1).length};
 });
 assert(fitMetrics.nodes.length>0);assert.equal(fitMetrics.visible,fitMetrics.nodes.length);
 console.log('fit-diagnostics',fitMetrics);
 await page.locator('.mind-map-panel').evaluate(el=>el.style.transform='');
 await page.getByRole('button',{name:'适应画布',exact:true}).evaluate(el=>el.click());
 await page.setViewportSize({width:390,height:844});assert(await page.locator('.knowledge-details').first().evaluate(el=>el.scrollWidth<=el.clientWidth+1));
 await page.screenshot({path:fileURLToPath(new URL('../../../.local/qa/grouped-course-ui.png',import.meta.url)),fullPage:true});
 assert.deepEqual(errors,[]);assert.deepEqual(mutations,[]);
 const after=await (await fetch(url)).json();assert.deepEqual(after,before);
 console.log(JSON.stringify({...metrics,defaultOptInFalse:true,realImageDisplayed:true,expandedMap:true,mobilePassed:true,historyUnchanged:true,paidModelCalls:0}));
}finally{await browser.close()}
