import test from 'node:test'
import assert from 'node:assert/strict'
import { previewTile, generatePreviewSheets, PreviewMemoryCache } from './timelinePreview.ts'

test('five-second tile lookup covers a whole video including its last second',()=>{
 assert.deepEqual(previewTile(102,3600),{index:20,sheet:1,x:0,y:0})
 assert.deepEqual(previewTile(99,3600),{index:19,sheet:0,x:960,y:405})
 assert.equal(previewTile(3600,3600).index,719)
 assert.equal(previewTile(-2,3600).index,0)
 assert.equal(previewTile(2,0),null)
})
test('generation waits for permission before decoding and resumes cached sheets',async()=>{
 let release;const permit=new Promise(r=>release=r);const calls=[];const stored=[]
 const task=generatePreviewSheets({duration:105,signal:new AbortController().signal,
  has:async sheet=>sheet===0,permit:async()=>permit,
  begin:()=>({capture:async index=>calls.push(index),finish:async()=>new Blob(['sheet'])}),save:async(i,b)=>stored.push(i)})
 await new Promise(r=>setImmediate(r));assert.deepEqual(calls,[])
 release();await task;assert.deepEqual(calls,[20]);assert.deepEqual(stored,[1])
})
test('cancellation during a frame never publishes an incomplete sheet',async()=>{
 const control=new AbortController();let saved=0
 await assert.rejects(generatePreviewSheets({duration:100,signal:control.signal,has:async()=>false,
  permit:async()=>{},begin:()=>({capture:async()=>control.abort(),finish:async()=>new Blob()}),save:async()=>saved++}),e=>e.name==='AbortError')
 assert.equal(saved,0)
})
test('a new foreground task stops additional capture until permission returns',async()=>{
 let release;let second=false;const captured=[];const permit=new Promise(r=>release=r)
 const task=generatePreviewSheets({duration:10,signal:new AbortController().signal,has:async()=>false,
 permit:async()=>{if(captured.length)await permit},begin:()=>({capture:async i=>captured.push(i),finish:async()=>new Blob()}),save:async()=>{}})
 await new Promise(r=>setImmediate(r));assert.deepEqual(captured,[0]);release();await task;assert.deepEqual(captured,[0,1])
})
test('memory eviction releases only RAM URLs; a sheet may be read from disk again',async()=>{
 const disposed=[];let loads=0;const cache=new PreviewMemoryCache(2,key=>{loads++;return Promise.resolve('url:'+key+':'+loads)},url=>disposed.push(url))
 await cache.get(0);await cache.get(1);await cache.get(0);await cache.get(2)
 assert.equal(disposed.length,1);assert.match(disposed[0],/url:1/)
 await cache.get(1);assert.equal(loads,4);cache.clear();assert.equal(disposed.length,4)
})

test('concurrent hover requests share disk reads and stale course loads release their URLs',async()=>{
 let release;let reads=0;const disposed=[];const cache=new PreviewMemoryCache(4,()=>{reads++;return new Promise(r=>release=r)},url=>disposed.push(url))
 const a=cache.get(2),b=cache.get(2);assert.equal(reads,1);cache.clear();release('old-video-url');assert.equal(await a,null);assert.equal(await b,null);assert.deepEqual(disposed,['old-video-url'])
})
