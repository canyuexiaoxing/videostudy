import {chromium} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';import path from 'node:path';import http from 'node:http';import assert from 'node:assert/strict';import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),dist=path.join(root,'desktop/dist'),fixture=await fs.readFile(path.join(root,'.local/qa/native-delivery/fixtures/lesson.mp4')),out=path.join(root,'.local/qa/native-delivery/compatibility-navigation-ui.json');
const checks=[];let browser,server,posts=0,deletes=0,previews=0,expired=false,pending=false;const id='11111111-1111-4111-8111-111111111111';
try{
 server=http.createServer(async(req,res)=>{try{const name=new URL(req.url,'http://localhost').pathname;const file=path.resolve(dist,'.'+(name==='/'?'/index.html':name));if(!file.startsWith(dist+path.sep)){res.writeHead(403).end();return}const data=await fs.readFile(file);res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.html')?'text/html':'application/octet-stream');res.end(data)}catch{res.writeHead(404).end()}});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.route('**/api/**',async route=>{const req=route.request(),p=new URL(req.url()).pathname;const headers={'Access-Control-Allow-Origin':'*'};let value={};let status=200;
  if(req.method()==='OPTIONS'){await route.fulfill({status:204,headers:{...headers,'Access-Control-Allow-Methods':'GET,POST,DELETE,OPTIONS','Access-Control-Allow-Headers':'*'}});return}
  if(p.includes('preview'))previews++;
  if(p==='/api/transcriptions')value=[];
  else if(p==='/api/compatibility/capabilities')value={available:true,encoder:'libopenh264'};
  else if(p==='/api/compatibility'&&req.method()==='POST'){posts++;value={id,status:'queued'};status=202}
  else if(p===`/api/compatibility/${id}`&&req.method()==='DELETE'){deletes++;status=204}
  else if(p===`/api/compatibility/${id}`){status=expired?404:200;value={id,status:pending?'processing':'completed',progress:pending?50:100}}
  else if(p===`/api/compatibility/${id}/video`){await route.fulfill({status:200,headers,contentType:'video/mp4',body:fixture});return}
  else value={configured:false};
  await route.fulfill({status,headers,contentType:'application/json',body:status===204?'':JSON.stringify(value)})
 });
 await page.goto(`http://127.0.0.1:${server.address().port}/`);
 const input=page.locator('input[type=file][accept*="video"]').first();const choose=async(b=false)=>{await input.setInputFiles({name:b?'fixture-b.mp4':'fixture-a.mp4',mimeType:'video/mp4',buffer:b?Buffer.concat([fixture,Buffer.from('different-video')]):fixture});await page.waitForFunction(()=>!document.body.textContent.includes('正在核对本地媒体文件…'))};
 await choose();await page.getByRole('button',{name:'显卡兼容播放',exact:true}).click();await page.getByRole('button',{name:'返回原视频',exact:true}).waitFor();assert.equal(posts,1);checks.push('initial_conversion');
 await choose(true);await page.getByRole('button',{name:'显卡兼容播放',exact:true}).waitFor();assert.equal(deletes,0);checks.push('switch_preserves_copy');
 await choose();await page.getByRole('button',{name:'返回原视频',exact:true}).waitFor();assert.equal(posts,1);assert.equal(deletes,0);checks.push('switch_back_reuses_copy_without_upload');
 await page.reload();await choose();await page.getByRole('button',{name:'返回原视频',exact:true}).waitFor();assert.equal(posts,1);checks.push('association_survives_reload');
 const slider=page.getByRole('slider',{name:'视频进度：点击或拖动定位到对应时间'});await slider.hover();assert.equal(await page.locator('.chapter-preview-image,.chapter-preview-hint').count(),0);assert.equal(previews,0);checks.push('no_hover_image_or_generation_request');
 await choose(true);expired=true;await choose();await page.getByRole('button',{name:'显卡兼容播放',exact:true}).waitFor();assert.equal(posts,1);checks.push('expired_copy_falls_back_without_automatic_transcode');
 expired=false;pending=true;await page.getByRole('button',{name:'显卡兼容播放',exact:true}).click();await page.getByRole('button',{name:'取消转码',exact:true}).waitFor();await page.waitForFunction(()=>document.body.textContent.includes('50%'));await page.getByRole('button',{name:'取消转码',exact:true}).click();await page.waitForTimeout(150);assert.equal(deletes,1);checks.push('explicit_cancel_deletes_only_on_request');
 await fs.writeFile(out,JSON.stringify({passed:true,checks,uploads:posts,deletes,previewRequests:previews},null,2));console.log(JSON.stringify({passed:true,checks:checks.length,uploads:posts,deletes,previewRequests:previews}));
}catch(e){await fs.writeFile(out,JSON.stringify({passed:false,checks,error:e.message.slice(0,500)},null,2));console.error(e.message);process.exitCode=1}finally{await browser?.close();await new Promise(r=>server?.close(r)??r())}
