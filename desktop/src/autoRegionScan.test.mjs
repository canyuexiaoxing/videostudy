import {test} from 'node:test'
import assert from 'node:assert/strict'
import {scanRegions} from './autoRegionScan.ts'
const A={x:.7,y:.6,width:.2,height:.3},B={x:.1,y:.1,width:.2,height:.2}
const d=(timeMs,region=A)=>({timeMs,status:region?'detected':'absent',region})
test('stable four-point scan only inspects beginning thirds and last frame',async()=>{
 const calls=[];const r=await scanRegions(90000,async times=>{calls.push(...times);return times.map(t=>d(t))})
 assert.deepEqual(calls,[0,30000,60000,89900]);assert.equal(r.setting.nodes.length,1);assert.deepEqual(r.setting.nodes[0],{timeMs:0,region:A})
})
test('only changing intervals recurse until30seconds and restore absence',async()=>{
 const calls=[];const r=await scanRegions(360000,async times=>{calls.push(...times);return times.map(t=>d(t,t<75000?A:t<250000?B:null))})
 assert(calls.length>4);assert(!calls.includes(180000));assert.equal(r.setting.nodes.length,3)
 assert(Math.abs(r.setting.nodes[1].timeMs-75000)<=15000);assert(Math.abs(r.setting.nodes[2].timeMs-250000)<=15000)
 assert.equal(r.setting.nodes[2].region,null)
})
test('uncertainty never turns into confirmed absence',async()=>{
 const r=await scanRegions(90000,async times=>times.map(t=>t===30000?{timeMs:t,status:'uncertain',region:null}:d(t)))
 assert(r.unresolved.length>0);assert.equal(r.setting.nodes[0].region,null)
})
test('malformed batch cannot create a candidate and cancellation stops',async()=>{
 await assert.rejects(scanRegions(90000,async times=>times.map(t=>d(t+1))))
 const c=new AbortController();c.abort();await assert.rejects(scanRegions(90000,async()=>[],{signal:c.signal}),{name:'AbortError'})
})

test('small adjacent shifts cannot lose accumulated movement',async()=>{
 const r=await scanRegions(90000,async times=>times.map(t=>d(t,{x:.1+.0000006667*t,y:.1,width:.1,height:.1})))
 assert(r.setting.nodes.length>1)
 assert(Math.abs(r.setting.nodes.at(-1).region.x-.16)<.012)
})
test('budget exhaustion is explicit and a late result cannot survive cancellation',async()=>{
 let count=0
 const r=await scanRegions(86400000,async times=>times.map(t=>d(t,{x:++count*.01,y:.1,width:.005,height:.005})))
 assert(r.samples.length<=64);assert(r.unresolved.length>0)
 const c=new AbortController()
 await assert.rejects(scanRegions(90000,async times=>{c.abort();return times.map(t=>d(t))},{signal:c.signal}),{name:'AbortError'})
})
