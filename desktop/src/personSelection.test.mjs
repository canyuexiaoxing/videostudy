import {test} from 'node:test'
import assert from 'node:assert/strict'
import {loadPersonSelection,savePersonSelection} from './personSelection.ts'
test('person filtering is per video, default off and survives reopening',()=>{
 const values=new Map();const storage={getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)}
 assert.equal(loadPersonSelection(storage,'a'),'off');savePersonSelection(storage,'a','adjacent')
 assert.equal(loadPersonSelection(storage,'a'),'adjacent');assert.equal(loadPersonSelection(storage,'b'),'off')
 savePersonSelection(storage,'a','off');assert.equal(loadPersonSelection(storage,'a'),'off');assert.equal(loadPersonSelection(storage,''),'off')
})
test('unavailable or malformed browser storage cannot enable filtering',()=>{
 assert.equal(loadPersonSelection({getItem:()=>{throw Error('blocked')}},'a'),'off')
 assert.equal(loadPersonSelection({getItem:()=> 'cpu'},'a'),'off')
 assert.doesNotThrow(()=>savePersonSelection({setItem:()=>{throw Error('blocked')}},'a','adjacent'))
})
