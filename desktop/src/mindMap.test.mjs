import assert from 'node:assert/strict'
import test from 'node:test'
import { jumpToMindMapNode, mediaFingerprint, toCanvasNode } from './mindMap.ts'

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
