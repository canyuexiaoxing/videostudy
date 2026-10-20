import test from 'node:test'
import assert from 'node:assert/strict'
import {waitForRuntimeReady,readCourseJson} from './courseReadRecovery.ts'
import {latestRequests} from './mediaBinding.ts'
const ticket=()=>latestRequests().begin()
const quick={pollMs:1,statusTimeoutMs:20,timeoutMs:100}
test('native reading waits until ready, browser reading proceeds immediately',async()=>{
 let calls=0,waiting=0;await waitForRuntimeReady({status:async()=>({phase:++calls<3?'starting':'ready',apiOrigin:'http://127.0.0.1:1234'})},ticket(),{...quick,expectedOrigin:'http://127.0.0.1:1234',onWaiting:()=>waiting++});assert.equal(calls,3);assert.equal(waiting,2);await waitForRuntimeReady(undefined,ticket())
})
test('service start failure and changed origin fail safely',async()=>{
 await assert.rejects(waitForRuntimeReady({status:async()=>({phase:'error'})},ticket(),quick),/本机服务/)
 await assert.rejects(waitForRuntimeReady({status:async()=>({phase:'ready',apiOrigin:'http://127.0.0.1:9'})},ticket(),{...quick,expectedOrigin:'http://127.0.0.1:8'}),/地址/)
})
test('temporary failures retry only GET and recover',async()=>{
 const methods=[];let calls=0,retries=0
 const result=await readCourseJson('http://test',ticket(),{retryMs:1,fetcher:async(_,init)=>{methods.push(init.method);return ++calls<3?new Response('',{status:503}):Response.json({status:'completed'})},onRetry:()=>retries++})
 assert.deepEqual(result,{status:'completed'});assert.deepEqual(methods,['GET','GET','GET']);assert.equal(retries,2)
})
test('missing or forbidden records are not retried',async()=>{
 for(const code of [401,403,404,410]){let calls=0;await assert.rejects(readCourseJson('http://test',ticket(),{retryMs:1,fetcher:async()=>{calls++;return new Response('',{status:code})}}));assert.equal(calls,1)}
})
test('persistent network failure has bounded attempts',async()=>{
 let calls=0;await assert.rejects(readCourseJson('http://test',ticket(),{retryMs:1,fetcher:async()=>{calls++;throw new TypeError('offline')}}));assert.equal(calls,3)
})
test('switching course cancels the wait and rejects a late response',async()=>{
 const requests=latestRequests();const old=requests.begin();let release
 const pending=readCourseJson('http://test',old,{fetcher:()=>new Promise(resolve=>{release=resolve})});requests.begin();release(Response.json({id:'old'}));await assert.rejects(pending,{name:'AbortError'})
 const waitTicket=requests.begin();const waiting=waitForRuntimeReady({status:async()=>({phase:'starting'})},waitTicket,{...quick,pollMs:30});requests.begin();await assert.rejects(waiting,{name:'AbortError'})
})
test('hung response is bounded even when transport ignores abort',async()=>{
 let calls=0;await assert.rejects(readCourseJson('http://test',ticket(),{retryMs:1,requestTimeoutMs:5,fetcher:()=>{calls++;return new Promise(()=>{})}}));assert.equal(calls,3)
})
import {progressView} from './analysisProgress.ts'
test('startup and reconnect indicators are distinct from analysis or upload failure',()=>{
 assert.match(progressView('waiting_runtime',null).label,/启动中/);assert.equal(progressView('waiting_runtime',null).indeterminate,true)
 assert.match(progressView('reconnecting',null).label,/重新读取/);assert.match(progressView('read_failed',null).label,/读取失败/)
 assert.match(progressView('upload_failed',null).label,/上传未完成/);assert.doesNotMatch(progressView('read_failed',null).label,/上传/)
})

test('brief stopped initialization phase waits, stalled IPC has an overall deadline',async()=>{
 let calls=0;await waitForRuntimeReady({status:async()=>({phase:++calls===1?'stopped':'ready',apiOrigin:'http://127.0.0.1:1234'})},ticket(),quick);assert.equal(calls,2)
 await assert.rejects(waitForRuntimeReady({status:()=>new Promise(()=>{})},ticket(),{timeoutMs:15,statusTimeoutMs:3,pollMs:1}),/启动超时/)
})
