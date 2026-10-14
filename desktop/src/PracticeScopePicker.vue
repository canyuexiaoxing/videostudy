<script setup lang="ts">
import {computed,ref,watch,onMounted,onBeforeUnmount} from 'vue'
import PracticeScopeBranch from './PracticeScopeBranch.vue'
import {practiceScopeTree,type ScopeNode} from './practiceScope'
const props=defineProps<{root?:ScopeNode|null;modelValue:string;disabled?:boolean}>()
const emit=defineEmits<{'update:modelValue':[id:string]}>()
const panel=ref<HTMLDetailsElement|null>(null)
const tree=computed(()=>practiceScopeTree(props.root))
function find(nodes:ScopeNode[],id:string):ScopeNode|undefined{for(const node of nodes){if(node.id===id)return node;const child=find(node.children??[],id);if(child)return child}}
const title=computed(()=>find(tree.value,props.modelValue)?.title??'整课范围 · 随机出题')
function select(id:string){emit('update:modelValue',id);if(panel.value)panel.value.open=false}
function outside(event:PointerEvent){if(panel.value&&!panel.value.contains(event.target as Node))panel.value.open=false}
onMounted(()=>document.addEventListener('pointerdown',outside))
onBeforeUnmount(()=>document.removeEventListener('pointerdown',outside))
watch(()=>props.disabled,value=>{if(value&&panel.value)panel.value.open=false})
</script>
<template>
 <div class="scope-picker"><span class="scope-label">练习范围</span>
  <details ref="panel" class="scope-menu" @keydown.esc="panel&&(panel.open=false)">
   <summary :aria-disabled="disabled" @click="disabled&&$event.preventDefault()"><span>{{ title }}</span><span aria-hidden="true">⌄</span></summary>
   <div class="scope-panel" role="group" aria-label="选择练习范围">
    <p>选整课随机练习，或选择模块及子范围</p>
    <button class="scope-all" type="button" :aria-pressed="!modelValue" :disabled="disabled" @click="select('')"><span aria-hidden="true">{{ !modelValue?'✓':'○' }}</span>整课范围 · 随机出题</button>
    <PracticeScopeBranch v-for="node in tree" :key="node.id" :node="node" :selected="modelValue" :disabled="disabled" @select="select"/>
   </div>
  </details>
 </div>
</template>
<style scoped>
.scope-picker{display:grid;align-content:start;gap:7px;min-width:0}.scope-label{font-size:12px;color:#53698f}.scope-menu{min-width:0;position:relative}.scope-menu summary{display:flex;align-items:center;justify-content:space-between;gap:8px;list-style:none;padding:10px;border:1px solid #dce4f7;border-radius:8px;background:#fff;color:#25395f;font-size:13px;line-height:1.5;cursor:pointer}.scope-menu summary::-webkit-details-marker{display:none}.scope-menu summary>span:first-child{overflow-wrap:anywhere}.scope-menu summary[aria-disabled=true]{opacity:.5;cursor:default}.scope-menu summary:focus-visible{outline:2px solid #4166ed;outline-offset:2px}.scope-menu[open] summary{border-color:#92aaf4}.scope-panel{position:absolute;top:100%;left:0;z-index:12;width:min(360px,calc(100vw - 64px));min-width:100%;box-sizing:border-box;box-shadow:0 10px 30px #25395f24;max-height:320px;overflow:auto;margin-top:6px;padding:7px 0;border:1px solid #cfdcf7;border-radius:10px;background:white}.scope-panel p{margin:4px 12px 8px;font-size:11px;line-height:1.7;color:#7183a2}.scope-all{display:flex;gap:9px;align-items:center;width:calc(100% - 16px);margin:0 8px 5px;padding:10px 7px;border:0;border-radius:7px;background:transparent;color:#304568;text-align:left;font:inherit;font-size:13px;cursor:pointer}.scope-all[aria-pressed=true]{background:#edf2ff;color:#315cde;font-weight:650}.scope-all span{width:17px;text-align:center}.scope-all:focus-visible{outline:2px solid #4166ed;outline-offset:1px}
</style>
