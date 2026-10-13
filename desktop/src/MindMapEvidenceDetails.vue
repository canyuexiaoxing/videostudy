<script setup lang="ts">
import type { MindMapNode } from './mindMap'
defineProps<{ nodes: MindMapNode[]; apiBase: string; courseId: string; frameTimes: number[] }>()
const emit = defineEmits<{ seek: [timeMs: number, sourceId: string] }>()
function time(ms: number) { const seconds=Math.floor(ms/1000); return `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}` }
</script>

<template>
  <div class="knowledge-details">
    <details v-for="node in nodes" :key="node.id">
      <summary>{{ node.title }}</summary>
      <button v-for="source in node.evidenceRefs" :key="source.sourceId" type="button" class="mind-source-link" @click="emit('seek', source.startMs, source.sourceId)"><span class="time">{{ time(source.startMs) }}</span> {{ source.quote }}</button>
      <img v-for="source in node.evidenceRefs.filter(ref => ref.sourceType === 'image' && frameTimes.includes(ref.startMs))" :key="source.sourceId" loading="lazy" :src="`${apiBase}/transcriptions/${courseId}/frames/${source.startMs}`" :alt="`${time(source.startMs)} 的课件截图`" class="mind-evidence-image" />
      <MindMapEvidenceDetails v-if="node.details?.length || node.children.length" :nodes="[...(node.details ?? []), ...node.children]" :api-base="apiBase" :course-id="courseId" :frame-times="frameTimes" @seek="(ms, id) => emit('seek', ms, id)" />
    </details>
  </div>
</template>
