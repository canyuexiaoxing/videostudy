<script setup lang="ts">
import { computed } from 'vue'
export type Diagram = { kind: 'bar' | 'line' | 'table' | 'circuit'; title?: string; unit?: string; values?: {label:string;value:number}[]; topology?:string; voltage?:number; r1?:number; r2?:number; r3?:number }
const props=defineProps<{ diagram: Diagram }>()
const values=computed(()=>props.diagram.values ?? [])
const ceiling=computed(()=>Math.max(1,...values.value.map(v=>v.value))*1.15)
const x=(i:number)=>70+(i+.5)*370/Math.max(1,values.value.length)
const y=(v:number)=>230-v/ceiling.value*150
const points=computed(()=>values.value.map((v,i)=>`${x(i)},${y(v.value)}`).join(' '))
</script>
<template>
  <table v-if="diagram.kind==='table'" class="figure-table"><caption>{{ diagram.title }}（{{ diagram.unit }}）</caption><thead><tr><th>项目</th><th>数值</th></tr></thead><tbody><tr v-for="v in values" :key="v.label"><td>{{ v.label }}</td><td>{{ v.value }}</td></tr></tbody></table>
  <svg v-else-if="diagram.kind==='circuit'" viewBox="0 0 520 310" role="img" :aria-label="`闭合开关，R1=${diagram.r1}欧姆串联R2=${diagram.r2}和R3=${diagram.r3}并联，电源${diagram.voltage}伏`">
    <title>电路结构图</title><text x="22" y="28">电路结构图 · 开关已闭合</text>
    <g stroke="#334e82" stroke-width="2.5" fill="none"><path d="M55 145 V80 H95 M125 80 H165 M95 80 H125 M235 80 H290 V135 H330 M400 135 H455 V255 H55 V175 M290 135 V205 H330 M400 205 H455 V135 H400"/><circle cx="95" cy="80" r="3" fill="#fff"/><circle cx="125" cy="80" r="3" fill="#fff"/><rect x="165" y="67" width="70" height="26" rx="3"/><rect x="330" y="122" width="70" height="26" rx="3"/><rect x="330" y="192" width="70" height="26" rx="3"/><path d="M36 145 H74 M43 175 H67"/></g>
    <g fill="#334e82"><circle cx="290" cy="135" r="4"/><circle cx="455" cy="135" r="4"/><circle cx="455" cy="205" r="4"/></g>
    <text x="104" y="64">S</text><text x="175" y="56">R₁ {{ diagram.r1 }} Ω</text><text x="338" y="111">R₂ {{ diagram.r2 }} Ω</text><text x="338" y="185">R₃ {{ diagram.r3 }} Ω</text><text x="12" y="210">{{ diagram.voltage }} V</text><text x="95" y="285">R₁ 串联（R₂ ∥ R₃）</text>
  </svg>
  <svg v-else viewBox="0 0 480 290" role="img" :aria-label="`${diagram.title}，单位${diagram.unit}：${values.map(v=>`${v.label} ${v.value}`).join('，')}`">
    <title>{{ diagram.title }}</title><text x="20" y="25" class="figure-title">{{ diagram.title }}</text><text x="20" y="49">单位：{{ diagram.unit }}</text>
    <g v-for="i in [0,1,2,3,4]" :key="i"><line x1="60" x2="455" :y1="y(ceiling*i/4)" :y2="y(ceiling*i/4)" stroke="#e6ecfa"/><text x="51" :y="y(ceiling*i/4)+4" text-anchor="end">{{ +(ceiling*i/4).toPrecision(3) }}</text></g>
    <polyline v-if="diagram.kind==='line'" :points="points" fill="none" stroke="#426aee" stroke-width="3"/>
    <g v-for="(v,i) in values" :key="v.label"><rect v-if="diagram.kind==='bar'" :x="x(i)-Math.min(24,130/values.length)" :y="y(v.value)" :width="Math.min(48,260/values.length)" :height="230-y(v.value)" rx="4" fill="#7297f8"/><circle v-else :cx="x(i)" :cy="y(v.value)" r="4" fill="#426aee"/><text :x="x(i)" :y="y(v.value)-9" text-anchor="middle" class="figure-value">{{ v.value }}</text><text :x="x(i)" y="254" text-anchor="middle">{{ v.label }}</text></g>
  </svg>
</template>
<style scoped>svg{display:block;width:100%;height:auto;background:#fff}text{font:11px system-ui;fill:#53698f}.figure-title{font-weight:700;font-size:14px;fill:#25395f}.figure-value{font-weight:700;fill:#3056bd}.figure-table{width:100%;border-collapse:collapse;font-size:13px}.figure-table caption{padding:12px;font-weight:700}.figure-table td,.figure-table th{padding:12px;border:1px solid #e0e7f5;text-align:left}.figure-table th{background:#f3f6ff}</style>
