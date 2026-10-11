import {chromium} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage();const bytes=await readFile('E:/workp/videostudy/.local/qa/compat-h264-8s.mp4');
 await page.route('http://127.0.0.1:18080/qa-video.mp4',route=>route.fulfill({status:200,headers:{'Content-Type':'video/mp4','Access-Control-Allow-Origin':'http://127.0.0.1:5173'},body:bytes}));
 await page.goto('http://127.0.0.1:5173/');
 const result=await page.evaluate(async()=>{const {createRegionCapture}=await import('/src/regionCapture.ts');const c=await createRegionCapture('http://127.0.0.1:18080/qa-video.mp4',new AbortController().signal);try{return await c.capture(2000)}finally{c.dispose()}});
 assert(result.image.startsWith('data:image/jpeg;base64,'));assert.equal(result.timeMs,2000);console.log('Cross-origin compatible video JPEG capture passed');
}finally{await browser.close()}
