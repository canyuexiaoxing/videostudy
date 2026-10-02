import assert from 'node:assert/strict'
import test from 'node:test'
import { toWebVtt } from './subtitles.ts'

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
