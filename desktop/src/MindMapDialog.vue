<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import MindMapCanvas from './MindMapCanvas.vue'
import type { MindMapNode } from './mindMap'

defineProps<{ root: MindMapNode }>()
const emit = defineEmits<{ close: []; select: [node: MindMapNode] }>()
const dialog = ref<HTMLDialogElement | null>(null)
function close() { dialog.value?.close() }
function backdropClick(event: MouseEvent) {
  if (event.target !== dialog.value) return
  const rect = dialog.value!.getBoundingClientRect()
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) close()
}
onMounted(() => dialog.value?.showModal())
onBeforeUnmount(() => dialog.value?.close())
</script>

<template>
  <dialog ref="dialog" class="expanded-map-dialog" aria-labelledby="expanded-map-title" @close="emit('close')" @click="backdropClick">
    <header class="expanded-map-heading">
      <div><h2 id="expanded-map-title">课程思维导图</h2><p>拖动或缩放查看全图；点击知识点可返回课程并回看讲解。</p></div>
      <button type="button" autofocus @click="close">关闭</button>
    </header>
    <MindMapCanvas :root="root" @select="emit('select', $event)" />
  </dialog>
</template>

<style scoped>
.expanded-map-dialog { box-sizing: border-box; width: calc(100vw - 48px); max-width: 1800px; height: calc(100dvh - 48px); max-height: calc(100dvh - 48px); margin: auto; padding: 0; border: 1px solid #dfe7f7; border-radius: 18px; background: #fff; color: #29334f; overflow: hidden; box-shadow: 0 20px 80px #17275040; }
.expanded-map-dialog[open] { display: flex; flex-direction: column; }
.expanded-map-dialog::backdrop { background: #17275080; }
.expanded-map-heading { display: flex; flex: none; justify-content: space-between; align-items: center; gap: 16px; padding: 18px 22px; }
.expanded-map-heading h2 { margin: 0; font-size: 21px; }
.expanded-map-heading p { margin: 6px 0 0; color: #7181a4; font-size: 13px; line-height: 1.5; }
.expanded-map-heading button { flex: none; padding: 8px 16px; border: 1px solid #dce5f7; border-radius: 8px; background: #f5f8ff; color: #38588f; cursor: pointer; }
.expanded-map-heading button:focus-visible { outline: 2px solid #7194f4; outline-offset: 2px; }
.expanded-map-dialog :deep(.map-canvas-shell) { display: flex; flex: 1; flex-direction: column; min-height: 0; border: 0; border-radius: 0; }
.expanded-map-dialog :deep(.map-toolbar) { flex: none; }
.expanded-map-dialog :deep(.mind-map-canvas) { flex: 1; height: auto; min-height: 0; max-height: none; }
@media (max-width: 600px) {
  .expanded-map-dialog { width: calc(100vw - 16px); height: calc(100dvh - 24px); max-height: calc(100dvh - 24px); border-radius: 12px; }
  .expanded-map-heading { padding: 14px; gap: 8px; }
  .expanded-map-heading h2 { font-size: 18px; }
  .expanded-map-heading p { font-size: 12px; }
}
</style>
