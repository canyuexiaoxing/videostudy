import fs from 'node:fs/promises';import path from 'node:path';import {fileURLToPath} from 'node:url';import {_electron} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),out=path.join(root,'.local/qa/native-delivery');const latest=JSON.parse(await fs.readFile(path.join(root,'.local/releases/latest.json'),'utf8'));const env={...process.env};delete env.ELECTRON_RUN_AS_NODE;const start=Date.now(),events=[],errors=[],writes=[];let app;
try{
 app=await _electron.launch({executablePath:latest.exe,args:[],env,timeout:60000});const page=await app.firstWindow();
 page.on('requestfailed',r=>{if(r.url().includes('/api/transcriptions'))events.push({event:'network_failed',origin:new URL(r.url()).origin,path:new URL(r.url()).pathname,error:r.failure()?.errorText})});
 page.on('response',r=>{if(/\/api\/transcriptions(?:\/[0-9a-f-]{36})?$/.test(new URL(r.url()).pathname))events.push({event:'response',origin:new URL(r.url()).origin,path:new URL(r.url()).pathname,status:r.status()})});
 page.on('console',m=>{if(m.type()==='error' && /CORS|Failed to fetch|net::ERR|Access-Control/.test(m.text()))errors.push(m.text().slice(0,600))});
 page.on('request',r=>{if(r.method()!=='GET'&&new URL(r.url()).pathname.startsWith('/api/'))writes.push({method:r.method(),path:new URL(r.url()).pathname})});
 await page.waitForFunction(()=>!!window.framewiseDesktop?.connection,{timeout:20000});let state;
 for(let i=0;i<180;i++){
  state=await page.evaluate(()=>window.framewiseDesktop.connection());if(state.phase==='ready'||state.phase==='error')break;
  if(i%10===0)console.log(JSON.stringify({stage:'waiting_actual_app',phase:state.phase,seconds:Math.round((Date.now()-start)/1000)}));await new Promise(r=>setTimeout(r,1000))
 }
 console.log(JSON.stringify({stage:'actual_app_state',...state,seconds:Math.round((Date.now()-start)/1000)}));
 if(await page.locator('.runtime-dialog').isVisible())await page.locator('.runtime-dialog').getByRole('button',{name:'关闭',exact:true}).click();
 await page.getByRole('tab',{name:'历史记录',exact:true}).click();await page.getByRole('button',{name:'刷新历史',exact:true}).click();await new Promise(r=>setTimeout(r,2500));
 const direct=await page.evaluate(async origin=>{try{const r=await fetch(origin+'/api/transcriptions');const j=await r.json();return {status:r.status,count:Array.isArray(j)?j.length:undefined}}catch(e){return {error:e.name,message:e.message}}},state.apiOrigin);
 if(await page.locator('.history-open').count())await page.locator('.history-open').first().click();await new Promise(r=>setTimeout(r,4000));
 const view=await page.locator('.analysis-progress strong').allTextContents();const failure=await page.locator('.results-panel p.error').allTextContents();const historyError=await page.locator('.history-error').allTextContents();
 const keyState=await page.evaluate(async()=>{const s=await window.framewiseDesktop.status();return {phase:s.phase,error:s.error,hasUsableKey:s.settings?.hasKey}});const result={keyState,seconds:Math.round((Date.now()-start)/1000),state,direct,view,failure,historyError,events,errors,writes};await fs.writeFile(path.join(out,'actual-native-read-result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{if(app)await app.close()}
