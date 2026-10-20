import {chromium} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import {spawn} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
import {createWriteStream} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const out=path.join(root,'.local/qa/native-delivery/ui');await mkdir(out,{recursive:true});
const log=createWriteStream(path.join(out,'vite.log'));
const vite=spawn(process.execPath,[path.join(root,'desktop/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port','5174','--strictPort'],{cwd:path.join(root,'desktop'),windowsHide:true,stdio:['ignore','pipe','pipe']});
vite.stdout.pipe(log);vite.stderr.pipe(log);
let browser;const checks=[];
try {
 for(let i=0;i<100;i++){try{if((await fetch('http://127.0.0.1:5174')).ok)break}catch{}await new Promise(resolve=>setTimeout(resolve,100))}
 browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.route('**/api/**',route=>route.fulfill({status:200,contentType:'application/json',body:'[]'}));
 const page=await context.newPage();let uploads=0,historyRequests=0;page.on('request',request=>{if(new URL(request.url()).pathname==='/api/transcriptions'){if(request.method()==='POST')uploads++;else if(request.method()==='GET')historyRequests++;}});const errors=[];page.on('pageerror',error=>errors.push(error.name));
 await page.goto('http://127.0.0.1:5174');await page.getByRole('button',{name:'设置',exact:true}).click();
 await page.getByRole('heading',{name:'浏览器预览模式'}).waitFor();checks.push('browser fallback without IPC');
 await page.getByRole('button',{name:'关闭',exact:true}).click();
 await page.addInitScript(()=>{
  window.__nativeCalls=[];window.__nativeErrorNext=false;
  window.__nativeState={phase:'starting',apiOrigin:'http://127.0.0.1:18080',settings:{mode:'auto',hasKey:false,model:'deepseek-flash',baseUrl:'https://api.deepseek.com'},hardware:{modules:{asr:{device:'CPU',fallbackReason:'cuda_unavailable'},ocr:{device:'GPU'},detector:{device:'CPU',reason:'cpu_selected'}}},models:{state:'absent',files:[{id:'asr-model',state:'absent',size:100}]},metrics:{cacheBytes:1048576,busy:false}};
  const action=name=>async args=>{window.__nativeCalls.push({name,...(name==='saveSettings'?{mode:args.mode,hasKey:!!args.apiKey}:{})});await new Promise(resolve=>setTimeout(resolve,100));if(window.__nativeErrorNext){window.__nativeErrorNext=false;return {ok:false,error:'runtime_busy'}}
   if(name==='start'||name==='restart')window.__nativeState.phase='ready';
   if(name==='saveSettings')window.__nativeState.settings={...window.__nativeState.settings,...args,hasKey:!!args.apiKey};
   if(name==='installModels')window.__nativeState.models={state:'downloading',files:[{id:'asr-model',state:'downloading',size:100,downloaded:40}]};
   if(name==='cancelModels')window.__nativeState.models={state:'absent',files:[{id:'asr-model',state:'absent',size:100}]};
   if(name==='importModels')window.__nativeState.models={state:'ready',files:[{id:'asr-model',state:'ready',size:100}]};
   return {ok:true};};
  window.framewiseDesktop={status:async()=>structuredClone(window.__nativeState),...Object.fromEntries(['saveSettings','start','restart','installModels','cancelModels','exportBackup','restoreBackup','exportDiagnostics','clearCache','openDataDirectory','importModels'].map(name=>[name,action(name)]))};
 });
 await page.reload();const dialog=page.getByRole('dialog',{name:'本机设置'});await dialog.waitFor();
 assert.equal(await dialog.getByRole('combobox').inputValue(),'auto');await dialog.getByText('CUDA 运行环境不可用，已使用 CPU。',{exact:true}).waitFor();checks.push('onboarding GPU default and per-module fallback');await page.screenshot({path:path.join(out,'onboarding.png')});
 async function action(label,name){const count=await page.evaluate(()=>window.__nativeCalls.length);await dialog.getByRole('button',{name:label,exact:true}).click();await page.waitForFunction(({name,count})=>window.__nativeCalls.slice(count).some(call=>call.name===name),{name,count});await page.waitForFunction(()=>!document.querySelector('.runtime-dialog button.run')?.disabled);}
 await action('启动 / 重试','start');await action('重启服务','restart');
 await dialog.getByPlaceholder('输入新的 API 密钥').fill('mock-key-for-local-test');await dialog.getByRole('combobox').selectOption('cpu');await action('保存设置','saveSettings');assert.equal(await dialog.getByPlaceholder('输入新的 API 密钥').inputValue(),'');assert.deepEqual(await page.evaluate(()=>window.__nativeCalls.find(call=>call.name==='saveSettings')),{name:'saveSettings',mode:'cpu',hasKey:true});checks.push('secure key save clears field');
 await action('下载 / 重试','installModels');await dialog.getByRole('progressbar').waitFor();assert.equal(await dialog.getByRole('progressbar').getAttribute('value'),'40');await action('取消下载','cancelModels');await action('导入离线模型','importModels');checks.push('model download progress cancel offline import');
 for(const [label,name] of [['导出备份','exportBackup'],['恢复备份','restoreBackup'],['导出诊断','exportDiagnostics'],['打开数据目录','openDataDirectory'],['清理临时缓存','clearCache']])await action(label,name);
 await page.evaluate(()=>window.__nativeErrorNext=true);await action('清理临时缓存','clearCache');await dialog.getByRole('alert').filter({hasText:'仍有课程任务正在处理'}).waitFor();checks.push('all native actions and safe failure feedback');
 await page.screenshot({path:path.join(out,'settings.png'),fullPage:true});
 const archiveResult=await page.evaluate(async()=>{
  const image={type:'image/png',base64:'AAECAwQ='};const archive={format:'framewise-renderer',version:1,notes:[{id:'note-a',scope:'course:course-a',timeMs:1500,text:'本机笔记',createdAt:'2026-10-19T00:00:00Z',image,annotation:{base:image,strokes:[{tool:'pen',color:'#ef4444',size:5,dashed:false,points:[{x:1,y:2}]}]}}],localStorage:{'framewise:appearance:v1':'blue','analysisMedia:course-a':'{"fingerprint":"abc","size":5}'}};
  await window.framewiseImportNotes(archive);const exported=await window.framewiseExportNotes();let rejected=false;try{await window.framewiseImportNotes({...archive,notes:[...archive.notes,...archive.notes]})}catch{rejected=true}
  const unchanged=await window.framewiseExportNotes();return {exported,expected:archive,rejected,unchanged:JSON.stringify(unchanged)===JSON.stringify(exported)};
 });assert.deepEqual(archiveResult.exported,archiveResult.expected);assert.equal(archiveResult.rejected,true);assert.equal(archiveResult.unchanged,true);checks.push('real IndexedDB annotated note backup roundtrip and failed validation preserves data');
 await dialog.getByRole('button',{name:'关闭',exact:true}).click();
 const previousHistoryRequests=historyRequests;await page.evaluate(()=>window.dispatchEvent(new CustomEvent('framewise-runtime-state',{detail:{phase:'ready',apiOrigin:'http://127.0.0.1:18080'}})));await page.waitForTimeout(150);assert.ok(historyRequests>previousHistoryRequests);checks.push('native-ready event refreshes history without reload');
 await page.locator('.file-picker input').setInputFiles(path.join(root,'.local/qa/timeline-preview/test.webm'));await page.getByRole('button',{name:'开始分析',exact:true}).waitFor();
 for(const scenario of ['phase','key','models','hardware']){
  await page.evaluate(scenario=>{window.__nativeState.phase='ready';window.__nativeState.settings.hasKey=true;window.__nativeState.models.state='ready';window.__nativeState.hardware.modules={asr:{device:'cpu',available:true}};if(scenario==='phase')window.__nativeState.phase='starting';if(scenario==='key')window.__nativeState.settings.hasKey=false;if(scenario==='models')window.__nativeState.models.state='absent';if(scenario==='hardware')window.__nativeState.hardware.modules.asr.available=false;},scenario);
  await page.getByRole('button',{name:'开始分析',exact:true}).click();await dialog.waitFor();assert.equal(uploads,0);await dialog.getByRole('button',{name:'关闭',exact:true}).click();
 }
 assert.equal(uploads,0);checks.push('native upload preflight blocks unready backend key models and devices before upload');
 assert.deepEqual(errors,[]);await writeFile(path.join(out,'result.json'),JSON.stringify({ok:true,checks},null,2));console.log(JSON.stringify({ok:true,checks}));
} finally {if(browser)await browser.close();vite.kill();log.end();}
