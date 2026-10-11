import test from 'node:test'
import assert from 'node:assert/strict'
import {validateRegionCombination, normalizeIgnoreSetting, regionAt, upsertRegionNode, removeRegionNode, regionNodes} from './videoRegionTimeline.ts'
const a={x:.7,y:.6,width:.2,height:.3},b={x:.1,y:.1,width:.2,height:.2}
test('first edit starts at zero even when drawn later',()=>{const t=upsertRegionNode(null,5000,a);assert.equal(regionNodes(t)[0].timeMs,0);assert.deepEqual(regionAt(t,0),a);assert.deepEqual(regionAt(t,9000),a)})
test('subsequent edits switch at exact boundaries and replace same timestamp',()=>{let t=upsertRegionNode(a,5000,b);assert.deepEqual(regionAt(t,4999),a);assert.deepEqual(regionAt(t,5000),b);t=upsertRegionNode(t,5000,a);assert.equal(regionNodes(t).length,2);assert.deepEqual(regionAt(t,5000),a)})
test('deleting a later node restores previous segment and preserves zero baseline',()=>{let t=upsertRegionNode(a,5000,b);t=removeRegionNode(t,5000);assert.deepEqual(regionAt(t,9000),a);assert.equal(regionNodes(removeRegionNode(t,0)).length,1)})
test('invalid timelines cannot silently turn into a static region',()=>{for(const v of [{nodes:[]},{nodes:[{timeMs:2,region:a}]},{nodes:[{timeMs:0,region:a},{timeMs:0,region:b}]},{nodes:[{timeMs:0,region:a},{timeMs:NaN,region:b}]}])assert.equal(normalizeIgnoreSetting(v),null);assert.deepEqual(normalizeIgnoreSetting(a),a)})

test('combined validation checks first baseline and all later boundaries',()=>{
 const board={x:.2,y:.2,width:.3,height:.3}, cover={x:.1,y:.1,width:.5,height:.5}, outside={x:.8,y:.8,width:.1,height:.1}
 const ignored=upsertRegionNode(cover,8000,outside)
 assert.throws(()=>validateRegionCombination(upsertRegionNode(null,10000,board,true),ignored),/0 秒/)
 assert.doesNotThrow(()=>validateRegionCombination(board,outside))
 assert.doesNotThrow(()=>validateRegionCombination(board,{x:.4,y:.4,width:.3,height:.3}))
 const analysis=upsertRegionNode(null,0,board,true)
 assert.throws(()=>validateRegionCombination(analysis,cover),/覆盖/)
 const safe=upsertRegionNode(cover,4000,outside)
 const later={nodes:[{timeMs:0,region:null},{timeMs:5000,region:board}]}
 assert.doesNotThrow(()=>validateRegionCombination(later,safe))
 assert.throws(()=>validateRegionCombination(later,removeRegionNode(safe,4000)),/5 秒/)
})
