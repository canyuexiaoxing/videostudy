<script setup lang="ts">
import { ref } from 'vue'
type Ref={sourceId:string;startMs:number;endMs:number;quote:string;sourceType?:string}
export type Note={title:string;anchor:Ref;image:Ref|null;points:{label:string;text:string}[];children:Note[]}
defineProps<{note:Note;courseId:string;depth:number}>()
const emit=defineEmits<{seek:[time:number]}>()
const imageFailed=ref(false)
const time=(ms:number)=>{const seconds=Math.floor(ms/1000);return `${Math.floor(seconds/60).toString().padStart(2,'0')}:${(seconds%60).toString().padStart(2,'0')}`}
</script>
<template>
  <section class="note-section" :class="{ 'note-nested': depth > 1 }">
    <div class="note-title"><strong>{{ note.title }}</strong><button type="button" class="note-time" :aria-label="`回看${note.title} ${time(note.anchor.startMs)}`" @click="emit('seek',note.anchor.startMs)">{{ time(note.anchor.startMs) }}</button></div>
    <img v-if="note.image && !imageFailed" class="note-image" loading="lazy" :src="`http://127.0.0.1:18080/api/transcriptions/${courseId}/frames/${note.image.startMs}`" :alt="`${note.title}的课件画面`" @error="imageFailed=true" />
    <ul v-if="note.points.length" class="note-points"><li v-for="(point,i) in note.points" :key="i"><strong v-if="point.label">{{ point.label }}：</strong>{{ point.text }}</li></ul>
    <AiNoteSection v-for="(child,i) in note.children" :key="i" :note="child" :course-id="courseId" :depth="depth+1" @seek="emit('seek',$event)" />
  </section>
</template>
<style scoped>
.note-section{margin:24px 0;color:#23334e}.note-nested{margin:18px 0 0;padding-left:16px;border-left:2px solid #e9eef8}.note-title{display:flex;align-items:baseline;flex-wrap:wrap;gap:10px;font-size:18px;line-height:1.6}.note-nested .note-title{font-size:16px}.note-time{padding:0;border:0;border-bottom:1px solid #2c8cf0;background:transparent;color:#188be9;font-size:inherit;white-space:nowrap;cursor:pointer}.note-image{display:block;width:auto;max-width:100%;height:auto;max-height:420px;object-fit:contain;margin:12px 0}.note-points{margin:12px 0;padding-left:22px;font-size:15px;line-height:1.9;overflow-wrap:anywhere}.note-points li+li{margin-top:5px}
</style>
