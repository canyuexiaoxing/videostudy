import test from 'node:test'
import assert from 'node:assert/strict'
import { API_ORIGIN, setApiOrigin } from './apiOrigin.ts'
import { bootstrapRuntime, formatBytes, modelPercent, runtimeError, unavailableAnalysisModules } from './nativeRuntime.ts'

test('runtime origin accepts loopback HTTP only and never credentials or remote destinations', () => {
 assert.equal(API_ORIGIN, 'http://127.0.0.1:18080')
 for (const value of ['https://example.com', 'http://evil.example:18080', 'file:///tmp/api', 'http://key@127.0.0.1:1234', 'http://127.0.0.1:1234/api', 'http://127.0.0.1:1234/?key=secret', null]) assert.equal(setApiOrigin(value), false)
 assert.equal(setApiOrigin('http://127.0.0.1:31234'), true)
 assert.equal(API_ORIGIN, 'http://127.0.0.1:31234')
 assert.equal(setApiOrigin('http://127.0.0.1:18080'), true)
})

test('bootstrap binds private port before rendering and does not wait for model download', async () => {
 const status = {phase:'starting', apiOrigin:'http://127.0.0.1:32456'}
 assert.equal(await bootstrapRuntime({status:async () => status}), status)
 assert.equal(API_ORIGIN, status.apiOrigin)
 setApiOrigin('http://127.0.0.1:18080')
})

test('browser preserves its service but failed stalled or invalid native IPC fails closed',async()=>{
 setApiOrigin('http://127.0.0.1:18080')
 assert.equal(await bootstrapRuntime(),null)
 assert.equal(API_ORIGIN,'http://127.0.0.1:18080')
 assert.equal(await bootstrapRuntime({status:async()=>{throw Error('private details')}}),null)
 assert.equal(API_ORIGIN,'http://127.0.0.1:0')
 setApiOrigin('http://127.0.0.1:18080')
 assert.equal(await bootstrapRuntime({status:()=>new Promise(()=>{})},10),null)
 assert.equal(API_ORIGIN,'http://127.0.0.1:0')
 for(const origin of [undefined,'http://127.0.0.1:0','http://evil.example:18080']){await bootstrapRuntime({status:async()=>({phase:'error',apiOrigin:origin})});assert.equal(API_ORIGIN,'http://127.0.0.1:0')}
 setApiOrigin('http://127.0.0.1:18080')
})

test('progress and cache size handle missing values without claiming completion', () => {
 assert.equal(modelPercent(undefined), undefined)
 assert.equal(modelPercent({bytes:5,totalBytes:10}), 50)
 assert.equal(modelPercent({completed:1,total:4}), 25)
 assert.equal(modelPercent({percent:200}), 100)
 assert.equal(modelPercent({bytes:0,totalBytes:0}), undefined)
 assert.equal(formatBytes(undefined), '待统计')
 assert.equal(formatBytes(0), '0 B')
 assert.equal(formatBytes(1048576), '1.0 MB')
})

test('unknown native errors never display raw details or secrets', () => {
 assert.ok(!runtimeError('secret sk-abcdef /private/path').includes('secret'))
 assert.match(runtimeError('restore_busy'), /空闲/)
})

 test('optional person module only blocks analysis when adjacent filtering is selected',()=>{
 const status={hardware:{modules:{whisper:{available:true},ocr:{available:true},yolo:{available:false}}}}
 assert.deepEqual(unavailableAnalysisModules(status),[])
 assert.deepEqual(unavailableAnalysisModules(status,'adjacent'),['yolo'])
 status.hardware.modules.ocr.available=false
 assert.deepEqual(unavailableAnalysisModules(status),['ocr'])
 })
 test('native recovery errors provide readable actionable descriptions',()=>{
 for(const code of ['runtime_agent_timeout','runtime_initialization_failed','renderer_restore_recovery_required']) assert.match(runtimeError(code),/数据目录/)
 })

test('bootstrap obtains its origin without waiting for heavyweight model checks',async()=>{
 let fullCalls=0;const value={phase:'starting',apiOrigin:'http://127.0.0.1:32456'};
 const result=await bootstrapRuntime({connection:async()=>value,status:()=>{fullCalls++;return new Promise(()=>{})}},20);
 assert.equal(result,value);assert.equal(API_ORIGIN,value.apiOrigin);assert.equal(fullCalls,0);setApiOrigin('http://127.0.0.1:18080');
})
