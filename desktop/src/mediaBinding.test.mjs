import test from 'node:test'
import assert from 'node:assert/strict'
import { mediaBindingState, latestRequests } from './mediaBinding.ts'
const fingerprint='a'.repeat(64)
test('missing or damaged metadata never grants a match',()=>{
 for(const metadata of [null,'{}','broken',JSON.stringify({size:4}),JSON.stringify({size:4,fingerprint:'abc'})])
   assert.equal(mediaBindingState(metadata,4,fingerprint),'unverified')
})
test('both file size and fingerprint must match; a renamed original is allowed',()=>{
 const metadata=JSON.stringify({name:'original.mp4',size:4,fingerprint})
 assert.equal(mediaBindingState(metadata,4,fingerprint),'matched')
 assert.equal(mediaBindingState(metadata,5,fingerprint),'mismatch')
 assert.equal(mediaBindingState(metadata,4,'b'.repeat(64)),'mismatch')
 assert.equal(mediaBindingState(metadata,4,''),'unverified')
})
test('switching context aborts older requests and prevents late writes',async()=>{
 const requests=latestRequests(), old=requests.begin()
 requests.invalidate()
 assert.equal(old.signal.aborted,true);assert.equal(old.current(),false)
 const newer=requests.begin();assert.equal(newer.current(),true)
 let result='new video'
 await Promise.resolve();if(old.current())result='old result'
 assert.equal(result,'new video')
 requests.begin();assert.equal(newer.current(),false)
})
