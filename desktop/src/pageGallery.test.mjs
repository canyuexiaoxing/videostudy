import test from 'node:test'
import assert from 'node:assert/strict'
import { groupFrameTimes, pageNearTime } from './pageGallery.ts'
test('group frames include all members and supplementary representatives without duplicates',()=>{
  assert.deepEqual(groupFrameTimes({memberFrameTimesMs:[4000,2000,4000,-1],representativeFrameTimesMs:[3000,4000]}),[2000,3000,4000])
  assert.deepEqual(groupFrameTimes({memberFrameTimesMs:[],representativeFrameTimesMs:[],firstFrameTimeMs:1000}),[1000])
})
test('playback chooses chronological group while manual navigation can use its index',()=>{
  const groups=[{pageIndex:2,firstFrameTimeMs:5000},{pageIndex:1,firstFrameTimeMs:1000}]
  assert.equal(pageNearTime(groups,0)?.pageIndex,1)
  assert.equal(pageNearTime(groups,6000)?.pageIndex,2)
  assert.equal(pageNearTime([],1000),undefined)
})
