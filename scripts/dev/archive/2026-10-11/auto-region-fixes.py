from pathlib import Path
p=Path('E:/workp/videostudy')
f=p/'desktop/src/regionCapture.ts';s=f.read_text(encoding='utf-8').replace("video.muted=true;video.preload='auto'", "video.muted=true;video.preload='auto';video.crossOrigin='anonymous'");f.write_text(s,encoding='utf-8')
f=p/'desktop/src/autoRegionScan.ts';s=f.read_text(encoding='utf-8').replace("return ['x','y','width','height'].every(k=>Math.abs(x[k as keyof VideoRegion]-y[k as keyof VideoRegion])<=.025)", "const overlap=Math.max(0,Math.min(x.x+x.width,y.x+y.width)-Math.max(x.x,y.x))*Math.max(0,Math.min(x.y+x.height,y.y+y.height)-Math.max(x.y,y.y))\n return overlap/(x.width*x.height+y.width*y.height-overlap)>=.8&&['x','y','width','height'].every(k=>Math.abs(x[k as keyof VideoRegion]-y[k as keyof VideoRegion])<=.025)")
s=s.replace('   if(same(a,b))continue', '''   if(same(a,b)){
    // Check against the retained mask too: adjacent tolerances can accumulate.
    const retained=[...nodes].filter(([t])=>t<=left).sort((x,y)=>y[0]-x[0])[0]?.[1]
    if(a.status!=='detected'||!retained||same({timeMs:left,status:'detected',region:retained},b))continue
   }''')
f.write_text(s,encoding='utf-8')
f=p/'desktop/src/autoRegionScan.test.mjs';s=f.read_text(encoding='utf-8').replace("times.map(t=>d(t,++count%2?A:B))", "times.map(t=>d(t,{x:++count*.01,y:.1,width:.005,height:.005}))");f.write_text(s,encoding='utf-8')
f=p/'backend-java/src/test/java/cn/videostudy/api/VideoRegionControllerTest.java';s=f.read_text(encoding='utf-8').replace('RestClient.create("http://unreachable")','org.mockito.Mockito.mock(RestClient.class)');f.write_text(s,encoding='utf-8')
