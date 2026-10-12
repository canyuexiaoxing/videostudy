import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const id='65894cb5-9404-4bdd-a10b-a4bdcdd4d5fc';
const job=await (await fetch(`http://127.0.0.1:18080/api/transcriptions/${id}`)).json();assert.equal(job.result.mindMap.examples.length,32);
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5173/');await page.getByRole('tab',{name:'历史记录',exact:true}).click();
 await page.locator('.history-item').filter({hasText:id}).locator('.history-open').click();
 await page.waitForFunction(()=>document.querySelectorAll('.example-timeline>button').length===12);
 const nodes=await page.locator('.example-timeline>button').allTextContents();assert.match(nodes[1],/00:01:33/);assert.match(nodes[2],/00:03:00/);assert(!nodes.some(v=>v.includes('00:01:53')));
 await page.setViewportSize({width:390,height:844});assert(await page.locator('.example-timeline').evaluate(el=>el.scrollWidth<=el.clientWidth+1));assert.deepEqual(errors,[]);
 const stored=await (await fetch(`http://127.0.0.1:18080/api/transcriptions/${id}`)).json();assert.equal(stored.result.mindMap.examples.length,32);
 console.log('Actual stored32fragments render12questions; second and third jump to real openings; old data unchanged, mobile layout passed. No AI calls or reanalysis.');
}finally{await browser.close()}
