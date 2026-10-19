<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { chapterAt, timelineChapters, timeAtPointer } from './chapters'
import type { VideoChapter } from './chapters'
import { BrowserPreview } from './browserPreview'
import type { PreviewState } from './browserPreview'
import { previewTile } from './timelinePreview'
const props=defineProps<{src:string;chapters:VideoChapter[];chapterStatus:string;previewCourseId?:string;previewFingerprint?:string;previewBlocked?:boolean}>()
const emit=defineEmits<{ready:[HTMLVideoElement|null];timeupdate:[Event]}>()
const media=ref<HTMLVideoElement|null>(null)
const surface=ref<HTMLElement|null>(null)
const duration=ref(0),time=ref(0),paused=ref(true),muted=ref(false),volume=ref(1),rate=ref('1')
const visible=ref(true),focused=ref(false),directory=ref(false),hoverTime=ref<number|null>(null),hoverRatio=ref(0)
const frameReady=ref(false),mediaError=ref('')
let timer:ReturnType<typeof setTimeout>|undefined
let pointerStart:number|null=null,dragging=false
let preview:BrowserPreview|undefined,lastInteraction=performance.now(),previewRequest=0
const previewImage=ref<string|null>(null),previewState=ref<PreviewState>('waiting')
const previewLocation=computed(()=>hoverTime.value===null?null:previewTile(hoverTime.value,duration.value))
const previewStyle=computed(()=>previewImage.value&&previewLocation.value?{backgroundImage:`url("${previewImage.value}")`,backgroundPosition:`-${previewLocation.value.x}px -${previewLocation.value.y}px`}:undefined)
function interacted(){lastInteraction=performance.now()}
async function loadPreview(){
 const request=++previewRequest,location=previewLocation.value
 if(!preview||!location){previewImage.value=null;return}
 const image=await preview.sheet(location.sheet)
 if(request===previewRequest)previewImage.value=image
}
watch(()=>[props.src,props.previewCourseId,props.previewFingerprint,duration.value] as const,([src,id,fingerprint,length])=>{
 preview?.dispose();preview=undefined;previewImage.value=null;previewState.value='waiting';previewRequest++
 if(!id||!fingerprint||!Number.isFinite(length)||length<=0)return
 preview=new BrowserPreview({src,courseId:id,fingerprint,duration:length,
  localIdle:()=>!props.previewBlocked&&document.visibilityState==='visible'&&!!media.value?.paused&&!dragging&&performance.now()-lastInteraction>2000,
  onSheet:()=>void loadPreview(),onState:state=>{previewState.value=state;if(state==='completed')void loadPreview()}})
})
watch(()=>previewLocation.value?.sheet,()=>{previewImage.value=null;void loadPreview()})

const chapters=computed(()=>timelineChapters(props.chapters,duration.value))
const active=computed(()=>chapterAt(chapters.value,time.value*1000))
const hovered=computed(()=>hoverTime.value===null?undefined:chapterAt(chapters.value,hoverTime.value*1000))
const sections=computed(()=>chapters.value.length?chapters.value:duration.value>0?[{id:'whole',title:'课程视频',startMs:0,endMs:duration.value*1000}]:[])
function stamp(seconds:number){const s=Math.max(0,Math.floor(seconds));return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`}
function sync(event?:Event){if(!media.value)return;frameReady.value=media.value.readyState>=2;time.value=media.value.currentTime;duration.value=Number.isFinite(media.value.duration)?media.value.duration:0;paused.value=media.value.paused;muted.value=media.value.muted;volume.value=media.value.volume;if(event?.type==='timeupdate')emit('timeupdate',event)}
function loadedMetadata(event:Event){if(media.value)media.value.playbackRate=Number(rate.value);sync(event)}
function failed(){mediaError.value=media.value?.error?.code===4?'当前视频的实际封装格式或编码无法直接播放，请使用上方的“显卡兼容播放”生成兼容副本。':'视频读取或解码失败，请重新选择本地文件。'}
watch(()=>props.src,()=>{frameReady.value=false;mediaError.value='';time.value=0;duration.value=0;paused.value=true;directory.value=false;hoverTime.value=null;reveal()})
function reveal(){visible.value=true;clearTimeout(timer);if(!paused.value)timer=setTimeout(()=>{visible.value=false},2800)}
function leave(){hoverTime.value=null;if(!paused.value)visible.value=false}
function seek(ms:number){if(!media.value||duration.value<=0)return;media.value.currentTime=Math.min(duration.value,Math.max(0,ms/1000));sync();reveal()}
async function toggle(){if(!media.value)return;if(media.value.paused){try{await media.value.play()}catch{paused.value=true}}else media.value.pause();reveal()}
function locate(event:PointerEvent){const r=(event.currentTarget as HTMLElement).getBoundingClientRect();hoverRatio.value=Math.min(.9,Math.max(.1,(event.clientX-r.left)/r.width));return timeAtPointer(event.clientX,r.left,r.width,duration.value)}
function move(event:PointerEvent){reveal();hoverTime.value=locate(event);if(pointerStart!==null&&Math.abs(event.clientX-pointerStart)>4)dragging=true;if(dragging)seek(hoverTime.value*1000)}
function down(event:PointerEvent){pointerStart=event.clientX;dragging=false;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);hoverTime.value=locate(event)}
function up(event:PointerEvent){if(pointerStart===null)return;const position=locate(event);seek(position*1000);pointerStart=null;dragging=false}
async function fullscreen(){if(!surface.value)return;try{if(document.fullscreenElement)await document.exitFullscreen();else await surface.value.requestFullscreen()}catch{/* Browser may deny fullscreen without activation. */}}
function key(event:KeyboardEvent){if((event.target as HTMLElement).matches('button,input,select'))return;if([' ','ArrowLeft','ArrowRight','f'].includes(event.key)){event.preventDefault();if(event.key===' ')void toggle();else if(event.key==='f')void fullscreen();else seek((time.value+(event.key==='ArrowLeft'?-5:5))*1000)}}
onMounted(()=>{emit('ready',media.value);window.addEventListener('pointermove',interacted,{passive:true});window.addEventListener('keydown',interacted)})
onUnmounted(()=>{clearTimeout(timer);preview?.dispose();window.removeEventListener('pointermove',interacted);window.removeEventListener('keydown',interacted);emit('ready',null)})
</script>

<template>
  <div ref="surface" class="chapter-player" :class="{'controls-visible':visible||paused||focused||directory}" tabindex="0" aria-label="课程视频播放器，空格播放暂停，方向键快进后退" @pointermove="reveal" @pointerenter="reveal" @pointerleave="leave" @focusin="focused=!!surface?.querySelector(':focus-visible')||!!surface?.matches(':focus-visible')" @focusout="focused=!!surface?.contains($event.relatedTarget as Node)&&!!surface?.querySelector(':focus-visible')" @keydown="key">
    <video ref="media" crossorigin="anonymous" :src="src" preload="auto" playsinline @loadedmetadata="loadedMetadata" @loadeddata="sync" @canplay="sync" @error="failed" @durationchange="sync" @timeupdate="sync" @play="sync();reveal()" @pause="sync" @ended="sync" @volumechange="sync" @click="toggle"><slot /></video>
    <div v-if="mediaError||!frameReady" class="chapter-media-status" role="status"><span>{{ mediaError||'正在加载本地视频画面…' }}</span><button v-if="!mediaError" type="button" @click="toggle">点击播放</button></div>
    <div class="chapter-overlay">
      <div class="chapter-current"><span class="chapter-live-dot"></span>{{ active?.title || '课程视频' }}</div>
      <div class="chapter-seek" role="slider" aria-label="视频进度：点击或拖动定位到对应时间" :aria-valuemin="0" :aria-valuemax="duration" :aria-valuenow="time" :aria-valuetext="`${stamp(time)} ${active?.title||''}`" tabindex="0" @pointerdown="down" @pointermove.stop="move" @pointerup="up" @pointercancel="pointerStart=null;dragging=false" @pointerleave="hoverTime=null">
        <div v-for="c in sections" :key="c.id" class="chapter-bar-segment" :class="{'is-active':active?.id===c.id}" :style="{flexGrow:c.endMs-c.startMs}"><span class="chapter-bar-fill" :style="{width:`${Math.max(0,Math.min(100,(time*1000-c.startMs)/(c.endMs-c.startMs)*100))}%`}"></span></div>
        <div v-if="hoverTime!==null" class="chapter-tooltip" :style="{'--hover-position':`${hoverRatio*100}%`}"><span v-if="previewImage" class="chapter-preview-image" :style="previewStyle" role="img" :aria-label="`${stamp(hoverTime)} 附近的视频预览`"></span><small v-else-if="previewCourseId && previewState!=='unavailable'" class="chapter-preview-hint">{{ previewState==='completed'?'此处预览暂不可用':'此处预览尚未生成，空闲后自动准备' }}</small><strong>{{ hovered?.title||'定位播放' }}</strong><span v-if="hovered">{{ stamp(hovered.startMs/1000) }} – {{ stamp(hovered.endMs/1000) }}</span><span>{{ stamp(hoverTime) }}</span></div>
      </div>
      <div class="chapter-controls">
        <button type="button" :aria-label="paused?'播放':'暂停'" @click="toggle">{{ paused?'▶':'❚❚' }}</button><span class="chapter-clock">{{ stamp(time) }}<span> / {{ stamp(duration) }}</span></span>
        <button type="button" class="chapter-directory-toggle" :aria-expanded="directory" @click="directory=!directory">☷ AI 章节<span v-if="chapters.length"> · {{ chapters.length }}</span></button>
        <div class="chapter-controls-spacer"></div>
        <button type="button" :aria-label="muted?'取消静音':'静音'" @click="media&&(media.muted=!media.muted)">{{ muted?'静音':'音量' }}</button><input class="chapter-volume" aria-label="音量" type="range" min="0" max="1" step="0.05" :value="volume" @input="media&&(media.volume=Number(($event.target as HTMLInputElement).value))" />
        <select v-model="rate" aria-label="播放倍速" @change="media&&(media.playbackRate=Number(rate))"><option v-for="speed in ['0.5','0.75','1','1.25','1.5','2']" :key="speed" :value="speed">{{ speed }}×</option></select><button type="button" aria-label="全屏播放器" @click="fullscreen">⛶</button>
      </div>
    </div>
    <div v-if="directory" class="chapter-directory">
      <div class="chapter-directory-header"><strong>AI 时间章节</strong><button type="button" aria-label="关闭章节目录" @click="directory=false">×</button></div>
      <button v-for="(c,i) in chapters" :key="c.id" type="button" class="chapter-directory-row" :class="{active:active?.id===c.id}" @click="seek(c.startMs);directory=false"><span>{{ String(i+1).padStart(2,'0') }}</span><strong>{{ c.title }}</strong><small>{{ stamp(c.startMs/1000) }}</small></button>
      <p v-if="!chapters.length">{{ ['queued','processing'].includes(chapterStatus)?'AI 正在按讲解顺序划分章节…':chapterStatus==='failed'?'章节暂时生成失败；视频仍可播放。':'暂无可用章节。' }}</p>
    </div>
  </div>
</template>
