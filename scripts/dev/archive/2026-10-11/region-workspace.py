from pathlib import Path
p=Path('E:/workp/videostudy')
app=p/'desktop/src/App.vue'
s=app.read_text(encoding='utf-8').replace("import { normalizeRegion } from './videoRegion'", "import { normalizeIgnoreSetting } from './videoRegionTimeline'").replace("import type { VideoRegion } from './videoRegion'", "import type { IgnoreSetting } from './videoRegionTimeline'").replace('ref<VideoRegion|null>', 'ref<IgnoreSetting|null>').replace('region: VideoRegion|null', 'region: IgnoreSetting|null').replace('normalizeRegion(', 'normalizeIgnoreSetting(')
app.write_text(s,encoding='utf-8')
f=p/'desktop/src/VideoWorkspace.vue'
s=f.read_text(encoding='utf-8'); style=s[s.index('<style scoped>'):]
script='''<script setup lang="ts">
import {ref,computed,watch,onMounted,onBeforeUnmount} from 'vue'
import StudyIcon from './StudyIcon.vue'
import {containedFrame,regionFromPoints} from './videoRegion'
import type {VideoRegion} from './videoRegion'
import {regionAt,regionNodes,upsertRegionNode,removeRegionNode} from './videoRegionTimeline'
import type {IgnoreSetting} from './videoRegionTimeline'
const props=defineProps<{src:string;filename:string;modelValue:IgnoreSetting|null;timeMs:number;checking?:boolean}>()
const emit=defineEmits<{close:[];selectFile:[event:Event];'update:modelValue':[region:IgnoreSetting|null]}>()
const dialog=ref<HTMLDialogElement|null>(null),media=ref<HTMLVideoElement|null>(null),stage=ref<HTMLElement|null>(null)
const surface=ref<HTMLElement|null>(null),width=ref(0),height=ref(0),videoWidth=ref(0),videoHeight=ref(0)
const time=ref(0),duration=ref(0),paused=ref(true),editing=ref(false),dragging=ref(false)
const draft=ref<VideoRegion|null>(regionAt(props.modelValue,props.timeMs))
const error=ref(''),note=ref(''),ready=ref(false)
type Anchor={x:number;y:number;pointerId:number;timeMs:number;mode:'draw'|'move'|'resize';region:VideoRegion|null}
let observer:ResizeObserver|undefined,anchor:Anchor|null=null
const nodes=computed(()=>regionNodes(props.modelValue))
const frame=computed(()=>containedFrame(width.value,height.value,videoWidth.value,videoHeight.value))
const frameStyle=computed(()=>({left:`${frame.value.left}px`,top:`${frame.value.top}px`,width:`${frame.value.width}px`,height:`${frame.value.height}px`}))
const regionStyle=computed(()=>draft.value?{left:`${draft.value.x*100}%`,top:`${draft.value.y*100}%`,width:`${draft.value.width*100}%`,height:`${draft.value.height*100}%`}:{})
const canDraw=computed(()=>ready.value&&videoWidth.value>0&&!props.checking)
const clock=(seconds:number)=>`${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`
const nodeClock=(ms:number)=>clock(ms/1000)+(ms%1000?`.${String(ms%1000).padStart(3,'0')}`:'')
const activeTime=computed(()=>nodes.value.filter(n=>n.timeMs<=Math.round(time.value*1000)).at(-1)?.timeMs)
function refresh(){if(!editing.value&&!anchor)draft.value=regionAt(props.modelValue,Math.round(time.value*1000))}
function sync(){if(media.value){time.value=media.value.currentTime;paused.value=media.value.paused;refresh()}}
function loaded(){
 const v=media.value;if(!v)return
 videoWidth.value=v.videoWidth;videoHeight.value=v.videoHeight;duration.value=Number.isFinite(v.duration)?v.duration:0
 v.currentTime=Math.max(0,Math.min(props.timeMs/1000,duration.value));ready.value=true;sync()
}
function cancelDrawing(){
 const id=anchor?.pointerId;anchor=null;dragging.value=false;editing.value=false
 if(id!==undefined&&surface.value?.hasPointerCapture(id))surface.value.releasePointerCapture(id)
 refresh();error.value='';note.value=''
}
function startDrawing(){media.value?.pause();cancelDrawing();editing.value=true;note.value='拖动框选，松开鼠标自动保存。'}
function point(event:PointerEvent){const box=surface.value!.getBoundingClientRect();return {x:Math.max(0,Math.min(1,(event.clientX-box.left)/box.width)),y:Math.max(0,Math.min(1,(event.clientY-box.top)/box.height))}}
function down(event:PointerEvent){
 if(!canDraw.value||event.button!==0||anchor)return
 const target=event.target as HTMLElement
 const mode=editing.value?'draw':target.closest('[data-resize]')?'resize':target.closest('.workspace-region')?'move':null
 if(!mode)return
 event.preventDefault();media.value?.pause();sync()
 const p=point(event);anchor={...p,pointerId:event.pointerId,timeMs:Math.round(time.value*1000),mode,region:draft.value?{...draft.value}:null}
 dragging.value=true;if(mode==='draw')draft.value=null
 surface.value?.setPointerCapture(event.pointerId)
}
function move(event:PointerEvent){
 if(!anchor||anchor.pointerId!==event.pointerId)return
 const p=point(event),r=anchor.region,dx=p.x-anchor.x,dy=p.y-anchor.y
 if(anchor.mode==='draw')draft.value=regionFromPoints(anchor.x,anchor.y,p.x,p.y)
 else if(r&&anchor.mode==='move')draft.value={...r,x:Math.max(0,Math.min(1-r.width,r.x+dx)),y:Math.max(0,Math.min(1-r.height,r.y+dy))}
 else if(r)draft.value={...r,width:Math.max(0,Math.min(1-r.x,r.width+dx)),height:Math.max(0,Math.min(1-r.y,r.height+dy))}
}
function up(event:PointerEvent){
 if(!anchor||anchor.pointerId!==event.pointerId)return
 move(event);const finished=anchor;anchor=null;dragging.value=false;editing.value=false
 if(surface.value?.hasPointerCapture(event.pointerId))surface.value.releasePointerCapture(event.pointerId)
 if(!draft.value||draft.value.width*frame.value.width<8||draft.value.height*frame.value.height<8){refresh();error.value='框选范围太小，请重新拖动。';return}
 if(draft.value.width*draft.value.height>.95){refresh();error.value='请保留需要分析的课件区域，不要框住整个画面。';return}
 if(JSON.stringify(draft.value)===JSON.stringify(finished.region)){refresh();return}
 try {
  const first=!nodes.value.length
  emit('update:modelValue',upsertRegionNode(props.modelValue,finished.timeMs,draft.value))
  error.value='';note.value=first?'已保存默认区域，应用于整段视频。':`已保存 ${nodeClock(finished.timeMs)} 节点，之后沿用这个位置，直到下一个节点。`
 }catch(e){refresh();error.value=e instanceof Error?e.message:'保存失败，请重新框选。'}
}
function clear(){cancelDrawing();draft.value=null;emit('update:modelValue',null);note.value='已清除全部区域节点。'}
function seek(seconds:number){if(!media.value||dragging.value)return;cancelDrawing();media.value.pause();media.value.currentTime=Math.max(0,Math.min(seconds,duration.value));sync()}
function remove(timeMs:number){cancelDrawing();emit('update:modelValue',removeRegionNode(props.modelValue,timeMs));note.value='已删除节点，这一时段沿用前一个区域。'}
async function toggle(){if(!media.value)return;if(media.value.paused){try{await media.value.play()}catch{error.value='视频暂时无法播放，可尝试主页面的兼容播放。'}}else media.value.pause()}
function close(){media.value?.pause();emit('close')}
watch(()=>props.src,()=>{media.value?.pause();ready.value=false;videoWidth.value=0;videoHeight.value=0;time.value=0;duration.value=0;cancelDrawing()})
watch(()=>props.modelValue,refresh)
onMounted(()=>{
 dialog.value?.showModal()
 observer=new ResizeObserver(entries=>{width.value=entries[0].contentRect.width;height.value=entries[0].contentRect.height})
 if(stage.value)observer.observe(stage.value)
})
onBeforeUnmount(()=>{observer?.disconnect();media.value?.pause();dialog.value?.close()})
</script>
<template>
 <dialog ref="dialog" class="video-workspace" aria-labelledby="workspace-title" @cancel.prevent="close">
  <header class="workspace-header"><div><h2 id="workspace-title">视频工作台</h2><p>{{ filename||'选择视频后，设置画面处理工具' }}</p></div><button type="button" class="workspace-close" aria-label="关闭视频工作台" @click="close">关闭 <span aria-hidden="true">×</span></button></header>
  <div class="workspace-layout">
   <nav class="workspace-nav" aria-label="视频工具"><span>视频工具</span><button type="button" aria-current="page"><StudyIcon name="slides"/>忽略区域</button><p>框选摄像头等区域，设置画面变化检测的排除范围。</p></nav>
   <section class="workspace-preview" aria-label="视频预览">
    <div ref="stage" class="workspace-stage">
     <video v-if="src" ref="media" :src="src" preload="metadata" playsinline @loadedmetadata="loaded" @timeupdate="sync" @seeked="sync" @play="sync" @pause="sync" @ended="sync" @error="error='无法读取视频画面，请在主页面尝试兼容播放。'"/>
     <div v-else class="workspace-empty"><StudyIcon name="play"/><h3>先选择一段视频</h3><p>播放并暂停在摄像头位置清楚的画面，再开始框选。</p><label class="workspace-primary">选择本地视频<input type="file" accept="video/*,audio/*" @change="emit('selectFile',$event)"/></label></div>
     <p v-if="src&&ready&&!videoWidth" class="workspace-audio">当前文件没有视频画面，无法框选。</p>
     <div v-if="canDraw" ref="surface" :style="frameStyle" :class="['workspace-surface',{drawing:editing}]" @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="cancelDrawing">
      <div v-if="draft" class="workspace-region" :style="regionStyle"><span>忽略区域 · 当前时段</span><button type="button" class="workspace-resize" data-resize tabindex="-1" aria-label="拖动调整区域大小"/></div>
     </div>
    </div>
    <div class="workspace-playback"><button type="button" :disabled="!ready||editing||dragging" :aria-label="paused?'播放预览':'暂停预览'" @click="toggle">{{ paused?'播放':'暂停' }}</button><input aria-label="预览进度" type="range" min="0" :max="duration||0" step="0.1" :value="time" :disabled="!ready||editing||dragging" @input="seek(Number(($event.target as HTMLInputElement).value))"/><span>{{ clock(time) }} / {{ clock(duration) }}</span></div>
    <p class="workspace-preview-note">拖动区域可移动位置，拖动右下角可调整大小，松开后自动保存当前时间节点。</p>
   </section>
   <aside class="workspace-settings" aria-labelledby="ignore-title"><span class="workspace-kicker">画面设置</span><h3 id="ignore-title">忽略画面区域</h3><p>首次框选默认应用于整段视频。后续在其他时间框选、移动或缩放，会自动新增节点，之后沿用新位置。</p>
    <div class="workspace-state">{{ checking?'正在确认当前文件…':editing||dragging?'正在调整区域':nodes.length?`已设置 ${nodes.length} 个时间节点`:'未设置忽略区域' }}</div>
    <button class="workspace-primary" type="button" :disabled="!canDraw||dragging" @click="startDrawing">{{ draft?'重新框选':'开始框选' }}</button>
    <button v-if="editing" class="workspace-secondary" type="button" @click="cancelDrawing">取消框选</button>
    <button class="workspace-secondary" type="button" :disabled="!modelValue||dragging" @click="clear">清除全部节点</button>
    <div v-if="nodes.length" class="workspace-nodes" aria-label="区域时间节点"><strong>区域时间节点</strong><div v-for="node in nodes" :key="node.timeMs" :class="['workspace-node',{active:node.timeMs===activeTime}]"><button type="button" :disabled="!ready||dragging" :aria-label="`跳到区域节点 ${nodeClock(node.timeMs)}`" @click="seek(node.timeMs/1000)">{{ nodeClock(node.timeMs) }} <span>{{ node.timeMs===0?'默认区域':node.region?'新位置':'暂停忽略' }}</span></button><button v-if="node.timeMs!==0" type="button" :disabled="dragging" :aria-label="`删除区域节点 ${nodeClock(node.timeMs)}`" @click="remove(node.timeMs)">×</button></div></div>
    <p v-if="note" class="workspace-note" role="status">{{ note }}</p><p v-if="error" class="workspace-error" role="alert">{{ error }}</p>
    <div class="workspace-scope"><strong>应用于新分析</strong><p>新分析按时间节点忽略区域的画面变化。已有任务及重试沿用原设置；截图和 OCR 原始记录完整保留。</p></div>
   </aside>
  </div>
 </dialog>
</template>
'''
style=style.replace('.workspace-surface{position:absolute;pointer-events:none}', '.workspace-surface{position:absolute;touch-action:none;pointer-events:auto}').replace('background:#537dee50;pointer-events:none','background:#537dee50;cursor:move;touch-action:none').replace('.workspace-region span{position:absolute;', '.workspace-region span{pointer-events:none;position:absolute;')
style=style.replace('@media(max-width:1000px)', '.workspace-resize{position:absolute;right:-6px;bottom:-6px;width:15px;height:15px;border:2px solid white;border-radius:3px;background:#4166ed;cursor:nwse-resize;padding:0}.workspace-nodes{grid-column:1/-1;min-width:0;margin-top:20px;font-size:12px}.workspace-nodes>strong{color:#6f809b}.workspace-node{display:flex;margin-top:8px;border:1px solid #e4eaf4;border-radius:7px;overflow:hidden}.workspace-node.active{border-color:#9bb4ff;background:#eef3ff}.workspace-node button{border:0;background:transparent;padding:9px;color:#3f608f}.workspace-node button:first-child{flex:1;text-align:left;min-width:0}.workspace-node span{color:#8493ab;margin-left:6px}.workspace-node button:last-child:not(:first-child){font-size:18px}\n@media(max-width:1000px)')
f.write_text(script+style,encoding='utf-8')
j=p/'backend-java/src/main/java/cn/videostudy/api/IgnoreRegion.java'
s=j.read_text(encoding='utf-8').replace('nodes.size()>200||nodes.getFirst().timeMs()!=0','nodes.size()>200||nodes.getFirst()==null||nodes.getFirst().timeMs()!=0')
j.write_text(s,encoding='utf-8')
