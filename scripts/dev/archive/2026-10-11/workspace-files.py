from pathlib import Path
root=Path(r'E:\workp\videostudy')
files={
'desktop/src/videoRegion.ts':'''export type VideoRegion = { x:number; y:number; width:number; height:number }
export type FrameRect = { left:number; top:number; width:number; height:number }
export function normalizeRegion(value:unknown):VideoRegion|null {
 if(!value||typeof value!=='object')return null
 const r=value as VideoRegion
 if(![r.x,r.y,r.width,r.height].every(v=>typeof v==='number'&&Number.isFinite(v))||r.x<0||r.y<0||r.width<=0||r.height<=0||r.x+r.width>1.000001||r.y+r.height>1.000001)return null
 return {x:r.x,y:r.y,width:Math.min(r.width,1-r.x),height:Math.min(r.height,1-r.y)}
}
export function containedFrame(width:number,height:number,videoWidth:number,videoHeight:number):FrameRect {
 if(![width,height,videoWidth,videoHeight].every(v=>Number.isFinite(v)&&v>0))return {left:0,top:0,width:0,height:0}
 const scale=Math.min(width/videoWidth,height/videoHeight),w=videoWidth*scale,h=videoHeight*scale
 return {left:(width-w)/2,top:(height-h)/2,width:w,height:h}
}
export function regionFromPoints(x1:number,y1:number,x2:number,y2:number):VideoRegion|null {
 const clamp=(v:number)=>Math.max(0,Math.min(1,v))
 const a=clamp(x1),b=clamp(y1),c=clamp(x2),d=clamp(y2)
 return normalizeRegion({x:Math.min(a,c),y:Math.min(b,d),width:Math.abs(a-c),height:Math.abs(b-d)})
}
''',
'desktop/src/videoRegion.test.mjs':'''import test from 'node:test'
import assert from 'node:assert/strict'
import {normalizeRegion,containedFrame,regionFromPoints} from './videoRegion.ts'
test('video frame mapping excludes letterbox space for wide and portrait videos',()=>{
 assert.deepEqual(containedFrame(1000,600,1920,1080),{left:0,top:18.75,width:1000,height:562.5})
 assert.deepEqual(containedFrame(1000,600,600,1200),{left:350,top:0,width:300,height:600})
 assert.equal(containedFrame(0,600,1920,1080).width,0)
})
test('reverse drags and out of frame pointers produce bounded normalized regions',()=>{
 assert.deepEqual(regionFromPoints(.8,.9,.2,.3),{x:.2,y:.3,width:.6000000000000001,height:.6000000000000001})
 assert.deepEqual(regionFromPoints(-1,-1,2,2),{x:0,y:0,width:1,height:1})
 assert.equal(regionFromPoints(.2,.2,.2,.8),null)
})
test('invalid saved regions cannot restore outside the video',()=>{
 for(const r of [null,{x:0,y:0,width:NaN,height:1},{x:.9,y:0,width:.2,height:.2},{x:0,y:-1,width:.2,height:.2}])assert.equal(normalizeRegion(r),null)
 assert.deepEqual(normalizeRegion({x:.8,y:.75,width:.2,height:.25}),{x:.8,y:.75,width:.19999999999999996,height:.25})
})
''',
'desktop/src/VideoWorkspace.vue':'''<script setup lang="ts">
import {ref,computed,watch,onMounted,onBeforeUnmount} from 'vue'
import StudyIcon from './StudyIcon.vue'
import {containedFrame,normalizeRegion,regionFromPoints} from './videoRegion'
import type {VideoRegion} from './videoRegion'
const props=defineProps<{src:string;filename:string;modelValue:VideoRegion|null;timeMs:number;checking?:boolean}>()
const emit=defineEmits<{close:[];selectFile:[event:Event];'update:modelValue':[region:VideoRegion|null]}>()
const dialog=ref<HTMLDialogElement|null>(null),media=ref<HTMLVideoElement|null>(null),stage=ref<HTMLElement|null>(null)
const surface=ref<HTMLElement|null>(null),width=ref(0),height=ref(0),videoWidth=ref(0),videoHeight=ref(0)
const time=ref(0),duration=ref(0),paused=ref(true),editing=ref(false),draft=ref<VideoRegion|null>(normalizeRegion(props.modelValue))
const error=ref(''),note=ref(''),ready=ref(false)
let observer:ResizeObserver|undefined,anchor:{x:number;y:number;pointerId:number}|null=null
const frame=computed(()=>containedFrame(width.value,height.value,videoWidth.value,videoHeight.value))
const frameStyle=computed(()=>({left:`${frame.value.left}px`,top:`${frame.value.top}px`,width:`${frame.value.width}px`,height:`${frame.value.height}px`}))
const regionStyle=computed(()=>draft.value?{left:`${draft.value.x*100}%`,top:`${draft.value.y*100}%`,width:`${draft.value.width*100}%`,height:`${draft.value.height*100}%`}:{})
const canDraw=computed(()=>ready.value&&videoWidth.value>0&&!props.checking)
const changed=computed(()=>JSON.stringify(draft.value)!==JSON.stringify(normalizeRegion(props.modelValue)))
const clock=(seconds:number)=>`${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`
function sync(){if(media.value){time.value=media.value.currentTime;paused.value=media.value.paused}}
function loaded(){
 const v=media.value;if(!v)return
 videoWidth.value=v.videoWidth;videoHeight.value=v.videoHeight;duration.value=Number.isFinite(v.duration)?v.duration:0
 v.currentTime=Math.max(0,Math.min(props.timeMs/1000,duration.value));ready.value=true;sync()
}
function cancelDrawing(){anchor=null;editing.value=false;draft.value=normalizeRegion(props.modelValue);error.value='';note.value=''}
function startDrawing(){media.value?.pause();cancelDrawing();editing.value=true;note.value='在视频画面上拖动，框住需要忽略的区域。'}
function point(event:PointerEvent){const box=surface.value!.getBoundingClientRect();return {x:(event.clientX-box.left)/box.width,y:(event.clientY-box.top)/box.height}}
function down(event:PointerEvent){
 if(!editing.value||!canDraw.value||event.button!==0)return
 event.preventDefault();const p=point(event);anchor={...p,pointerId:event.pointerId};draft.value=null
 surface.value?.setPointerCapture(event.pointerId)
}
function move(event:PointerEvent){if(!anchor||anchor.pointerId!==event.pointerId)return;const p=point(event);draft.value=regionFromPoints(anchor.x,anchor.y,p.x,p.y)}
function up(event:PointerEvent){
 if(!anchor||anchor.pointerId!==event.pointerId)return
 move(event);anchor=null
 if(surface.value?.hasPointerCapture(event.pointerId))surface.value.releasePointerCapture(event.pointerId)
 if(!draft.value||draft.value.width*frame.value.width<8||draft.value.height*frame.value.height<8){draft.value=null;error.value='框选范围太小，请重新拖动。';return}
 if(draft.value.width*draft.value.height>.95){draft.value=null;error.value='请保留需要分析的课件区域，不要框住整个画面。';return}
 editing.value=false;error.value='';note.value='框选完成，点击“确认区域”保存。'
}
function save(){if(!draft.value||editing.value||!canDraw.value)return;emit('update:modelValue',normalizeRegion(draft.value));note.value='已保存当前视频的框选设置。'}
function clear(){cancelDrawing();draft.value=null;emit('update:modelValue',null);note.value='已清除忽略区域。'}
async function toggle(){if(!media.value)return;if(media.value.paused){try{await media.value.play()}catch{error.value='视频暂时无法播放，可尝试主页面的兼容播放。'}}else media.value.pause()}
function close(){media.value?.pause();emit('close')}
watch(()=>props.src,()=>{media.value?.pause();ready.value=false;videoWidth.value=0;videoHeight.value=0;time.value=0;duration.value=0;cancelDrawing()})
watch(()=>props.modelValue,value=>{if(!editing.value&&!anchor)draft.value=normalizeRegion(value)})
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
     <video v-if="src" ref="media" :src="src" preload="metadata" playsinline @loadedmetadata="loaded" @timeupdate="sync" @play="sync" @pause="sync" @ended="sync" @error="error='无法读取视频画面，请在主页面尝试兼容播放。'"/>
     <div v-else class="workspace-empty"><StudyIcon name="play"/><h3>先选择一段视频</h3><p>播放并暂停在摄像头位置清楚的画面，再开始框选。</p><label class="workspace-primary">选择本地视频<input type="file" accept="video/*,audio/*" @change="emit('selectFile',$event)"/></label></div>
     <p v-if="src&&ready&&!videoWidth" class="workspace-audio">当前文件没有视频画面，无法框选。</p>
     <div v-if="canDraw" ref="surface" :style="frameStyle" :class="['workspace-surface',{drawing:editing}]" @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="cancelDrawing">
      <div v-if="draft" class="workspace-region" :style="regionStyle"><span>{{ changed?'待确认区域':'忽略区域' }}</span></div>
     </div>
    </div>
    <div class="workspace-playback"><button type="button" :disabled="!ready||editing" :aria-label="paused?'播放预览':'暂停预览'" @click="toggle">{{ paused?'播放':'暂停' }}</button><input aria-label="预览进度" type="range" min="0" :max="duration||0" step="0.1" :value="time" :disabled="!ready||editing" @input="media&&(media.currentTime=Number(($event.target as HTMLInputElement).value))"/><span>{{ clock(time) }} / {{ clock(duration) }}</span></div>
    <p class="workspace-preview-note">暂停后框选。摄像头区域会显示遮罩，视频和原始截图仍保留完整画面。</p>
   </section>
   <aside class="workspace-settings" aria-labelledby="ignore-title"><span class="workspace-kicker">画面设置</span><h3 id="ignore-title">忽略画面区域</h3><p>用于排除摄像头、人像等持续运动区域，减少无关变化引起的重复截图。</p>
    <div class="workspace-state">{{ checking?'正在确认当前文件…':editing?'正在框选':changed?'有待确认的修改':modelValue?'已设置 1 个区域':'未设置忽略区域' }}</div>
    <button class="workspace-primary" type="button" :disabled="!canDraw" @click="startDrawing">{{ draft?'重新框选':'开始框选' }}</button>
    <button v-if="editing||changed" class="workspace-secondary" type="button" @click="cancelDrawing">取消框选</button>
    <button v-if="draft&&!editing" class="workspace-primary" type="button" :disabled="!canDraw||!changed" @click="save">确认区域</button>
    <button class="workspace-secondary" type="button" :disabled="!modelValue&&!draft" @click="clear">清除区域</button>
    <p v-if="note" class="workspace-note" role="status">{{ note }}</p><p v-if="error" class="workspace-error" role="alert">{{ error }}</p>
    <div class="workspace-scope"><strong>当前为前端设置</strong><p>区域保存在当前浏览器，并与所选文件关联；尚未接入实际分析。</p></div>
   </aside>
  </div>
 </dialog>
</template>
<style scoped>
.video-workspace{box-sizing:border-box;width:min(1400px,96vw);max-width:none;max-height:94dvh;margin:auto;padding:0;border:1px solid #e1e8f6;border-radius:18px;background:#f7f9fd;color:#273754;box-shadow:0 28px 100px #0b1b4540;overflow:auto}.video-workspace::backdrop{background:#142342a6;backdrop-filter:blur(4px)}.workspace-header{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:22px 26px;background:#fff;border-bottom:1px solid #e4eaf4}.workspace-header h2{margin:0;font-size:21px}.workspace-header p{margin:7px 0 0;color:#7182a0;font-size:12px;overflow-wrap:anywhere}.workspace-close{border:1px solid #dce4f2;background:#fff;border-radius:8px;padding:9px 14px;color:#536582;white-space:nowrap}.workspace-close span{margin-left:8px;font-size:19px}.workspace-layout{display:grid;grid-template-columns:165px minmax(0,1fr) 250px;min-height:500px}.workspace-nav{padding:22px 14px;border-right:1px solid #e4eaf4;background:#fff}.workspace-nav>span,.workspace-kicker{font-size:11px;letter-spacing:.08em;color:#8290aa}.workspace-nav button{display:flex;align-items:center;gap:9px;width:100%;margin-top:15px;padding:12px 10px;border:1px solid #cbd9ff;border-radius:9px;color:#315dec;background:#eef3ff;text-align:left;font-weight:600}.workspace-nav svg{width:17px;height:17px}.workspace-nav p{margin:17px 4px;color:#8190a8;font-size:11px;line-height:1.9}.workspace-preview{min-width:0;padding:24px 20px}.workspace-stage{position:relative;aspect-ratio:16/9;background:#10192b;border-radius:12px;overflow:hidden}.workspace-stage video{display:block;width:100%;height:100%;object-fit:contain}.workspace-surface{position:absolute;pointer-events:none}.workspace-surface.drawing{pointer-events:auto;touch-action:none;cursor:crosshair}.workspace-region{position:absolute;box-sizing:border-box;border:2px solid #84a8ff;background:#537dee50;pointer-events:none}.workspace-region span{position:absolute;top:5px;left:5px;padding:3px 6px;border-radius:4px;background:#20396de6;color:white;font-size:10px;white-space:nowrap}.workspace-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;padding:16px;box-sizing:border-box;color:#dbe5ff;text-align:center}.workspace-empty svg{width:34px;height:34px;color:#a8bfff}.workspace-empty h3{margin:12px 0 0;font-size:17px}.workspace-empty p{font-size:12px;color:#9fafcb;line-height:1.7}.workspace-empty label{margin-top:8px;cursor:pointer}.workspace-empty input{display:none}.workspace-playback{display:flex;align-items:center;gap:12px;margin-top:14px}.workspace-playback button{border:1px solid #d8e2f3;background:#fff;padding:7px 12px;border-radius:7px;color:#3c557a;white-space:nowrap}.workspace-playback input{min-width:0;flex:1;accent-color:#4166ed}.workspace-playback span{font-size:11px;color:#6f809c;white-space:nowrap}.workspace-preview-note{font-size:12px;color:#7283a1;line-height:1.8}.workspace-settings{padding:24px 20px;background:#fff;border-left:1px solid #e4eaf4}.workspace-settings h3{font-size:17px;margin:12px 0}.workspace-settings>p{font-size:12px;color:#73829a;line-height:1.9}.workspace-state{margin:20px 0 12px;padding:11px 12px;border:1px solid #e4eaf4;border-radius:8px;background:#f7f9fd;font-size:12px;color:#5d7396}.workspace-primary,.workspace-secondary{box-sizing:border-box;display:block;width:100%;padding:11px 14px;margin-top:9px;border-radius:8px;font:inherit;font-size:12px;text-align:center}.workspace-primary{border:1px solid #4166ed;color:#fff;background:#4166ed}.workspace-secondary{border:1px solid #dce4f2;color:#5d7293;background:#fff}.workspace-scope{margin-top:26px;padding-top:18px;border-top:1px solid #e8edf5;font-size:11px;color:#8795aa;line-height:1.8}.workspace-scope strong{color:#6f809b}.workspace-scope p{margin:6px 0}.workspace-settings .workspace-note{color:#375dba}.workspace-settings .workspace-error{color:#b24f61}.workspace-audio{position:absolute;inset:40% 10%;color:#c9d6ec;text-align:center;font-size:13px}button,label{cursor:pointer}button:disabled{opacity:.45;cursor:default}button:focus-visible,input:focus-visible,label:focus-within{outline:2px solid #6f99ff;outline-offset:3px}
@media(max-width:1000px){.workspace-layout{grid-template-columns:140px minmax(0,1fr)}.workspace-settings{grid-column:1/-1;border-left:0;border-top:1px solid #e4eaf4;display:grid;grid-template-columns:1fr 1fr;gap:0 14px}.workspace-settings>h3,.workspace-settings>.workspace-kicker,.workspace-settings>p,.workspace-scope,.workspace-state{grid-column:1/-1}}@media(max-width:600px){.video-workspace{width:96vw;border-radius:12px}.workspace-header{padding:16px}.workspace-header h2{font-size:18px}.workspace-layout{display:block;min-height:0}.workspace-nav{padding:12px 16px;border-right:0;border-bottom:1px solid #e4eaf4}.workspace-nav>span,.workspace-nav>p{display:none}.workspace-nav button{width:auto;margin:0}.workspace-preview{padding:16px 12px}.workspace-settings{padding:18px 16px}.workspace-empty h3{font-size:14px}.workspace-empty p{display:none}.workspace-playback{gap:7px}.workspace-playback span{font-size:10px}}
</style>
'''
}
for name,content in files.items(): (root/name).write_text(content,encoding='utf-8')
p=root/'desktop/src/App.vue';s=p.read_text(encoding='utf-8')
s=s.replace("import ChapterPlayer from './ChapterPlayer.vue'","import ChapterPlayer from './ChapterPlayer.vue'\nimport VideoWorkspace from './VideoWorkspace.vue'\nimport { normalizeRegion } from './videoRegion'\nimport type { VideoRegion } from './videoRegion'")
s=s.replace("const selectedFingerprint = ref('')",'''const selectedFingerprint = ref('')
const workspaceOpen = ref(false)
const ignoredRegion = ref<VideoRegion|null>(null)
watch(selectedFingerprint, fingerprint => {
  try { ignoredRegion.value = fingerprint ? normalizeRegion(JSON.parse(localStorage.getItem(`videoIgnoreRegion:v1:${fingerprint}`) ?? 'null')) : null }
  catch { ignoredRegion.value = null }
})
function saveIgnoredRegion(region: VideoRegion|null) {
  ignoredRegion.value = normalizeRegion(region)
  if (!selectedFingerprint.value) return
  try {
    const key = `videoIgnoreRegion:v1:${selectedFingerprint.value}`
    if (ignoredRegion.value) localStorage.setItem(key, JSON.stringify(ignoredRegion.value))
    else localStorage.removeItem(key)
  } catch { /* Keep the current setting even when browser storage is unavailable. */ }
}
function openVideoWorkspace() { video.value?.pause(); workspaceOpen.value = true }
''')
old='<div class="player-tools"><button v-if="selectedFile"'
assert s.count(old)==1
s=s.replace(old,'<div class="player-tools"><button type="button" class="subtitle-toggle workspace-entry" @click="openVideoWorkspace"><StudyIcon name="slides" />视频工作台<span v-if="ignoredRegion" class="workspace-entry-dot" aria-label="已保存忽略区域"></span></button><button v-if="selectedFile"')
assert s.count('  </main>')==1
s=s.replace('  </main>','''    <VideoWorkspace v-if="workspaceOpen" :src="videoUrl" :filename="filename" :model-value="ignoredRegion" :time-ms="currentPlaybackMs" :checking="checkingMedia" @close="workspaceOpen=false" @select-file="chooseVideo" @update:model-value="saveIgnoredRegion" />
  </main>''')
p.write_text(s,encoding='utf-8')
p=root/'desktop/src/study-design.css';p.write_text(p.read_text(encoding='utf-8')+'''
.player-tools .workspace-entry { display:inline-flex; align-items:center; gap:6px; border-color:#ccd9ff; color:#315dec; background:#f0f4ff; }
.player-tools .workspace-entry svg { width:15px; height:15px; }
.player-tools .workspace-entry .workspace-entry-dot { width:6px; height:6px; border-radius:50%; background:#4166ed; }
''',encoding='utf-8')
p=root/'docs/superpowers/specs/2026-10-10-video-workspace-frontend.md';p.write_text('''# 视频工作台前端
用户确认在课程视频标题右侧增加工作台按钮，先改前端。
原生dialog弹窗：工具导航、视频预览、设置面板。第一项忽略区域支持暂停定位、指针/触摸拖动、确认、取消、重新框选和清除。
框选使用实际视频画面的比例坐标，object-fit contain黑边不参与。区域在当前浏览器按现有文件指纹隔离保存；关闭保留已确认设置，未确认草稿丢弃。
无文件时支持在弹窗选择文件，音频无视频画面时禁用框选。打开暂停主播放器，关闭暂停预览。Esc关闭，原生模态焦点管理。
本次不传入分析API、不改后端和OCR，界面明确标记仅前端设置尚未接入分析。
验证宽/竖视频几何、反向拖动、非法数据、弹窗空状态、保存恢复清除、切文件隔离及手机布局。
''',encoding='utf-8')
