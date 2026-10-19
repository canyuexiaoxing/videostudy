import {chromium} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const out=path.join(root,'.local/qa/framewise-design-audit');await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.goto('http://127.0.0.1:5173/',{waitUntil:'networkidle'});
 await page.screenshot({path:path.join(out,'01-home.png'),fullPage:true,animations:'disabled'});
 await writeFile(path.join(out,'01-dom.txt'),await page.locator('body').innerText());
 await page.locator('#analysis-id').fill('e3d741db-0368-4b49-ab79-2fce8a88e801');
 await page.getByRole('button',{name:'读取结果',exact:true}).click();
 await page.waitForLoadState('networkidle');
 await page.locator('.mind-map-badge').waitFor({state:'visible',timeout:15000});
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:path.join(out,'02-course.png'),fullPage:true,animations:'disabled'});
 await writeFile(path.join(out,'02-dom.txt'),await page.locator('body').innerText());
 const tabs=page.getByRole('tab');await writeFile(path.join(out,'tabs.json'),JSON.stringify(await tabs.allTextContents()));
 const slides=page.getByRole('tab',{name:/课件/});
 if(await slides.count()) {await slides.click();await page.locator('#tab-slides img').first().waitFor();await page.waitForFunction(()=>Array.from(document.querySelectorAll('#tab-slides img')).every(img=>img.complete));await page.waitForLoadState('networkidle');await page.screenshot({path:path.join(out,'03-slides.png'),fullPage:true,animations:'disabled'});}
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'04-mobile.png'),fullPage:true,animations:'disabled'});
 console.log('Audit captured homepage, course results, slides and mobile.');
} finally {await browser.close();}
