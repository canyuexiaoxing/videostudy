from pathlib import Path
stage=Path(__file__).parent
s=(stage/'core-map-ui.mjs').read_text().replace('examples:[example]','examples:Array.from({length:20},(_,i)=>({...example,id:`example_${i}`,title:`例题 ${i+1}`}))')
s=s.replace("assert.equal(await page.locator('.example-timeline button').count(),1);","assert.equal(await page.locator('.example-timeline button').count(),20);\n const bounds=await page.locator('.mind-map-canvas').boundingBox(); console.log(JSON.stringify({canvas:bounds})); assert(bounds && bounds.height>=300,'core map must remain visible with 20 examples');")
s=s.replace("page.locator('.example-timeline button').click()","page.locator('.example-timeline button').first().click()")
(stage/'map-layout-ui.mjs').write_text(s)
