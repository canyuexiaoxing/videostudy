<script setup lang="ts">
import { API_ORIGIN } from './apiOrigin' 
import {ref,computed,watch,onMounted,onBeforeUnmount} from 'vue'
import StudyIcon from './StudyIcon.vue'
import type {PersonSelectionMode} from './personSelection'
import {containedFrame,regionFromPoints} from './videoRegion'
import type {VideoRegion} from './videoRegion'
import {validateRegionCombination,regionAt,regionNodes,upsertRegionNode,removeRegionNode} from './videoRegionTimeline'
import type {IgnoreSetting} from './videoRegionTimeline'
import {scanRegions,currentRegionCandidate} from './autoRegionScan'
import type {ScanResult} from './autoRegionScan'
import {createRegionCapture} from './regionCapture'
const props=defineProps<{src:string;filename:string;modelValue:IgnoreSetting|null;analysisRegion:IgnoreSetting|null;timeMs:number;checking?:boolean;personSelectionMode?:PersonSelectionMode;analysisPending?:boolean}>()
const emit=defineEmits<{close:[];selectFile:[event:Event];'update:modelValue':[region:IgnoreSetting|null];'update:analysisRegion':[region:IgnoreSetting|null];'update:personSelectionMode':[mode:PersonSelectionMode]}>()
const dialog=ref<HTMLDialogElement|null>(null),media=ref<HTMLVideoElement|null>(null),stage=ref<HTMLElement|null>(null)
const surface=ref<HTMLElement|null>(null),width=ref(0),height=ref(0),videoWidth=ref(0),videoHeight=ref(0)
const time=ref(0),duration=ref(0),paused=ref(true),editing=ref(false),dragging=ref(false)
const draft=ref<VideoRegion|null>(regionAt(props.modelValue,props.timeMs))
const error=ref(''),note=ref(''),ready=ref(false)
type Anchor={x:number;y:number;pointerId:number;timeMs:number;mode:'draw'|'move'|'resize';region:VideoRegion|null}
let observer:ResizeObserver|undefined,anchor:Anchor|null=null
const scanMode=ref<'full'|'current'>('full')
const scanBusy=ref(false),scanCount=ref(0),candidate=ref<ScanResult|null>(null),editingCandidate=ref(false)
let scanController:AbortController|null=null
const areaMode=ref<'ignore'|'analysis'|'person'>('ignore')
const selectedSetting=computed(()=>areaMode.value==='analysis'?props.analysisRegion:props.modelValue)
const displaySetting=computed(()=>candidate.value?.setting??selectedSetting.value)
const nodes=computed(()=>regionNodes(displaySetting.value))
const frame=computed(()=>containedFrame(width.value,height.value,videoWidth.value,videoHeight.value))
const frameStyle=computed(()=>({left:`${frame.value.left}px`,top:`${frame.value.top}px`,width:`${frame.value.width}px`,height:`${frame.value.height}px`}))
const personAnalysisRegion=computed(()=>regionAt(props.analysisRegion,Math.round(time.value*1000)))
const personIgnoredRegion=computed(()=>regionAt(props.modelValue,Math.round(time.value*1000)))
function savedRegionStyle(region:VideoRegion){return {left:`${region.x*100}%`,top:`${region.y*100}%`,width:`${region.width*100}%`,height:`${region.height*100}%`}}
const otherRegion=computed(()=>regionAt(areaMode.value==='analysis'?props.modelValue:props.analysisRegion,Math.round(time.value*1000)))
const otherStyle=computed(()=>otherRegion.value?{left:`${otherRegion.value.x*100}%`,top:`${otherRegion.value.y*100}%`,width:`${otherRegion.value.width*100}%`,height:`${otherRegion.value.height*100}%`}:{})
const overlapNote=computed(()=>{
 const a=areaMode.value==='analysis'?draft.value:otherRegion.value,b=areaMode.value==='ignore'?draft.value:otherRegion.value
 if(!a||!b)return ''
 if(b.x+b.width<=a.x||a.x+a.width<=b.x||b.y+b.height<=a.y||a.y+a.height<=b.y)return '忽略区域位于分析范围外，当前不生效。'
 return '只分析绿色框内内容，并排除与蓝色框重叠的部分。'
})
function commitRegion(value:IgnoreSetting|null){
 try{validateRegionCombination(areaMode.value==='analysis'?value:props.analysisRegion,areaMode.value==='ignore'?value:props.modelValue)}
 catch(e){refresh();error.value=e instanceof Error?e.message:'区域设置冲突';return false}
 if(candidate.value&&editingCandidate.value){candidate.value={...candidate.value,setting:{nodes:regionNodes(value)}};return true}
 if(areaMode.value==='analysis')emit('update:analysisRegion',value);else emit('update:modelValue',value)
 return true
}
function selectMode(mode:'ignore'|'analysis'|'person'){if(scanBusy.value||candidate.value)return;cancelDrawing();areaMode.value=mode;refresh()}
const regionStyle=computed(()=>draft.value?{left:`${draft.value.x*100}%`,top:`${draft.value.y*100}%`,width:`${draft.value.width*100}%`,height:`${draft.value.height*100}%`}:{})
const canDraw=computed(()=>areaMode.value!=='person'&&ready.value&&videoWidth.value>0&&!props.checking&&!scanBusy.value)
const clock=(seconds:number)=>`${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`
const nodeClock=(ms:number)=>clock(ms/1000)+(ms%1000?`.${String(ms%1000).padStart(3,'0')}`:'')
const activeTime=computed(()=>nodes.value.filter(n=>n.timeMs<=Math.round(time.value*1000)).at(-1)?.timeMs)
function refresh(){if(!editing.value&&!anchor)draft.value=regionAt(displaySetting.value,Math.round(time.value*1000))}
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
 if(!canDraw.value||(candidate.value&&!editingCandidate.value)||event.button!==0||anchor)return
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
 if(areaMode.value==='ignore'&&draft.value.width*draft.value.height>.95){refresh();error.value='请保留需要分析的课件区域，不要框住整个画面。';return}
 if(JSON.stringify(draft.value)===JSON.stringify(finished.region)){refresh();return}
 try {
  const first=!nodes.value.length
  const a=areaMode.value==='analysis'?draft.value:regionAt(props.analysisRegion,finished.timeMs),b=areaMode.value==='ignore'?draft.value:regionAt(props.modelValue,finished.timeMs)
  if(a&&b&&b.x<=a.x&&b.y<=a.y&&b.x+b.width>=a.x+a.width&&b.y+b.height>=a.y+a.height)throw new Error('忽略框覆盖了整个分析区域，请保留需要分析的内容')
  const saveTime=candidate.value&&editingCandidate.value?(activeTime.value??0):finished.timeMs
  if(!commitRegion(upsertRegionNode(candidate.value&&editingCandidate.value?displaySetting.value:selectedSetting.value,saveTime,draft.value,areaMode.value==='analysis')))return
  error.value='';note.value=candidate.value&&editingCandidate.value?'已调整当前候选节点，点击应用后生效。':first?'已保存默认区域，应用于整段视频。':`已保存 ${nodeClock(finished.timeMs)} 节点，之后沿用这个位置，直到下一个节点。`
 }catch(e){refresh();error.value=e instanceof Error?e.message:'保存失败，请重新框选。'}
}
function clear(){cancelDrawing();draft.value=null;if(!commitRegion(null))return;note.value=areaMode.value==='analysis'?'已清除分析范围，恢复完整画面。':'已清除忽略区域节点。'}
function seek(seconds:number){if(!media.value||dragging.value)return;cancelDrawing();media.value.pause();media.value.currentTime=Math.max(0,Math.min(seconds,duration.value));sync()}
function remove(timeMs:number){cancelDrawing();if(!commitRegion(removeRegionNode(selectedSetting.value,timeMs)))return;note.value='已删除节点，这一时段沿用前一个区域。'}
async function toggle(){if(!media.value)return;if(media.value.paused){try{await media.value.play()}catch{error.value='视频暂时无法播放，可尝试主页面的兼容播放。'}}else media.value.pause()}
function stopScan(){scanController?.abort();scanController=null;scanBusy.value=false}
function adjustCandidate(){editingCandidate.value=true;note.value='拖动候选框或右下角调整大小；也可重新框选。点击应用后才保存。'}
function discardCandidate(){editingCandidate.value=false;candidate.value=null;refresh();note.value='已保留原有设置。'}
function applyCandidate(){if(!candidate.value)return;const value=candidate.value.setting;try{validateRegionCombination(props.analysisRegion,value)}catch(e){error.value=e instanceof Error?e.message:'区域设置冲突';return}editingCandidate.value=false;candidate.value=null;emit('update:modelValue',value);note.value='已应用自动识别的时间节点，可继续手动调整。';refresh()}
async function autoScan(mode:'full'|'current'='full'){
 if(!canDraw.value||!duration.value)return
 media.value?.pause();sync();cancelDrawing();editingCandidate.value=false;candidate.value=null;error.value='';note.value='';scanCount.value=0;scanMode.value=mode
 const capturedTime=Math.round(time.value*1000)
 const controller=new AbortController();scanController=controller;scanBusy.value=true
 let decoder:Awaited<ReturnType<typeof createRegionCapture>>|undefined
 try{
  decoder=await createRegionCapture(props.src,controller.signal)
  const detect=async (times:number[])=>{
   const frames=[];for(const t of times)frames.push(await decoder!.capture(t))
   const response=await fetch(API_ORIGIN + '/api/video-region-detections',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({frames}),signal:AbortSignal.any([controller.signal,AbortSignal.timeout(65000)])})
   if(!response.ok)throw new Error(response.status===429?'识别服务繁忙，请稍后重试':response.status===422||response.status===400?'截图无法识别，请尝试兼容播放':'AI 自动识别暂时不可用，请检查模型配置或使用手动框选')
   const data=await response.json();return data.detections
  }
  let result:ScanResult
  if(mode==='current'){
   const detections=await detect([capturedTime])
   if(controller.signal.aborted||scanController!==controller)return
   if(!Array.isArray(detections)||detections.length!==1||detections[0]?.timeMs!==capturedTime)throw new Error('识别结果与当前画面不匹配')
   result=currentRegionCandidate(props.modelValue,detections[0]);scanCount.value=1
  }else result=await scanRegions(Math.round(duration.value*1000),detect,{signal:controller.signal,onProgress:count=>{if(!controller.signal.aborted)scanCount.value=count}})
  if(scanController!==controller||controller.signal.aborted)return
  candidate.value=result;editingCandidate.value=false;refresh();note.value=mode==='current'?`已识别 ${nodeClock(capturedTime)} 的画面，请预览后应用。`:`识别完成，共检查 ${result.samples.length} 张画面。请预览后应用。`
 }catch(e){if(!controller.signal.aborted&&scanController===controller)error.value=e instanceof Error?e.message:'自动识别失败，请手动框选'}
 finally{decoder?.dispose();if(scanController===controller){scanController=null;scanBusy.value=false}}
}
function close(){stopScan();media.value?.pause();emit('close')}
watch(()=>props.src,()=>{stopScan();candidate.value=null;media.value?.pause();ready.value=false;videoWidth.value=0;videoHeight.value=0;time.value=0;duration.value=0;cancelDrawing()})
watch(()=>[props.modelValue,props.analysisRegion],()=>{editingCandidate.value=false;candidate.value=null;refresh()})
onMounted(()=>{
 dialog.value?.showModal()
 observer=new ResizeObserver(entries=>{width.value=entries[0].contentRect.width;height.value=entries[0].contentRect.height})
 if(stage.value)observer.observe(stage.value)
})
onBeforeUnmount(()=>{stopScan();observer?.disconnect();media.value?.pause();dialog.value?.close()})
</script>
<template>
 <dialog ref="dialog" class="video-workspace" aria-labelledby="workspace-title" @cancel.prevent="close">
  <header class="workspace-header"><div><h2 id="workspace-title">视频工作台</h2><p>{{ filename||'选择视频后，设置画面处理工具' }}</p></div><button type="button" class="workspace-close" aria-label="关闭视频工作台" @click="close">关闭 <span aria-hidden="true">×</span></button></header>
  <div class="workspace-layout">
   <nav class="workspace-nav" aria-label="视频工具"><span>视频工具</span><button type="button" :aria-current="areaMode==='analysis'?'page':undefined" :disabled="scanBusy||!!candidate" @click="selectMode('analysis')"><StudyIcon name="slides"/>分析区域</button><button type="button" :aria-current="areaMode==='ignore'?'page':undefined" :disabled="scanBusy||!!candidate" @click="selectMode('ignore')"><StudyIcon name="slides"/>忽略区域</button><button type="button" :aria-current="areaMode==='person'?'page':undefined" :disabled="scanBusy||!!candidate" @click="selectMode('person')"><StudyIcon name="slides"/>人物过滤<span v-if="personSelectionMode==='adjacent'" class="person-nav-dot" aria-hidden="true"></span></button><p>区域框选与人物过滤可以配合使用。</p></nav>
   <section class="workspace-preview" aria-label="视频预览">
    <div ref="stage" class="workspace-stage">
     <video v-if="src" ref="media" :src="src" preload="metadata" playsinline @loadedmetadata="loaded" @timeupdate="sync" @seeked="sync" @play="sync" @pause="sync" @ended="sync" @error="error='无法读取视频画面，请在主页面尝试兼容播放。'"/>
     <div v-else class="workspace-empty"><StudyIcon name="play"/><h3>先选择一段视频</h3><p>播放并暂停在摄像头位置清楚的画面，再开始框选。</p><label class="workspace-primary">选择本地视频<input type="file" accept="video/*,audio/*" @change="emit('selectFile',$event)"/></label></div>
     <p v-if="src&&ready&&!videoWidth" class="workspace-audio">当前文件没有视频画面，无法框选。</p>
     <div v-if="canDraw" ref="surface" :style="frameStyle" :class="['workspace-surface',{drawing:editing}]" @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="cancelDrawing">
      <div v-if="otherRegion" :class="['workspace-region','workspace-other',{analysis:areaMode==='ignore'}]" :style="otherStyle"><span>{{ areaMode==='ignore'?'分析区域':'忽略区域' }}</span></div>
      <div v-if="draft" :class="['workspace-region',{analysis:areaMode==='analysis'}]" :style="regionStyle"><span>{{ areaMode==='analysis'?'分析区域':'忽略区域' }} · 当前时段</span><button type="button" class="workspace-resize" data-resize tabindex="-1" aria-label="拖动调整区域大小"/></div>
     </div>
     <div v-if="areaMode==='person'&&ready&&videoWidth>0" class="workspace-region-overlays" :style="frameStyle" aria-label="已保存的画面区域">
      <div v-if="personAnalysisRegion" class="workspace-region workspace-other analysis" data-readonly-region="analysis" :style="savedRegionStyle(personAnalysisRegion)"><span>分析区域 · 已保存</span></div>
      <div v-if="personIgnoredRegion" class="workspace-region workspace-other" data-readonly-region="ignore" :style="savedRegionStyle(personIgnoredRegion)"><span>忽略区域 · 已保存</span></div>
     </div>
    </div>
    <div class="workspace-playback"><button type="button" :disabled="!ready||editing||dragging" :aria-label="paused?'播放预览':'暂停预览'" @click="toggle">{{ paused?'播放':'暂停' }}</button><input aria-label="预览进度" type="range" min="0" :max="duration||0" step="0.1" :value="time" :disabled="!ready||editing||dragging" @input="seek(Number(($event.target as HTMLInputElement).value))"/><span>{{ clock(time) }} / {{ clock(duration) }}</span></div>
    <p class="workspace-preview-note">{{ areaMode==='person'?'绿色框为分析区域，蓝色框为忽略区域，随时间节点更新。此处仅预览，请切换对应工具调整；人物过滤在开始分析后执行。':'拖动区域可移动位置，拖动右下角可调整大小，松开后自动保存当前时间节点。' }}</p>
   </section>
   <aside v-if="areaMode==='person'" class="workspace-settings workspace-person" aria-labelledby="person-title">
    <span class="workspace-kicker">自动画面处理</span><h3 id="person-title">人物干扰过滤</h3>
    <p>适合老师在黑板前走动的课程，减少人物动作造成的重复截图。</p>
    <div class="person-filter-card" :class="{enabled:personSelectionMode==='adjacent'}">
     <div class="person-filter-heading"><div><strong>排除人物动作</strong><span>GPU 处理</span></div><button type="button" class="person-switch" role="switch" :aria-checked="personSelectionMode==='adjacent'" aria-label="排除人物动作" :disabled="!src||checking" @click="emit('update:personSelectionMode',personSelectionMode==='adjacent'?'off':'adjacent')"><span></span></button></div>
     <p class="person-filter-status" role="status">{{ personSelectionMode==='adjacent'?'已开启 · 应用于下一次新分析':'已关闭 · 使用普通画面筛选' }}</p>
    </div>
    <ul class="person-filter-facts"><li>只比较前后画面中，都没有被人物挡住的区域。</li><li>原始截图完整保留，后续照常识别文字、检查覆盖与补录。</li><li>教鞭、笔和字幕等非人物变化仍可能保留。</li></ul>
    <p class="workspace-person-device">需要本机 GPU 与人物模型就绪；不可用时回退普通筛选并记录原因。</p>
    <div class="workspace-scope"><strong>按视频保存，仅影响新分析</strong><p>{{ analysisPending?'当前任务继续沿用启动时的设置。此次修改在下一次新分析时使用。':'设置自动保存。已有任务和失败重试沿用各自原设置。' }}</p></div>
   </aside>
   <aside v-else class="workspace-settings" aria-labelledby="ignore-title"><span class="workspace-kicker">画面设置</span><h3 id="ignore-title">{{ areaMode==='analysis'?'只分析框内内容':'忽略画面区域' }}</h3><p>首次框选默认应用于整段视频。后续在其他时间框选、移动或缩放，会自动新增节点，之后沿用新位置。</p>
    <div class="workspace-state">{{ scanBusy?(scanMode==='current'?'正在识别当前画面…':`正在扫描 · 已识别 ${scanCount} 张`):candidate?'自动识别结果 · 尚未应用':checking?'正在确认当前文件…':editing||dragging?'正在调整区域':nodes.length?`已设置 ${nodes.length} 个时间节点`:'未设置忽略区域' }}</div>
    <button v-if="!scanBusy&&areaMode==='ignore'" class="workspace-primary" type="button" :disabled="!canDraw||dragging||!!candidate" @click="autoScan('full')">AI 扫描全片</button>
    <button v-else-if="scanBusy" class="workspace-secondary" type="button" @click="stopScan">{{ scanMode==='current'?'取消识别':'取消扫描' }}</button>
    <button v-if="!scanBusy&&areaMode==='ignore'" class="workspace-secondary" type="button" :disabled="!canDraw||dragging||!!candidate" @click="autoScan('current')">AI 识别当前区域</button>
    <p v-if="areaMode==='ignore'" class="workspace-auto-hint">当前区域只识别这一帧；全片扫描从 4 张画面开始递归，时间粒度约 30 秒，小幅定位抖动会合并。截图会发送至当前配置的 AI 服务。</p>
    <div v-if="candidate" class="workspace-candidate"><strong>{{ scanMode==='current'?'当前画面候选区域':'候选结果' }}</strong><p>{{ candidate.setting.nodes.length }} 个区域节点 · {{ candidate.samples.length }} 张检测画面</p><p v-if="candidate.unresolved.length" class="workspace-error">{{ candidate.unresolved.length }} 个区间无法确定，暂不忽略：{{ candidate.unresolved.map(r=>`${nodeClock(r.startMs)}—${nodeClock(r.endMs)}`).join('、') }}。请人工检查。</p><p v-else-if="scanMode==='current'">{{ modelValue?`应用后从 ${nodeClock(candidate.samples[0]!.timeMs)} 开始使用，已有后续节点保留。`:'首次应用默认覆盖整段视频。' }}请检查是否覆盖课件。</p><p v-else>请检查是否覆盖课件。相同采样位置之间的短暂移动可能漏检。</p><button type="button" class="workspace-primary" :disabled="dragging" @click="applyCandidate">{{ scanMode==='current'?'应用当前区域':'应用自动框选' }}</button><p v-if="candidate.samples.some(s=>s.precision==='estimated')" class="workspace-error">部分边界仅为模型估计，请检查并手动调整。</p><button type="button" class="workspace-secondary" :disabled="dragging" @click="adjustCandidate">手动调整候选框</button><button type="button" class="workspace-secondary" :disabled="dragging" @click="discardCandidate">放弃结果，保留原设置</button></div>
    <button class="workspace-primary" type="button" :disabled="!canDraw||dragging||(!!candidate&&!editingCandidate)" @click="startDrawing">{{ draft?'重新框选':'开始框选' }}</button>
    <button v-if="editing" class="workspace-secondary" type="button" @click="cancelDrawing">取消框选</button>
    <button class="workspace-secondary" type="button" :disabled="!selectedSetting||dragging||scanBusy||!!candidate" @click="clear">{{ areaMode==='analysis'?'清除分析范围':'清除全部节点' }}</button>
    <div v-if="nodes.length" class="workspace-nodes" aria-label="区域时间节点"><strong>{{ candidate?'候选时间节点 · 未应用':areaMode==='analysis'?'分析区域时间节点':'忽略区域时间节点' }}</strong><div v-for="node in nodes" :key="node.timeMs" :class="['workspace-node',{active:node.timeMs===activeTime}]"><button type="button" :disabled="!ready||dragging||scanBusy" :aria-label="`跳到区域节点 ${nodeClock(node.timeMs)}`" @click="seek(node.timeMs/1000)">{{ nodeClock(node.timeMs) }} <span>{{ !node.region?(areaMode==='analysis'?'完整画面':'暂停忽略'):node.timeMs===0?'默认区域':'新位置' }}</span></button><button v-if="node.timeMs!==0" type="button" :disabled="dragging||scanBusy||!!candidate" :aria-label="`删除区域节点 ${nodeClock(node.timeMs)}`" @click="remove(node.timeMs)">×</button></div></div>
    <p v-if="overlapNote" class="workspace-note" role="status">{{ overlapNote }}</p><p v-if="note" class="workspace-note" role="status">{{ note }}</p><p v-if="error" class="workspace-error" role="alert">{{ error }}</p>
    <div class="workspace-scope"><strong>应用于新分析</strong><p>新分析只处理分析框内、忽略框外的画面内容。没有分析框时使用全画面。已有任务及重试沿用原设置；截图和 OCR 原始记录完整保留。</p></div>
   </aside>
  </div>
 </dialog>
</template>
<style scoped>
.video-workspace{box-sizing:border-box;width:min(1400px,96vw);max-width:none;max-height:94dvh;margin:auto;padding:0;border:1px solid #e1e8f6;border-radius:18px;background:#f7f9fd;color:#273754;box-shadow:0 28px 100px #0b1b4540;overflow:auto}.video-workspace::backdrop{background:#142342a6;backdrop-filter:blur(4px)}.workspace-header{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:22px 26px;background:#fff;border-bottom:1px solid #e4eaf4}.workspace-header h2{margin:0;font-size:21px}.workspace-header p{margin:7px 0 0;color:#7182a0;font-size:12px;overflow-wrap:anywhere}.workspace-close{border:1px solid #dce4f2;background:#fff;border-radius:8px;padding:9px 14px;color:#536582;white-space:nowrap}.workspace-close span{margin-left:8px;font-size:19px}.workspace-layout{display:grid;grid-template-columns:165px minmax(0,1fr) 250px;min-height:500px}.workspace-nav{padding:22px 14px;border-right:1px solid #e4eaf4;background:#fff}.workspace-nav>span,.workspace-kicker{font-size:11px;letter-spacing:.08em;color:#8290aa}.workspace-nav button{display:flex;align-items:center;gap:9px;width:100%;margin-top:15px;padding:12px 10px;border:1px solid #cbd9ff;border-radius:9px;color:#315dec;background:#eef3ff;text-align:left;font-weight:600}.workspace-nav svg{width:17px;height:17px}.workspace-nav p{margin:17px 4px;color:#8190a8;font-size:11px;line-height:1.9}.workspace-preview{min-width:0;padding:24px 20px}.workspace-stage{position:relative;aspect-ratio:16/9;background:#10192b;border-radius:12px;overflow:hidden}.workspace-stage video{display:block;width:100%;height:100%;object-fit:contain}.workspace-surface{position:absolute;touch-action:none;pointer-events:auto}.workspace-surface.drawing{pointer-events:auto;touch-action:none;cursor:crosshair}.workspace-region{position:absolute;box-sizing:border-box;border:2px solid #84a8ff;background:#537dee50;cursor:move;touch-action:none}.workspace-region span{pointer-events:none;position:absolute;top:5px;left:5px;padding:3px 6px;border-radius:4px;background:#20396de6;color:white;font-size:10px;white-space:nowrap}.workspace-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;padding:16px;box-sizing:border-box;color:#dbe5ff;text-align:center}.workspace-empty svg{width:34px;height:34px;color:#a8bfff}.workspace-empty h3{margin:12px 0 0;font-size:17px}.workspace-empty p{font-size:12px;color:#9fafcb;line-height:1.7}.workspace-empty label{margin-top:8px;cursor:pointer}.workspace-empty input{display:none}.workspace-playback{display:flex;align-items:center;gap:12px;margin-top:14px}.workspace-playback button{border:1px solid #d8e2f3;background:#fff;padding:7px 12px;border-radius:7px;color:#3c557a;white-space:nowrap}.workspace-playback input{min-width:0;flex:1;accent-color:#4166ed}.workspace-playback span{font-size:11px;color:#6f809c;white-space:nowrap}.workspace-preview-note{font-size:12px;color:#7283a1;line-height:1.8}.workspace-settings{padding:24px 20px;background:#fff;border-left:1px solid #e4eaf4}.workspace-settings h3{font-size:17px;margin:12px 0}.workspace-settings>p{font-size:12px;color:#73829a;line-height:1.9}.workspace-state{margin:20px 0 12px;padding:11px 12px;border:1px solid #e4eaf4;border-radius:8px;background:#f7f9fd;font-size:12px;color:#5d7396}.workspace-primary,.workspace-secondary{box-sizing:border-box;display:block;width:100%;padding:11px 14px;margin-top:9px;border-radius:8px;font:inherit;font-size:12px;text-align:center}.workspace-primary{border:1px solid #4166ed;color:#fff;background:#4166ed}.workspace-secondary{border:1px solid #dce4f2;color:#5d7293;background:#fff}.workspace-scope{margin-top:26px;padding-top:18px;border-top:1px solid #e8edf5;font-size:11px;color:#8795aa;line-height:1.8}.workspace-scope strong{color:#6f809b}.workspace-scope p{margin:6px 0}.workspace-settings .workspace-note{color:#375dba}.workspace-settings .workspace-error{color:#b24f61}.workspace-audio{position:absolute;inset:40% 10%;color:#c9d6ec;text-align:center;font-size:13px}button,label{cursor:pointer}button:disabled{opacity:.45;cursor:default}button:focus-visible,input:focus-visible,label:focus-within{outline:2px solid #6f99ff;outline-offset:3px}
.workspace-resize{position:absolute;right:-6px;bottom:-6px;width:15px;height:15px;border:2px solid white;border-radius:3px;background:#4166ed;cursor:nwse-resize;padding:0}.workspace-nodes{grid-column:1/-1;min-width:0;margin-top:20px;font-size:12px}.workspace-nodes>strong{color:#6f809b}.workspace-node{display:flex;margin-top:8px;border:1px solid #e4eaf4;border-radius:7px;overflow:hidden}.workspace-node.active{border-color:#9bb4ff;background:#eef3ff}.workspace-node button{border:0;background:transparent;padding:9px;color:#3f608f}.workspace-node button:first-child{flex:1;text-align:left;min-width:0}.workspace-node span{color:#8493ab;margin-left:6px}.workspace-node button:last-child:not(:first-child){font-size:18px}
.workspace-auto-hint{grid-column:1/-1;font-size:11px!important}.workspace-candidate{grid-column:1/-1;margin-top:15px;padding:12px;border:1px solid #b8caff;border-radius:9px;background:#f3f6ff;font-size:12px;overflow-wrap:anywhere}.workspace-candidate p{font-size:11px;line-height:1.8;color:#6f809b}
.workspace-region-overlays{position:absolute;pointer-events:none;z-index:3}.workspace-region-overlays .workspace-region{pointer-events:none;cursor:default}
.workspace-region{z-index:2}.workspace-other{z-index:1;pointer-events:none}.workspace-region.analysis{border-color:#26a77d;background:#20a87824}.workspace-region.analysis span{background:#16775de6}.workspace-nav button:not([aria-current]){background:#fff;border-color:#e4eaf4;color:#6b7e9b}
.person-nav-dot{width:7px;height:7px;border-radius:50%;background:#27a97e;margin-left:auto;flex-shrink:0}.person-filter-card{grid-column:1/-1;border:1px solid #dce5f4;border-radius:12px;padding:16px 13px;margin:20px 0;background:#f8faff}.person-filter-card.enabled{background:#eef7f3;border-color:#a8d7c3}.person-filter-heading{display:flex;gap:12px;align-items:center;justify-content:space-between}.person-filter-heading strong{display:block;font-size:14px}.person-filter-heading div>span{display:block;font-size:11px;color:#7183a0;margin-top:6px}.person-switch{flex-shrink:0;width:44px;height:25px;border:0;border-radius:20px;background:#bbc6da;padding:3px}.person-switch>span{display:block;width:19px;height:19px;border-radius:50%;background:white;box-shadow:0 1px 3px #15264b33;transition:transform .15s}.person-switch[aria-checked=true]{background:#278466}.person-switch[aria-checked=true]>span{transform:translateX(19px)}.person-filter-status{font-size:11px;color:#5b7291;margin:14px 0 0;line-height:1.7}.person-filter-facts{grid-column:1/-1;padding-left:18px;font-size:12px;line-height:1.9;color:#647a99}.person-filter-facts li+li{margin-top:12px}.workspace-person-device{font-size:11px!important;color:#7c8ba4!important}.workspace-person .workspace-scope{margin-top:20px}
@media(prefers-reduced-motion:reduce){.person-switch>span{transition:none}}
@media(max-width:1000px){.workspace-layout{grid-template-columns:140px minmax(0,1fr)}.workspace-settings{grid-column:1/-1;border-left:0;border-top:1px solid #e4eaf4;display:grid;grid-template-columns:1fr 1fr;gap:0 14px}.workspace-settings>h3,.workspace-settings>.workspace-kicker,.workspace-settings>p,.workspace-scope,.workspace-state{grid-column:1/-1}}@media(max-width:600px){.video-workspace{width:96vw;border-radius:12px}.workspace-header{padding:16px}.workspace-header h2{font-size:18px}.workspace-layout{display:block;min-height:0}.workspace-nav{padding:12px 16px;border-right:0;border-bottom:1px solid #e4eaf4}.workspace-nav>span,.workspace-nav>p{display:none}.workspace-nav button{width:auto;margin:0}.workspace-preview{padding:16px 12px}.workspace-settings{padding:18px 16px}.workspace-empty h3{font-size:14px}.workspace-empty p{display:none}.workspace-playback{gap:7px}.workspace-playback span{font-size:10px}}
</style>
