from pathlib import Path
p=Path('E:/workp/videostudy/desktop/src/currentRegion.test.mjs')
p.write_text('''import {test} from 'node:test'
import assert from 'node:assert/strict'
import {currentRegionCandidate} from './autoRegionScan.ts'
const A={x:.7,y:.6,width:.2,height:.3},B={x:.1,y:.1,width:.2,height:.2}
test('current-frame first detection becomes default zero only on application',()=>{
 const result=currentRegionCandidate(null,{timeMs:5000,status:'detected',region:A})
 assert.deepEqual(result.setting.nodes,[{timeMs:0,region:A}]);assert.equal(result.samples[0].timeMs,5000)
})
test('current-frame candidate preserves earlier and later nodes and updates same timestamp',()=>{
 const original={nodes:[{timeMs:0,region:A},{timeMs:8000,region:null}]}
 const result=currentRegionCandidate(original,{timeMs:4000,status:'detected',region:B})
 assert.deepEqual(result.setting.nodes,[{timeMs:0,region:A},{timeMs:4000,region:B},{timeMs:8000,region:null}]);assert.equal(original.nodes.length,2)
 assert.equal(currentRegionCandidate(result.setting,{timeMs:4000,status:'detected',region:A}).setting.nodes.length,3)
})
test('absent uncertain and malformed detections cannot replace existing settings',()=>{
 for(const detection of [{timeMs:0,status:'absent',region:null},{timeMs:0,status:'uncertain',region:null},{timeMs:0,status:'detected',region:{...A,x:2}},{timeMs:-1,status:'detected',region:A}])assert.throws(()=>currentRegionCandidate(null,detection))
})
''',encoding='utf-8')
