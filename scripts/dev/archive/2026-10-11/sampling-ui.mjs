import { chromium } from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5173/');
 await page.locator('.advanced-toggle').evaluate(el=>{const details=el.closest('details');if(details)details.open=true;});
 await page.locator('.advanced-toggle').click();
 const buttons=page.locator('.sampling-options button');assert.equal(await buttons.count(),3);
 assert.equal(await buttons.nth(0).getAttribute('aria-pressed'),'true');
 await buttons.nth(1).click();assert.equal(await buttons.nth(1).getAttribute('aria-pressed'),'true');
 await buttons.nth(2).click();assert.equal(await buttons.nth(2).getAttribute('aria-pressed'),'true');
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
 await page.locator('input[type=file]').first().setInputFiles('E:/workp/videostudy/.local/qa/compat-h264-8s.mp4');
 await page.waitForFunction(()=>!!document.querySelector('#app').__vue_app__._instance.setupState.selectedFingerprint);
 await page.evaluate(()=>{
  const original=window.fetch;window.samplingPayload=null;
  window.fetch=async(url,options)=>{
   if(String(url).endsWith('/transcriptions')&&options?.method==='POST'){
    window.samplingPayload=Object.fromEntries([...options.body.entries()].filter(([k])=>k!=='file'));
    return new Response('{}',{status:503,headers:{'Content-Type':'application/json'}});
   }
   return original(url,options);
  };
 });
 await page.getByRole('button',{name:'开始分析',exact:true}).click();await page.waitForFunction(()=>!!window.samplingPayload);
 const payload=await page.evaluate(()=>window.samplingPayload);assert.equal(payload.coarseSampleSeconds,'4');
 assert.deepEqual(errors,[]);console.log(JSON.stringify({buttons:3,defaultSeconds:2,selectedSeconds:4,multipartSeconds:payload.coarseSampleSeconds,mobileOverflow:false,errors}));
}finally{await browser.close();}
