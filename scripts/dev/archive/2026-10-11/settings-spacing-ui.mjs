import {chromium} from 'file:///C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try {
 const page=await browser.newPage({viewport:{width:1280,height:900}});
 await page.goto('http://127.0.0.1:5173/');
 await page.locator('.analysis-settings').evaluate(el=>el.open=true);
 const gap=await page.locator('.analysis-settings-content').evaluate(el=>getComputedStyle(el).rowGap);
 assert.equal(gap,'20px');
 await page.locator('.advanced-toggle').click();
 assert.equal(await page.locator('.sampling-options button').count(),3);
 await page.locator('.analysis-settings').screenshot({path:'C:/Users/Administrator/.codex/visualizations/2026/10/10/01a123b6-19aa-7d32-8d1e-83e31cc453a1/settings-separated.png'});
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 console.log(JSON.stringify({desktopGap:gap,sections:3,mobileOverflow:false}));
} finally {await browser.close();}
