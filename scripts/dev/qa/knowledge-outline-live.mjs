import {pathToFileURL,fileURLToPath} from 'node:url';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const id='65894cb5-9404-4bdd-a10b-a4bdcdd4d5fc';
const before=await (await fetch(`http://127.0.0.1:18080/api/transcriptions/${id}`)).json();
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5173/');await page.getByRole('tab',{name:'历史记录',exact:true}).click();
 await page.locator('.history-item').filter({hasText:id}).locator('.history-open').click();
 await page.waitForFunction(()=>document.querySelector('#app').__vue_app__._instance.setupState.mindMap?.root.children.length>0);
 const metrics=await page.evaluate(()=>{
  const state=document.querySelector('#app').__vue_app__._instance.setupState;
  function count(node){return 1+node.children.reduce((sum,n)=>sum+count(n),0)}
  const candidates=[];function walk(node){if(node.details?.length)candidates.push(node);node.children.forEach(walk)}walk(state.mindMap.root);
  if(!candidates.length)throw Error('No explanation details');state.selectMindMapNode(candidates[0]);
  return {storedNodes:count(state.rawMindMap.root),displayNodes:count(state.mindMap.root),details:candidates.reduce((sum,n)=>sum+n.details.length,0),selectedTitle:candidates[0].title};
 });
 assert(metrics.displayNodes<metrics.storedNodes);assert(metrics.details>0);
 await page.locator('.knowledge-details summary').first().click();assert(await page.locator('.knowledge-details .mind-source-link').first().isVisible());
 await page.getByRole('button',{name:'放大查看',exact:true}).click();await page.locator('.expanded-map-dialog[open]').waitFor();await page.getByRole('button',{name:'关闭',exact:true}).click();
 const file=fileURLToPath(new URL('../../../.local/qa/compat-h264-8s.mp4',import.meta.url)),bytes=readFileSync(file),size=Buffer.alloc(8);size.writeBigUInt64BE(BigInt(bytes.length));
 const fingerprint=createHash('sha256').update(Buffer.concat([size,bytes.subarray(0,65536),bytes.subarray(Math.max(0,bytes.length-65536))])).digest('hex');
 await page.evaluate(({id,fingerprint,size})=>localStorage.setItem('analysisMedia:'+id,JSON.stringify({name:'compat-h264-8s.mp4',size,fingerprint})),{id,fingerprint,size:bytes.length});
 await page.locator('.file-picker input').setInputFiles(file);
 await page.waitForFunction(id=>document.querySelector('#app').__vue_app__._instance.setupState.existingJobId===id&&!document.querySelector('#app').__vue_app__._instance.setupState.checkingMedia,id);
 assert.equal(await page.evaluate(()=>JSON.stringify(document.querySelector('#app').__vue_app__._instance.setupState.rawMindMap)),JSON.stringify(before.result.mindMap));
 await page.setViewportSize({width:390,height:844});const detailPanel=page.locator('.knowledge-details');if(await detailPanel.count())assert(await detailPanel.evaluate(el=>el.scrollWidth<=el.clientWidth+1));
 const after=await (await fetch(`http://127.0.0.1:18080/api/transcriptions/${id}`)).json();assert.deepEqual(after.result.mindMap,before.result.mindMap);assert.deepEqual(errors,[]);
 const snapshotRaw=await page.evaluate(()=>JSON.stringify(document.querySelector('#app').__vue_app__._instance.setupState.rawMindMap));assert.equal(snapshotRaw,JSON.stringify(before.result.mindMap));
 console.log(JSON.stringify({...metrics,detailsReadable:true,expandedMap:true,mobilePassed:true,storedMapUnchanged:true,rawPracticeMapPreserved:true,paidModelCalls:0}));
}finally{await browser.close()}
