import test from 'node:test'
import assert from 'node:assert/strict'
import { timelineChapters, chapterAt, timeAtPointer } from './chapters.ts'
test('chapter widths follow time and last chapter extends to actual local duration',()=>{
  const chapters=timelineChapters([{id:'a',title:'介绍',startMs:0,endMs:10000},{id:'b',title:'例题',startMs:10000,endMs:15000}],20)
  assert.equal(chapters[0].endMs,10000)
  assert.equal(chapters[1].endMs,20000)
  assert.equal(chapterAt(chapters,10000).id,'b')
  assert.equal(chapterAt(chapters,19999).id,'b')
})
test('progress pointer clamps positions and never seeks to invalid duration',()=>{
  assert.equal(timeAtPointer(80,100,200,60),0)
  assert.equal(timeAtPointer(200,100,200,60),30)
  assert.equal(timeAtPointer(500,100,200,60),60)
  assert.equal(timeAtPointer(200,100,200,Infinity),0)
})
