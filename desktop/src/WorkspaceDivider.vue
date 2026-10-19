<script setup lang="ts">
import {computed,onMounted,onUnmounted,ref} from 'vue'
const handle=ref<HTMLElement|null>(null),ratio=ref(1.52/2.52),available=ref(1000),dragging=ref(false)
const defaultRatio=1.52/2.52,key='framewise:workspace-split:v1'
let observer:ResizeObserver|null=null,layout:HTMLElement|null=null,pointer:number|null=null
const minimum=computed(()=>Math.max(.25,Math.min(360,available.value*.48)/available.value))
const maximum=computed(()=>Math.min(.75,1-Math.min(360,available.value*.48)/available.value))
function apply(value:number){
  ratio.value=Math.max(minimum.value,Math.min(maximum.value,value))
  layout?.style.setProperty('--workspace-left',`${ratio.value}fr`)
  layout?.style.setProperty('--workspace-right',`${1-ratio.value}fr`)
}
function save(){try{localStorage.setItem(key,String(ratio.value))}catch{/* Resizing still works without storage. */}}
function measure(){
  if(!layout)return
  const style=getComputedStyle(layout)
  available.value=Math.max(1,layout.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight)-parseFloat(style.columnGap))
  apply(ratio.value)
  if(innerWidth<=800)finish()
}
function move(event:PointerEvent){
  if(pointer!==event.pointerId||!layout)return
  const style=getComputedStyle(layout),box=layout.getBoundingClientRect()
  apply((event.clientX-box.left-parseFloat(style.paddingLeft)-parseFloat(style.columnGap)/2)/available.value)
}
function start(event:PointerEvent){
  if(!event.isPrimary||event.button!==0||innerWidth<=800)return
  event.preventDefault();pointer=event.pointerId;dragging.value=true
  handle.value?.focus();handle.value?.setPointerCapture(event.pointerId)
  layout?.classList.add('workspace-resizing')
}
function finish(){
  if(pointer===null)return
  const id=pointer;pointer=null;dragging.value=false
  layout?.classList.remove('workspace-resizing')
  if(handle.value?.hasPointerCapture(id))handle.value.releasePointerCapture(id)
  save()
}
function reset(){apply(defaultRatio);save()}
function keyboard(event:KeyboardEvent){
  const step=event.shiftKey?.05:.02
  if(event.key==='ArrowLeft')apply(ratio.value-step)
  else if(event.key==='ArrowRight')apply(ratio.value+step)
  else if(event.key==='Home')apply(minimum.value)
  else if(event.key==='End')apply(maximum.value)
  else return
  event.preventDefault();save()
}
onMounted(()=>{
  layout=handle.value?.parentElement??null
  try{const stored=localStorage.getItem(key);if(stored!==null){const value=Number(stored);if(Number.isFinite(value)&&value>0&&value<1)ratio.value=value}}catch{/* Keep default layout. */}
  measure();observer=new ResizeObserver(measure);if(layout)observer.observe(layout)
})
onUnmounted(()=>{finish();observer?.disconnect()})
</script>
<template>
  <div ref="handle" class="workspace-divider" :class="{'is-dragging':dragging}" role="separator" tabindex="0" aria-label="调整视频与学习工作台宽度" aria-orientation="vertical" :aria-valuenow="Math.round(ratio*100)" :aria-valuemin="Math.round(minimum*100)" :aria-valuemax="Math.round(maximum*100)" :aria-valuetext="`视频 ${Math.round(ratio*100)}%，学习工作台 ${100-Math.round(ratio*100)}%`" title="左右拖动调整宽度，双击恢复默认；方向键微调" @pointerdown="start" @pointermove="move" @pointerup="finish" @pointercancel="finish" @lostpointercapture="finish" @keydown="keyboard" @dblclick="reset"><span aria-hidden="true"></span></div>
</template>
