<script setup lang="ts">
import StructuredFigure from './StructuredFigure.vue'
import type {Diagram} from './practiceDiagram'
export type {Diagram} from './practiceDiagram'
defineProps<{diagram:Diagram}>()
</script>
<template>
 <StructuredFigure v-if="diagram.kind!=='circuit'||diagram.nodes" :diagram="diagram"/>
  <svg v-else viewBox="0 0 520 310" role="img" :aria-label="`闭合开关，R1=${diagram.r1}欧姆串联R2=${diagram.r2}和R3=${diagram.r3}并联，电源${diagram.voltage}伏`">
    <title>电路结构图</title><text x="22" y="28">电路结构图 · 开关已闭合</text>
    <g stroke="#334e82" stroke-width="2.5" fill="none"><path d="M55 145 V80 H95 M125 80 H165 M95 80 H125 M235 80 H290 V135 H330 M400 135 H455 V255 H55 V175 M290 135 V205 H330 M400 205 H455 V135 H400"/><circle cx="95" cy="80" r="3" fill="#fff"/><circle cx="125" cy="80" r="3" fill="#fff"/><rect x="165" y="67" width="70" height="26" rx="3"/><rect x="330" y="122" width="70" height="26" rx="3"/><rect x="330" y="192" width="70" height="26" rx="3"/><path d="M36 145 H74 M43 175 H67"/></g>
    <g fill="#334e82"><circle cx="290" cy="135" r="4"/><circle cx="455" cy="135" r="4"/><circle cx="455" cy="205" r="4"/></g>
    <text x="104" y="64">S</text><text x="175" y="56">R₁ {{ diagram.r1 }} Ω</text><text x="338" y="111">R₂ {{ diagram.r2 }} Ω</text><text x="338" y="185">R₃ {{ diagram.r3 }} Ω</text><text x="12" y="210">{{ diagram.voltage }} V</text><text x="95" y="285">R₁ 串联（R₂ ∥ R₃）</text>
  </svg>
</template>
<style scoped>svg{display:block;width:100%;height:auto;background:#fff}text{font:11px system-ui;fill:#53698f}</style>
