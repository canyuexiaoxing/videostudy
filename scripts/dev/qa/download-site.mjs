import { chromium } from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';import {fileURLToPath} from 'node:url';import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');const out=path.join(root,'.local/qa/download-site');await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});const errors=[];let checks=0;
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5180/',{waitUntil:'networkidle'});await page.waitForTimeout(1100);
 assert.match(await page.title(),/Framewise/);checks++;
 await page.screenshot({path:path.join(out,'desktop-hero.png')});
 await page.locator('.map-geometry').click();assert.equal(await page.locator('#demo-time').textContent(),'15:20');assert.match(await page.locator('#lesson-caption').textContent(),/割线/);checks+=2;
 await page.getByRole('tab',{name:'课程问答'}).click();assert.equal(await page.locator('#panel-chat').isVisible(),true);assert.equal(await page.locator('#panel-map').isVisible(),false);checks+=2;
 await page.locator('#panel-chat .source-button').click();assert.match(await page.locator('#evidence-label').textContent(),/15:20/);checks++;
 await page.getByRole('tab',{name:'随手笔记'}).click();assert.equal(await page.locator('#panel-notes').isVisible(),true);checks++;
 await page.getByRole('tab',{name:'随手笔记'}).focus();await page.keyboard.press('Home');assert.equal(await page.locator('#tab-map').getAttribute('aria-selected'),'true');checks++;
 await page.locator('#demo-play').click();await page.waitForTimeout(1200);assert.equal(await page.locator('#demo-time').textContent(),'15:21');await page.locator('#demo-play').click();assert.equal(await page.locator('#demo-play').getAttribute('aria-pressed'),'false');checks+=2;
 const items=page.locator('.faq-list details');await items.nth(0).locator('summary').click();await page.waitForTimeout(80);assert.equal(await items.nth(0).getAttribute('open'),'');await items.nth(1).locator('summary').click();await page.waitForTimeout(120);assert.equal(await items.nth(0).getAttribute('open'),null);checks+=2;
 await page.route('https://framewise-download-2026.obs.cn-east-3.myhuaweicloud.com/**',route=>route.fulfill({status:200,contentType:'application/octet-stream',headers:{'Content-Disposition':'attachment; filename="Framewise-0.3.1-Online-Setup.exe"'},body:'download-test-only'}));
 const [download]=await Promise.all([page.waitForEvent('download'),page.locator('.download-main .download-link').click()]);assert.equal(download.suggestedFilename(),'Framewise-0.3.1-Online-Setup.exe');assert.equal(await page.locator('.toast').evaluate(el=>el.classList.contains('visible')),true);checks+=2;
 await page.locator('.toast button').click();
 for(const width of [1440,1024,768,580,390,360]){
  await page.setViewportSize({width,height:1000});await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(350);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`overflow at ${width}`);checks++;
 }
 await page.setViewportSize({width:390,height:844});await page.locator('.menu-toggle').click();assert.equal(await page.locator('.menu-toggle').getAttribute('aria-expanded'),'true');await page.getByRole('link',{name:'如何开始',exact:true}).click();assert.equal(await page.locator('.menu-toggle').getAttribute('aria-expanded'),'false');checks+=2;
 await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(500);await page.screenshot({path:path.join(out,'mobile-hero.png')});
 for(let y=0;y<await page.evaluate(()=>document.body.scrollHeight);y+=600){await page.evaluate(y=>scrollTo(0,y),y);await page.waitForTimeout(100);}
 await page.waitForTimeout(800);await page.screenshot({path:path.join(out,'mobile-full.png'),fullPage:true});
 await page.setViewportSize({width:1440,height:1000});for(let y=0;y<await page.evaluate(()=>document.body.scrollHeight);y+=750){await page.evaluate(y=>scrollTo(0,y),y);await page.waitForTimeout(120);}await page.waitForTimeout(900);await page.screenshot({path:path.join(out,'desktop-full.png'),fullPage:true});
 await page.locator('#experience').scrollIntoViewIfNeeded();await page.waitForTimeout(600);await page.locator('.product-frame').screenshot({path:path.join(out,'product-demo.png')});
 await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior),'auto');checks++;
 const targets=await page.locator('a[href^="#"]').evaluateAll(links=>links.map(a=>a.hash).filter(x=>x&&x!=='#').every(x=>document.getElementById(x.slice(1))));assert.equal(targets,true);checks++;
 const images=await page.locator('img').evaluateAll(images=>images.every(i=>i.complete&&i.naturalWidth>0));assert.equal(images,true);checks++;
 assert.deepEqual(errors,[]);checks++;
 const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});const staticPage=await nojs.newPage();await staticPage.goto('http://127.0.0.1:5180/');assert.equal(await staticPage.locator('#download').isVisible(),true);assert.equal(await staticPage.locator('.faq-list details').count(),6);checks+=2;await nojs.close();
 await writeFile(path.join(out,'verification.json'),JSON.stringify({passed:true,checks,viewportWidths:[1440,1024,768,580,390,360],downloadTest:'mocked attachment; real OBS link verified separately; no installer executed',errors},null,2));console.log(JSON.stringify({passed:true,checks,errors}));
}finally{await browser.close();}
