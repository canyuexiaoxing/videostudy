import test from 'node:test'
import assert from 'node:assert/strict'
import { archiveStorageKey, serializeNote, validateNotesArchive, applyNotesArchive } from './notesArchive.ts'
const note={id:'original-note',scope:'course:original-course',timeMs:12345,text:'课程笔记',createdAt:'2026-10-19T00:00:00Z'}
const archive=notes=>({format:'framewise-renderer',version:1,notes,localStorage:{'framewise:appearance:v1':'blue'}})
function memoryStore(initial={}){const entries=new Map(Object.entries(initial));return {get length(){return entries.size},key:i=>[...entries.keys()][i]??null,getItem:key=>entries.get(key)??null,setItem:(key,value)=>entries.set(key,value),removeItem:key=>entries.delete(key),clear:()=>entries.clear()}}

test('note image and editable annotation round trip with exact scope and identity',async()=>{
 const bytes=new Uint8Array(70000).fill(123),image=new Blob([bytes],{type:'image/png'})
 const strokes=[{tool:'pen',color:'#ef4444',size:5,dashed:false,points:[{x:1,y:2},{x:3,y:4}]}]
 const encoded=await serializeNote({...note,image,annotation:{base:image,strokes}})
 const decoded=validateNotesArchive(archive([encoded])).notes[0]
 assert.equal(decoded.id,note.id);assert.equal(decoded.scope,note.scope);assert.equal(decoded.timeMs,note.timeMs)
 assert.deepEqual(new Uint8Array(await decoded.image.arrayBuffer()),bytes)
 assert.deepEqual(new Uint8Array(await decoded.annotation.base.arrayBuffer()),bytes)
 assert.deepEqual(decoded.annotation.strokes,strokes)
})

test('backup keeps study identities and preferences but rejects keys and unrelated browser state',()=>{
 for(const key of ['analysisHistory:v1','analysisMedia:abc-def','videostudy:practice-client','videoPersonSelection:v1:abc:1024'])assert.equal(archiveStorageKey(key),true)
 for(const key of ['apiKey','deepseekKey','framewise:preview:last-run','random','__proto__'])assert.equal(archiveStorageKey(key),false)
 assert.throws(()=>validateNotesArchive({...archive([]),localStorage:{apiKey:'secret'}}),/invalid_notes_backup/)
})

test('invalid duplicate identity, image encoding and annotation fail before writes',async()=>{
 let opened=false
 const bad=[archive([note,note]),archive([{...note,timeMs:-1}]),archive([{...note,image:{type:'text/html',base64:'PHNjcmlwdD4='}}]),archive([{...note,image:{type:'image/png',base64:'invalid!!'}}]),archive([{...note,annotation:{base:{type:'image/png',base64:'AA=='},strokes:[{tool:'pen',color:'red',size:5,dashed:false,points:[]}]}}])]
 for(const value of bad)await assert.rejects(applyNotesArchive(value,memoryStore(),()=>{opened=true;throw Error('should not open')}),/invalid_notes_backup/)
 assert.equal(opened,false)
})

test('restore replaces notes as one storage operation and preserves unrelated browser state',async()=>{
 const preferences=memoryStore({'framewise:appearance:v1':'classic',unrelated:'keep'});let received,closed=false
 await applyNotesArchive(archive([note]),preferences,()=>({replaceAll:async notes=>{received=notes},close:async()=>{closed=true}}))
 assert.deepEqual(received,[note]);assert.equal(preferences.getItem('framewise:appearance:v1'),'blue');assert.equal(preferences.getItem('unrelated'),'keep');assert.equal(closed,true)
})

test('failed notes transaction restores prior preferences and closes database',async()=>{
 const preferences=memoryStore({'framewise:appearance:v1':'classic'});let closed=false
 await assert.rejects(applyNotesArchive(archive([note]),preferences,()=>({replaceAll:async()=>{throw Error('disk_full')},close:async()=>{closed=true}})),/disk_full/)
 assert.equal(preferences.getItem('framewise:appearance:v1'),'classic');assert.equal(closed,true)
})
