<script setup lang="ts">
import {ref,watch,onUnmounted} from 'vue'
const props=defineProps<{image:Blob}>(),url=ref(''),dialog=ref<HTMLDialogElement|null>(null)
watch(()=>props.image,image=>{if(url.value)URL.revokeObjectURL(url.value);url.value=URL.createObjectURL(image)},{immediate:true})
onUnmounted(()=>{if(url.value)URL.revokeObjectURL(url.value)})
</script>
<template><button type="button" class="note-picture" aria-label="放大查看笔记图片" @click="dialog?.showModal()"><img :src="url" alt="笔记图片" loading="lazy" /></button><dialog ref="dialog" class="note-image-viewer"><button type="button" class="secondary" @click="dialog?.close()">关闭图片</button><img :src="url" alt="笔记图片原图" /></dialog></template>
<style scoped>
.note-picture{display:block;width:100%;padding:0;border:1px solid #dce5f5;border-radius:9px;overflow:hidden;background:#eef3fc;cursor:zoom-in}.note-picture img{display:block;width:100%;height:auto;max-height:260px;object-fit:contain}.note-image-viewer{max-width:94vw;max-height:94vh;border:1px solid #d9e3fb;border-radius:14px;padding:14px;background:#f7faff}.note-image-viewer img{display:block;max-width:88vw;max-height:80vh;object-fit:contain;margin-top:10px}.note-image-viewer::backdrop{background:#0f1c39a8}
</style>
