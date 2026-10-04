import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeAppearance, appearanceCss, positionCue } from './subtitleAppearance.ts'

test('saved appearance rejects invalid colors and clamps sizes and opacity', () => {
  const value=normalizeAppearance({fontSize:999,textColor:'red;display:none',backgroundOpacity:-5,vertical:101})
  assert.equal(value.fontSize,48)
  assert.equal(value.textColor,'#ffffff')
  assert.equal(value.backgroundOpacity,0)
  assert.equal(value.vertical,90)
  assert.equal(normalizeAppearance(null).vertical,80)
})
test('cue appearance retains timestamps and uses percentage positioning', () => {
  const cue={startTime:10,endTime:12,text:'字幕'}
  positionCue(cue,normalizeAppearance({vertical:20}))
  assert.equal(cue.line,20)
  assert.equal(cue.snapToLines,false)
  assert.equal(cue.startTime,10)
  assert.equal(cue.text,'字幕')
  const css=appearanceCss(normalizeAppearance({backgroundOpacity:0,textOpacity:50,fontSize:28}))
  assert.match(css,/font-size:28px/)
  assert.match(css,/rgba\(255,255,255,0.5\)/)
  assert.match(css,/rgba\(16,24,39,0\)/)
})
