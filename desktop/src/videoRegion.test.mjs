import test from 'node:test'
import assert from 'node:assert/strict'
import {normalizeRegion,containedFrame,regionFromPoints} from './videoRegion.ts'
test('video frame mapping excludes letterbox space for wide and portrait videos',()=>{
 assert.deepEqual(containedFrame(1000,600,1920,1080),{left:0,top:18.75,width:1000,height:562.5})
 assert.deepEqual(containedFrame(1000,600,600,1200),{left:350,top:0,width:300,height:600})
 assert.equal(containedFrame(0,600,1920,1080).width,0)
})
test('reverse drags and out of frame pointers produce bounded normalized regions',()=>{
 assert.deepEqual(regionFromPoints(.8,.9,.2,.3),{x:.2,y:.3,width:.6000000000000001,height:.6000000000000001})
 assert.deepEqual(regionFromPoints(-1,-1,2,2),{x:0,y:0,width:1,height:1})
 assert.equal(regionFromPoints(.2,.2,.2,.8),null)
})
test('invalid saved regions cannot restore outside the video',()=>{
 for(const r of [null,{x:0,y:0,width:NaN,height:1},{x:.9,y:0,width:.2,height:.2},{x:0,y:-1,width:.2,height:.2}])assert.equal(normalizeRegion(r),null)
 assert.deepEqual(normalizeRegion({x:.8,y:.75,width:.2,height:.25}),{x:.8,y:.75,width:.19999999999999996,height:.25})
})
