import assert from 'node:assert/strict'
import test from 'node:test'
import { toWebVtt } from './subtitles.ts'
import * as subtitles from './subtitles.ts'

const source = [{ id: 's1', startMs: 1234, endMs: 2876, text: '原始转写' }]
const corrected = [{ id: 's1', startMs: 1234, endMs: 2876, text: '纠正转写' }]

test('seeking to the next subtitle start cannot activate the previous cue at the same endpoint', () => {
  const segments = [
    { startMs: 628480, endMs: 639370, text: '前一句' },
    { startMs: 639370, endMs: 645370, text: '后一句' },
  ]
  const before = structuredClone(segments)
  const vtt = toWebVtt(segments)
  assert.match(vtt, /00:10:28\.480 --> 00:10:39\.369/)
  assert.match(vtt, /00:10:39\.370 --> 00:10:45\.370/)
  assert.deepEqual(segments, before)
})

test('playback cues clip true overlaps but retain gaps and final cue end', () => {
  const vtt = toWebVtt([
    { startMs: 1000, endMs: 4000, text: '重叠前句' },
    { startMs: 3000, endMs: 3500, text: '下一句' },
    { startMs: 5000, endMs: 6000, text: '末句' },
  ])
  assert.match(vtt, /00:00:01\.000 --> 00:00:02\.999/)
  assert.match(vtt, /00:00:03\.000 --> 00:00:03\.500/)
  assert.match(vtt, /00:00:05\.000 --> 00:00:06\.000/)
})

test('old completed subtitle versions can be updated without auto-requesting', () => {
  assert.equal(subtitles.needsSubtitleUpdate({ status: 'completed', result: { promptVersion: 'subtitle-calibration-v3' } }), true)
  assert.equal(subtitles.needsSubtitleUpdate({ status: 'completed', result: { promptVersion: 'subtitle-calibration-v8-page-understanding' } }), false)
  assert.equal(subtitles.needsSubtitleUpdate({ status: 'processing', result: { promptVersion: 'subtitle-calibration-v3' } }), false)
  assert.equal(subtitles.needsSubtitleUpdate(null), false)
})

test('AI selection falls back to original while queued, failed, or unavailable', () => {
  assert.equal(typeof subtitles.selectSubtitleSource, 'function')
  for (const status of ['not_requested', 'awaiting_source', 'queued', 'processing', 'failed', 'unsupported']) {
    const selected = subtitles.selectSubtitleSource(source, 'en', { id: 'course', status, result: { segments: corrected, targetLanguage: 'zh' } }, 'ai')
    assert.equal(selected.segments, source)
    assert.equal(selected.language, 'en')
    assert.equal(selected.mode, 'original')
  }
})

test('partial AI subtitles are selectable without replacing raw segments or their times', () => {
  assert.equal(typeof subtitles.selectSubtitleSource, 'function')
  const selected = subtitles.selectSubtitleSource(source, 'zh', {
    id: 'course', status: 'partial', result: { segments: corrected, targetLanguage: 'en', mode: 'translation' }
  }, 'ai')
  assert.equal(selected.language, 'en')
  assert.equal(selected.mode, 'ai')
  assert.deepEqual(selected.segments, [{ id: 's1', startMs: 1234, endMs: 2876, text: '纠正转写' }])
  assert.deepEqual(source, [{ id: 's1', startMs: 1234, endMs: 2876, text: '原始转写' }])
  const original = subtitles.selectSubtitleSource(source, 'zh-CN', { id: 'course', status: 'completed', result: { segments: corrected, targetLanguage: 'en' } }, 'original')
  assert.equal(original.segments, source)
  assert.equal(original.language, 'zh-CN')
})

test('changing native caption visibility preserves the video playback position and paused state', () => {
  assert.equal(typeof subtitles.setSubtitleVisibility, 'function')
  const track = { mode: 'hidden' }
  const player = { currentTime: 92.125, paused: false, textTracks: [track] }
  subtitles.setSubtitleVisibility(player, true)
  assert.equal(track.mode, 'showing')
  subtitles.setSubtitleVisibility(player, false)
  assert.equal(track.mode, 'hidden')
  assert.equal(player.currentTime, 92.125)
  assert.equal(player.paused, false)
})

test('subtitle polling queries an older course and stops once a partial result is available', async () => {
  assert.equal(typeof subtitles.createSubtitlePoller, 'function')
  const received = []
  const poller = subtitles.createSubtitlePoller({
    fetchJob: async (id, target) => ({ id, status: 'partial', result: { targetLanguage: target, segments: corrected } }),
    onJob: job => received.push(job), onError: message => assert.fail(message)
  })
  await poller.start('older-course', 'en')
  assert.equal(received.length, 1)
  assert.equal(received[0].id, 'older-course')
  assert.equal(received[0].result.targetLanguage, 'en')
  poller.stop()
})

test('late subtitle responses from a previous course or language cannot replace the current course', async () => {
  assert.equal(typeof subtitles.createSubtitlePoller, 'function')
  const received = []
  let finishOld
  const poller = subtitles.createSubtitlePoller({
    fetchJob: async (id, target) => id === 'old-course' ? new Promise(resolve => { finishOld = resolve })
      : ({ id, status: 'completed', result: { targetLanguage: target, segments: corrected } }),
    onJob: job => received.push(job), onError: message => assert.fail(message)
  })
  const oldRequest = poller.start('old-course', 'source')
  await poller.start('new-course', 'en')
  finishOld({ id: 'old-course', status: 'completed', result: { targetLanguage: 'zh', segments: source } })
  await oldRequest
  assert.deepEqual(received.map(job => job.id), ['new-course'])
  poller.stop()
})

test('stopping subtitle polling ignores a pending request after file change or unmount', async () => {
  assert.equal(typeof subtitles.createSubtitlePoller, 'function')
  let finish
  const received = []
  const poller = subtitles.createSubtitlePoller({
    fetchJob: async () => new Promise(resolve => { finish = resolve }),
    onJob: job => received.push(job), onError: message => assert.fail(message)
  })
  const request = poller.start('course', 'source')
  poller.stop()
  finish({ id: 'course', status: 'completed', result: { segments: corrected, targetLanguage: 'zh' } })
  await request
  assert.deepEqual(received, [])
})

test('subtitle polling recovers from transient errors and resets the retry allowance after success', { timeout: 1000 }, async () => {
  const received = []
  let attempt = 0
  let finish
  let fail
  const done = new Promise((resolve, reject) => { finish = resolve; fail = reject })
  const poller = subtitles.createSubtitlePoller({
    intervalMs: 1, retryDelayMs: 1,
    fetchJob: async id => {
      attempt++
      if ([1, 3, 4].includes(attempt)) throw new Error('Temporary network failure')
      return { id, status: attempt === 2 ? 'queued' : 'completed', result: { segments: corrected, targetLanguage: 'zh' } }
    },
    onJob: job => { received.push(job.status); if (job.status === 'completed') finish() },
    onError: message => fail(new Error(message))
  })
  await poller.start('course', 'source')
  await done
  assert.deepEqual(received, ['queued', 'completed'])
  assert.equal(attempt, 5)
  poller.stop()
})

test('subtitle polling bounds consecutive network failures and preserves the original fallback', { timeout: 1000 }, async () => {
  let attempt = 0
  let finish
  const done = new Promise(resolve => { finish = resolve })
  const poller = subtitles.createSubtitlePoller({
    retryDelayMs: 1,
    fetchJob: async () => { attempt++; throw new Error('Temporary network failure') },
    onJob: () => assert.fail('Failed queries must not replace subtitles'),
    onError: message => finish(message)
  })
  await poller.start('course', 'source')
  assert.equal(await done, 'Temporary network failure')
  assert.equal(attempt, 3)
  assert.equal(subtitles.selectSubtitleSource(source, 'zh', null, 'ai').segments, source)
  poller.stop()
})

test('subtitle polling does not retry a permanently missing course', async () => {
  assert.equal(typeof subtitles.SubtitleRequestError, 'function')
  let attempt = 0
  const errors = []
  const poller = subtitles.createSubtitlePoller({
    retryDelayMs: 1,
    fetchJob: async () => { attempt++; throw new subtitles.SubtitleRequestError(404) },
    onJob: () => assert.fail('Missing course must not replace subtitles'), onError: message => errors.push(message)
  })
  await poller.start('deleted-course', 'source')
  assert.equal(attempt, 1)
  assert.deepEqual(errors, ['HTTP 404'])
  poller.stop()
})

test('VTT preserves timestamp milliseconds, multiline text and long videos', () => {
  const output = toWebVtt([{startMs:3599123,endMs:3602456,text:'第一行\n第二行'}])
  assert.ok(output.startsWith('WEBVTT\n\n'))
  assert.ok(output.includes('00:59:59.123 --> 01:00:02.456'))
  assert.ok(output.includes('第一行\n第二行'))
})

test('subtitle text cannot become cue markup or prematurely terminate a cue', () => {
  const output = toWebVtt([{startMs:0,endMs:1000,text:'<b>字幕</b> & 数据\n\n另一句'}])
  assert.ok(output.includes('&lt;b&gt;字幕&lt;/b&gt; &amp; 数据'))
  assert.ok(!output.includes('数据\n\n另一句'))
  assert.equal(toWebVtt([{startMs:-1,endMs:0,text:'invalid'}]), 'WEBVTT\n\n')
})
