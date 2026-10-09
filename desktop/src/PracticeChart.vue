<script setup lang="ts">
defineProps<{ title: string; unit: string; values: { label: string; value: number }[] }>()
const ceiling = 200
const baseline = 242
const height = 180
</script>

<template>
  <svg class="practice-chart" viewBox="0 0 480 300" role="img" :aria-label="`${title}，单位${unit}：${values.map(item => `${item.label}${item.value}`).join('，')}`">
    <title>{{ title }}</title>
    <text x="18" y="25" class="chart-title">{{ title }}</text>
    <text x="18" y="48" class="chart-unit">单位：{{ unit }}</text>
    <g v-for="tick in [0, 50, 100, 150, 200]" :key="tick">
      <line x1="58" x2="454" :y1="baseline - tick / ceiling * height" :y2="baseline - tick / ceiling * height" stroke="#e6ecfa" :stroke-dasharray="tick ? '4 5' : undefined" />
      <text x="47" :y="baseline - tick / ceiling * height + 4" text-anchor="end" class="chart-tick">{{ tick }}</text>
    </g>
    <g v-for="(item, i) in values" :key="item.label">
      <rect :x="106 + i * 130" :y="baseline - item.value / ceiling * height" width="54" :height="item.value / ceiling * height" rx="5" :fill="['#aac0ff', '#7297f8', '#426aee'][i % 3]" />
      <text :x="133 + i * 130" :y="baseline - item.value / ceiling * height - 10" text-anchor="middle" class="chart-value">{{ item.value }}</text>
      <text :x="133 + i * 130" y="267" text-anchor="middle" class="chart-label">{{ item.label }}</text>
    </g>
    <text x="256" y="291" text-anchor="middle" class="chart-unit">模拟数据，仅用于练习</text>
  </svg>
</template>

<style scoped>
.practice-chart{display:block;width:100%;height:auto;font-family:inherit;background:#fff}.chart-title{fill:#25395f;font-size:14px;font-weight:700}.chart-unit,.chart-tick{fill:#7283a6;font-size:11px}.chart-value{fill:#3056bd;font-size:14px;font-weight:700}.chart-label{fill:#415879;font-size:12px}
</style>
