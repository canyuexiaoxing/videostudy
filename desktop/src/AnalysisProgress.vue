<script setup lang="ts">
import {computed} from 'vue'
import {progressView} from './analysisProgress'
import type {AnalysisProgress} from './analysisProgress'
const props=defineProps<{state:string;progress:AnalysisProgress|null}>()
const view=computed(()=>progressView(props.state,props.progress))
const steps=computed(()=>['转写与选图','补采检查','同页分组',props.progress?.totalGroups!=null||props.progress?.stage==='groups'?'组图文理解':'页面解读','思维导图'])
</script>
<template>
 <section v-if="state" class="analysis-progress" :class="{'progress-failed':['failed','interrupted','read_failed','upload_failed'].includes(state)}" aria-label="视频分析进度">
  <div class="progress-heading"><strong role="status" aria-live="polite">{{view.label}}</strong><span>已完成 {{view.completed}} / 5 个阶段</span></div>
  <div class="progress-track" :class="{'progress-indeterminate':view.indeterminate}" role="progressbar" aria-label="分析阶段完成情况" :aria-valuenow="view.indeterminate?undefined:view.ratio*5" :aria-valuemin="0" :aria-valuemax="5" :aria-valuetext="view.label"><div class="progress-fill" :style="{width:`${view.ratio*100}%`}"></div></div>
  <div class="progress-steps" aria-hidden="true"><span v-for="(step,index) in steps" :key="step" :class="{done:index<view.completed,current:index===view.completed&&state==='processing'}">{{step}}</span></div>
 </section>
</template>
<style scoped>
.analysis-progress{flex-basis:100%;min-width:0;margin:0 0 13px;padding:12px 14px;border:1px solid #e1e8f7;border-radius:10px;background:#f8faff}.progress-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:9px;font-size:12px;color:#617391}.progress-heading strong{font-weight:600;color:#3559ad}.progress-heading>span{white-space:nowrap;font-size:11px}.progress-track{height:7px;background:#e4eafb;border-radius:6px;overflow:hidden}.progress-fill{height:100%;border-radius:6px;background:#5276ee;transition:width .3s ease}.progress-steps{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5px;margin-top:9px;font-size:11px;color:#8796ae}.progress-steps span{text-align:center}.progress-steps .done{color:#4d70c0}.progress-steps .current{color:#315dec;font-weight:600}.progress-indeterminate .progress-fill{width:25%!important;animation:progress-sweep 1.6s ease-in-out infinite}.progress-failed .progress-fill{background:#b77782}.progress-failed .progress-heading strong{color:#a34d60}@keyframes progress-sweep{from{transform:translateX(-100%)}to{transform:translateX(400%)}}@media(prefers-reduced-motion:reduce){.progress-fill{transition:none}.progress-indeterminate .progress-fill{animation:none}}@media(max-width:600px){.progress-heading{align-items:flex-start;flex-direction:column;gap:4px}.progress-steps{font-size:10px}.analysis-progress{padding:10px}}
</style>
