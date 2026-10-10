import test from 'node:test'
import assert from 'node:assert/strict'
import {progressView} from './analysisProgress.ts'
test('real page counts advance bar and completion depends on stored job status',()=>{
 const snapshot={stage:'pages',completedStages:3,totalStages:5,completedUnits:8,totalUnits:20}
 const view=progressView('processing',snapshot)
 assert.equal(view.label,'页面解读 · 已完成 8 / 20 页');assert.ok(Math.abs(view.ratio-.68)<1e-9)
 assert.equal(progressView('completed',null).ratio,1)
 assert.equal(progressView('processing',{...snapshot,stage:'saving',completedStages:4,completedUnits:0,totalUnits:0}).ratio,.95)
})
test('queue and missing data stay indeterminate and failed tasks retain last actual progress',()=>{
 assert.equal(progressView('queued',null).indeterminate,true)
 assert.equal(progressView('processing',null).indeterminate,true)
 assert.ok(Math.abs(progressView('failed',{stage:'pages',completedStages:3,totalStages:5,completedUnits:8,totalUnits:20}).ratio-.68)<1e-9)
 assert.equal(progressView('processing',{stage:'pages',completedStages:NaN,totalStages:5,completedUnits:0,totalUnits:20}).indeterminate,true)
 assert.equal(progressView('processing',{stage:'pages',completedStages:5,totalStages:5,completedUnits:20,totalUnits:20}).indeterminate,true)
})
test('saving never moves backwards after both learning materials finish',()=>{
 const materials=progressView('processing',{stage:'materials',completedStages:4,totalStages:5,completedUnits:2,totalUnits:2})
 const saving=progressView('processing',{stage:'saving',completedStages:4,totalStages:5,completedUnits:0,totalUnits:0})
 assert.equal(saving.ratio,materials.ratio)
 assert.ok(saving.ratio<1)
})