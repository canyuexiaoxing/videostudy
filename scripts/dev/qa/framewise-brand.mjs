import { chromium } from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const out=path.join(root,'.local/qa/framewise-brand');await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const svg=await readFile(path.join(root,'desktop/public/framewise.svg'),'utf8');
 for (const size of [32,192,256,512]) {
  const data=await page.evaluate(async ({svg,size})=>{
   const img=new Image();img.src='data:image/svg+xml;base64,'+btoa(svg);await img.decode();
   const canvas=document.createElement('canvas');canvas.width=canvas.height=size;canvas.getContext('2d').drawImage(img,0,0,size,size);return canvas.toDataURL('image/png').split(',')[1];
  },{svg,size});
  await writeFile(path.join(root,`desktop/public/framewise-${size}.png`),Buffer.from(data,'base64'));
 }
 const png=await readFile(path.join(root,'desktop/public/framewise-256.png'));
 const ico=Buffer.alloc(22);ico.writeUInt16LE(1,2);ico.writeUInt16LE(1,4);ico.writeUInt16LE(1,10);ico.writeUInt16LE(32,12);ico.writeUInt32LE(png.length,14);ico.writeUInt32LE(22,18);
 await writeFile(path.join(root,'desktop/public/favicon.ico'),Buffer.concat([ico,png]));
 await page.goto('http://127.0.0.1:5173/',{waitUntil:'networkidle'});
 assert.equal(await page.title(),'Framewise');assert.equal((await page.locator('.brand').innerText()).trim(),'Framewise');
 assert.equal(await page.locator('.brand-symbol').evaluate(img=>img.complete && img.naturalWidth>0),true);
 assert.equal(await page.locator('link[rel="icon"]').getAttribute('href'),'/framewise.svg');
 for (const resource of ['framewise.svg','framewise-512.png','favicon.ico']) assert.equal((await page.request.get('http://127.0.0.1:5173/'+resource)).status(),200);
 await page.locator('.app-header').screenshot({path:path.join(out,'header.png')});
 await page.screenshot({path:path.join(out,'desktop.png')});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'mobile.png')});
 const brand=await page.locator('.brand').boundingBox();assert.ok(brand.x>=0 && brand.x+brand.width<=390);
 await writeFile(path.join(out,'verification.json'),JSON.stringify({title:'Framewise',brand:true,iconLoaded:true,resources:true,mobileBrandFits:true},null,2));
 console.log('Framewise branding verified; desktop/mobile screenshots saved.');
} finally {await browser.close();}
