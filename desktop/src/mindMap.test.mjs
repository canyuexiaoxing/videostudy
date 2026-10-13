import assert from 'node:assert/strict'
import test from 'node:test'
import { jumpToMindMapNode, mediaFingerprint, toCanvasNode, compactKnowledgeMap } from './mindMap.ts'

const node = {
  id: 'concept_0_0', title: '增长量公式', startMs: 999999, endMs: 999999, children: [],
  evidenceRefs: [{ sourceType: 'transcript', sourceId: 't_1', startMs: 28000,
    endMs: 31000, quote: '增长量等于现期减基期' }],
}

test('clicking a node seeks to its verified citation, not model time', async () => {
  const player = { currentTime: 0, play: async () => {} }
  assert.equal(await jumpToMindMapNode(node, player), 'playing')
  assert.equal(player.currentTime, 28)
})

test('a missing local file leaves the citation readable and requests relinking', async () => {
  assert.equal(await jumpToMindMapNode(node, null), 'missing_media')
})

test('browser autoplay rejection does not undo the seek', async () => {
  const player = { currentTime: 0, play: async () => { throw new Error('blocked') } }
  assert.equal(await jumpToMindMapNode(node, player), 'paused')
  assert.equal(player.currentTime, 28)
})

test('local media re-link fingerprint distinguishes files with the same length', async () => {
  const original = new Blob(['lesson A'])
  const matching = new Blob(['lesson A'])
  const wrong = new Blob(['lesson B'])
  assert.equal(await mediaFingerprint(original), await mediaFingerprint(matching))
  assert.notEqual(await mediaFingerprint(original), await mediaFingerprint(wrong))
})

test('canvas adapter preserves every level and stable source IDs', () => {
  const leaf = { id: 'leaf', title: '现期减基期', startMs: 43000, endMs: 45000,
    evidenceRefs: [{ sourceType: 'transcript', sourceId: 't_43', startMs: 43000, endMs: 45000, quote: '原话' }], children: [] }
  const root = { id: 'course', title: '课程', startMs: 43000, endMs: 45000,
    evidenceRefs: leaf.evidenceRefs, children: [] }
  let cursor = root
  for (let depth = 0; depth < 7; depth++) {
    const child = { ...root, id: `level_${depth}`, title: `第${depth}层`, children: [] }
    cursor.children = [child]
    cursor = child
  }
  cursor.children = [leaf]
  let canvas = toCanvasNode(root)
  for (let depth = 0; depth < 8; depth++) canvas = canvas.children[0]
  assert.equal(canvas.data._sourceId, 'leaf')
  assert.equal(canvas.data.text, '现期减基期')
  const compact = toCanvasNode(root, 2)
  assert.equal(compact.children[0].children[0].data.expand, false)
  assert.equal(compact.children[0].children[0].children.length, 1)
})

test('explanation sentences become sourced details of one concept, not many map leaves',()=>{
 const point=(id,title,quote)=>({id,title,startMs:1000,endMs:1900,evidenceRefs:[{sourceType:'transcript',sourceId:id,startMs:1000,endMs:1900,quote}],children:[]})
 const original={...node,id:'course',children:[{...node,id:'chapter',children:[{...node,id:'formula',title:'增长量公式',children:[point('meaning','符号含义','现期是当前时期'),point('condition','适用条件','时期口径保持一致'),point('case','本题代入计算','本题答案是20')]}]}]}
 const snapshot=JSON.stringify(original),root=compactKnowledgeMap(original),concept=root.children[0].children[0]
 assert.equal(concept.children.length,0);assert.deepEqual(concept.details.map(n=>n.title),['符号含义','适用条件']);assert.equal(concept.details[1].evidenceRefs[0].sourceId,'condition');assert.equal(JSON.stringify(original),snapshot)
})
test('independent subtopics are retained and a standalone formula is not discarded',()=>{
 const leaf={...node,id:'single',children:[]},branch={...node,id:'branch',children:[{...leaf,id:'detail'}]}
 const root=compactKnowledgeMap({...node,id:'course',children:[{...node,id:'chapter',children:[{...node,id:'topic',children:[branch,leaf]}]}]})
 assert.equal(root.children[0].children[0].children.length,2)
})

test('independent named rules remain separate canvas entries even when all are leaves',()=>{
 const leaf=(id,title)=>({...node,id,title,children:[]})
 const root=compactKnowledgeMap({...node,id:'course',children:[{...node,id:'chapter',children:[{...node,id:'topic',title:'求导法则',children:[leaf('product','乘积法则'),leaf('quotient','商法则'),leaf('condition','适用条件')]}]}]})
 const topic=root.children[0].children[0];assert.deepEqual(topic.children.map(n=>n.title),['乘积法则','商法则']);assert.deepEqual(topic.details.map(n=>n.title),['适用条件'])
})


test('explicit details preserve independent concepts and image evidence',()=>{
 const ref={sourceType:'image',sourceId:'frame_1200',startMs:1200,endMs:1200,quote:'课件截图'}
 const child={id:'independent',title:'任意独立知识点',startMs:1200,endMs:1200,evidenceRefs:[ref],children:[]}
 const detail={...child,id:'detail',title:'图中条件'}
 const root={...child,id:'root',title:'课程',children:[{...child,id:'topic',children:[{...child,id:'concept',children:[child],details:[detail]}]}]}
 const concept=compactKnowledgeMap(root).children[0].children[0]
 assert.deepEqual(concept.children.map(n=>n.id),['independent']);assert.deepEqual(concept.details.map(n=>n.id),['detail'])
 assert.equal(concept.details[0].evidenceRefs[0].sourceType,'image')
})

test('numbered method classifications remain nested canvas nodes',()=>{
 const methods=['1.给基期、增长率','2.给现期、基期','3.给现期、增长率'].map((title,i)=>({...node,id:`method_${i}`,title,children:[]}))
 const root=compactKnowledgeMap({...node,id:'course',children:[{...node,id:'chapter',children:[{...node,id:'growth',title:'增长量计算',children:methods}]}]})
 assert.equal(root.children[0].children[0].children.length,3)
})
