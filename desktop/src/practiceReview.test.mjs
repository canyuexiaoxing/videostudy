import test from 'node:test'
import assert from 'node:assert/strict'
import { reviewTargets } from './practiceReview.ts'
test('prefers a cited explanation matching the knowledge point over an unrelated cited sentence',()=>{
 const refs=[{sourceId:'intro',startMs:1000,endMs:2000,quote:'我们来看下一道题'},
 {sourceId:'formula',startMs:8000,endMs:11000,quote:'增长率的分母应当用基期，不是现期'}]
 const ranked=reviewTargets(refs,'增长率的分母','分母使用基期','误用现期作为分母')
 assert.equal(ranked[0].sourceId,'formula');assert.equal(ranked[0].startMs,8000)
 assert.equal(ranked[0].endMs,11000);assert.deepEqual(refs.map(r=>r.sourceId),['intro','formula'])
})
test('never invents a time when evidence is missing or unusable',()=>{
 assert.deepEqual(reviewTargets([], '增长率','',''),[])
 assert.deepEqual(reviewTargets([{sourceId:'bad',startMs:-1,quote:'增长率'}], '增长率','',''),[])
 assert.deepEqual(reviewTargets([{sourceId:'bad',startMs:0,endMs:0,quote:'增长率'}], '增长率','',''),[])
})
test('deduplicates sources and preserves a chronological fallback without claiming a match',()=>{
 const ranked=reviewTargets([{sourceId:'late',startMs:3000,quote:'开始解题'},
 {sourceId:'early',startMs:1000,quote:'请看题目'},{sourceId:'early',startMs:1000,quote:'请看题目'}], '基期','','')
 assert.equal(ranked.length,2);assert.equal(ranked[0].sourceId,'early');assert.equal(ranked[0].matched,false)
})


test('verified screenshot citations remain available as zero-duration review targets',()=>{
 const ref={sourceType:'image',sourceId:'frame_1200',startMs:1200,endMs:1200,quote:'课件截图'}
 assert.equal(reviewTargets([ref],'图中公式','','')[0].sourceId,'frame_1200')
 assert.deepEqual(reviewTargets([{...ref,sourceId:'frame_9999'}],'图中公式','',''),[])
})
