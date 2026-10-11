from pathlib import Path
stage=Path(__file__).parent
s=(stage/'core-map-ui.mjs').read_text()
start=s.index(" await page.locator('.example-timeline').waitFor();")
s=s[:start]+'''
 page.setDefaultTimeout(8000);
 const opener=page.getByRole('button',{name:'放大查看',exact:true});
 await opener.click();
 const dialog=page.getByRole('dialog',{name:'课程思维导图'});
 await dialog.waitFor();
 const desktop=await dialog.boundingBox(); assert(desktop.width>1200 && desktop.height>750);
 const canvas=dialog.locator('.mind-map-canvas');
 await canvas.locator('svg').first().waitFor();
 assert((await canvas.boundingBox()).width>1100 && (await canvas.boundingBox()).height>600);
 await dialog.getByRole('button',{name:'聚焦主题',exact:true}).click();
 await dialog.getByRole('button',{name:'展开全部',exact:true}).click();
 await dialog.getByRole('button',{name:'放大导图',exact:true}).click();
 await dialog.getByRole('button',{name:'适应画布',exact:true}).click();
 await page.screenshot({path:'C:/Users/Administrator/.codex/visualizations/2026/10/10/01a123b6-19aa-7d32-8d1e-83e31cc453a1/map-dialog-desktop.png'});
 await page.keyboard.press('Escape'); await dialog.waitFor({state:'detached'});
 assert(await opener.evaluate(el=>el===document.activeElement));
 await opener.click(); await dialog.getByRole('button',{name:'关闭',exact:true}).click(); await dialog.waitFor({state:'detached'});
 await page.setViewportSize({width:390,height:844}); await opener.click();
 const mobile=await dialog.boundingBox(); assert(mobile.width<=390 && mobile.height<=844);
 assert((await canvas.boundingBox()).height>400);
 await page.evaluate(()=>{document.querySelector('#app').__vue_app__._instance.setupState.mindMap=null});
 await dialog.waitFor({state:'detached'});
 assert.equal(posts.length,0);assert.deepEqual(errors,[]);
 console.log(JSON.stringify({largeCanvas:true,controls:true,escapeAndFocus:true,closeButton:true,mobile:true,courseResetCloses:true,modelRequests:0}));
}finally{await browser.close();}
'''
(stage/'map-dialog-ui.mjs').write_text(s)
