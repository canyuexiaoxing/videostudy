import test from 'node:test'
import assert from 'node:assert/strict'
import {serverHistory} from './history.ts'
const id='0af262c2-ed83-4f68-b246-ea7e6e290d92', other='65894cb5-9404-4bdd-a10b-a4bdcdd4d5fc'
test('server membership replaces stale local records and preserves only old display names',()=>{
 const local=[{id,name:'原课程',addedAt:'2020-01-01',status:'failed'},{id:other,name:'已删除',addedAt:'2020-01-01',status:'completed'}]
 const rows=[{id,name:null,status:'completed',createdAt:'2026-10-01T00:00:00Z'}]
 assert.deepEqual(serverHistory(rows,local),[{id,name:'原课程',status:'completed',addedAt:'2026-10-01T00:00:00Z'}])
 assert.deepEqual(serverHistory([],local),[])
})
test('fresh browser gets all statuses including expired and stable names',()=>{
 const entries=serverHistory([{id,name:'课程.mp4',status:'processing',createdAt:'2026-10-01T00:00:00Z'},{id:other,name:null,status:'expired',createdAt:'2026-09-01T00:00:00Z'}],[])
 assert.equal(entries[0].name,'课程.mp4');assert.equal(entries[1].status,'expired');assert.match(entries[1].name,/65894cb5/)
})
test('malformed server response fails instead of replacing cache with incomplete history',()=>{
 assert.throws(()=>serverHistory({},[]));assert.throws(()=>serverHistory([{id,status:'made-up',createdAt:'invalid'}],[]))
})
