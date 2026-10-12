import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const rows=await (await fetch('http://127.0.0.1:18080/api/transcriptions')).json();
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5173/');await page.getByRole('tab',{name:'历史记录',exact:true}).click();
 await page.waitForFunction(count=>document.querySelectorAll('.history-item').length===count,rows.length);
 assert.equal(await page.locator('.history-item').count(),rows.length);
 await page.evaluate(()=>localStorage.clear());await page.reload();await page.getByRole('tab',{name:'历史记录',exact:true}).click();
 await page.waitForFunction(count=>document.querySelectorAll('.history-item').length===count,rows.length);assert.deepEqual(errors,[]);
 console.log(`Live fresh browser restored ${rows.length} server tasks after cache clearing; no task opened or deleted.`);
}finally{await browser.close()}
