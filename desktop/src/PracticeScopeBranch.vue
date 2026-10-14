<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ScopeNode } from './practiceScope'
const props=defineProps<{node:ScopeNode;selected:string;disabled?:boolean;depth?:number}>()
const emit=defineEmits<{select:[id:string]}>()
const expanded=ref(false)
function contains(node:ScopeNode,id:string):boolean{return node.id===id||!!node.children?.some(child=>contains(child,id))}
watch(()=>props.selected,id=>{if(id!==props.node.id&&contains(props.node,id))expanded.value=true},{immediate:true})
</script>
<template>
 <div class="scope-branch">
  <div class="scope-row" :style="{paddingLeft:`${8+(depth??0)*16}px`}">
   <button class="scope-choice" type="button" :aria-pressed="selected===node.id" :disabled="disabled" @click="emit('select',node.id)"><span class="scope-dot" aria-hidden="true">{{ selected===node.id?'✓':'' }}</span><span>{{ node.title }}</span></button>
   <button v-if="node.children?.length" class="scope-expand" type="button" :aria-label="`${expanded?'收起':'展开'}${node.title}`" :aria-expanded="expanded" :disabled="disabled" @click="expanded=!expanded">{{ expanded?'收起':'展开' }} <span aria-hidden="true">{{ expanded?'⌃':'⌄' }}</span></button>
  </div>
  <template v-if="expanded"><PracticeScopeBranch v-for="child in node.children" :key="child.id" :node="child" :selected="selected" :disabled="disabled" :depth="(depth??0)+1" @select="emit('select',$event)"/></template>
 </div>
</template>
<style scoped>
.scope-row{display:flex;align-items:center;gap:6px;padding:4px 8px}.scope-choice{display:flex;align-items:center;gap:9px;flex:1;min-width:0;padding:9px 6px;border:0;border-radius:7px;background:transparent;color:#304568;text-align:left;font:inherit;font-size:13px;line-height:1.6;cursor:pointer}.scope-choice>span:last-child{overflow-wrap:anywhere}.scope-choice:hover{background:#f0f4ff}.scope-choice[aria-pressed=true]{background:#edf2ff;color:#315cde;font-weight:650}.scope-dot{display:grid;place-items:center;flex:none;width:17px;height:17px;border:1px solid #c9d5ed;border-radius:50%;background:#fff;font-size:11px}.scope-choice[aria-pressed=true] .scope-dot{background:#4166ed;border-color:#4166ed;color:#fff}.scope-expand{flex:none;padding:7px 8px;border:0;border-radius:6px;background:#f0f4ff;color:#4763ab;font:inherit;font-size:11px;cursor:pointer}.scope-expand:hover{background:#e1e9ff}button:focus-visible{outline:2px solid #4166ed;outline-offset:1px}button:disabled{opacity:.5;cursor:default}
</style>
