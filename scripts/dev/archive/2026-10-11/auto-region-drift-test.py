from pathlib import Path
p=Path('E:/workp/videostudy/desktop/src/autoRegionScan.test.mjs')
with p.open('a',encoding='utf-8') as out:out.write('''
test('small adjacent shifts cannot lose accumulated movement',async()=>{
 const r=await scanRegions(90000,async times=>times.map(t=>d(t,{x:.1+.0000006667*t,y:.1,width:.1,height:.1})))
 assert(r.setting.nodes.length>1)
 assert(Math.abs(r.setting.nodes.at(-1).region.x-.16)<.012)
})
test('budget exhaustion is explicit and a late result cannot survive cancellation',async()=>{
 let count=0
 const r=await scanRegions(86400000,async times=>times.map(t=>d(t,++count%2?A:B)))
 assert(r.samples.length<=64);assert(r.unresolved.length>0)
 const c=new AbortController()
 await assert.rejects(scanRegions(90000,async times=>{c.abort();return times.map(t=>d(t))},{signal:c.signal}),{name:'AbortError'})
})
''')
