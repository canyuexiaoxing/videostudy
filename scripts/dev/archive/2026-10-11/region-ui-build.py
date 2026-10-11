from pathlib import Path
stage=Path(__file__).parent
s=(stage/'workspace-ui.mjs').read_text(encoding='utf-8')
s=s.replace(" // Selecting a different file",''' await page.evaluate(()=>{
  const original=window.fetch;window.regionUploads=[];
  window.fetch=async(url,options)=>{
   if(String(url).endsWith('/transcriptions')&&options?.method==='POST'){
    window.regionUploads.push(Object.fromEntries([...options.body.entries()].filter(([k])=>k!=='file')));
    return new Response('{}',{status:503,headers:{'Content-Type':'application/json'}});
   }
   return original(url,options);
  };
 });
 await page.getByRole('button',{name:'开始分析',exact:true}).click();
 await page.waitForFunction(()=>window.regionUploads.length===1&&!document.querySelector('#app').__vue_app__._instance.setupState.isAnalysisPending);
 assert.deepEqual(JSON.parse(await page.evaluate(()=>window.regionUploads[0].ignoredRegion)),saved);
 // Selecting a different file''')
s=s.replace(" assert.deepEqual(errors,[]);assert.equal(posts.length,0);",''' await page.getByRole('button',{name:'开始分析',exact:true}).click();
 await page.waitForFunction(()=>window.regionUploads.length===2);
 assert.equal(await page.evaluate(()=>window.regionUploads[1].ignoredRegion),undefined);
 assert.deepEqual(errors,[]);assert.equal(posts.length,0);''')
s=s.replace('modelRequests:0,errors','multipartRegion:true,clearOmitsRegion:true,modelRequests:0,errors')
(stage/'region-ui.mjs').write_text(s,encoding='utf-8')
deploy=(stage/'sampling-deploy.py').read_text(encoding='utf-8').replace("'sampling-images'","'region-images'").replace("('app.py','analysis.py','visual_evidence.py')","('app.py','analysis.py','visual_evidence.py','slide_grouping.py','ignored_region.py')").replace('COPY app.py analysis.py visual_evidence.py /app/','COPY app.py analysis.py visual_evidence.py slide_grouping.py ignored_region.py /app/')
(stage/'region-deploy.py').write_text(deploy,encoding='utf-8')
