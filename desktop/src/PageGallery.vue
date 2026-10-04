<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { groupFrameTimes, pageNearTime } from './pageGallery'
type Page={pageIndex:number;firstFrameTimeMs:number;lastFrameTimeMs:number;memberFrameTimesMs:number[];representativeFrameTimesMs:number[];ocrLines:{text:string}[];imageAnalysis?:{title:string;content:string}|null;textAnalysis?:{title:string;content:string}|null}
const props=defineProps<{pages:Page[];courseId:string;timeMs:number}>()
const emit=defineEmits<{seek:[timeMs:number]}>()
const selectedIndex=ref<number|null>(null),selectedTime=ref<number|null>(null),following=ref(true),thumbnailPage=ref(0)
const missing=ref(new Set<number>())
const viewer=ref<HTMLDialogElement|null>(null)
const pages=computed(()=>[...props.pages].sort((a,b)=>a.firstFrameTimeMs-b.firstFrameTimeMs))
const selected=computed(()=>pages.value.find(page=>page.pageIndex===selectedIndex.value))
const times=computed(()=>selected.value?groupFrameTimes(selected.value):[])
const index=computed(()=>pages.value.findIndex(page=>page.pageIndex===selectedIndex.value))
const frameIndex=computed(()=>selectedTime.value===null?-1:times.value.indexOf(selectedTime.value))
const thumbnailPages=computed(()=>Math.ceil(times.value.length/8))
const thumbnails=computed(()=>times.value.slice(thumbnailPage.value*8,thumbnailPage.value*8+8))
const automatic=computed(()=>pageNearTime(pages.value,props.timeMs)?.pageIndex)
function stamp(ms:number){const seconds=Math.floor(ms/1000);return `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`}
function title(page:Page){return page.imageAnalysis?.title||page.textAnalysis?.title||page.ocrLines?.[0]?.text||'课程画面'}
function url(time:number){return `http://127.0.0.1:18080/api/transcriptions/${props.courseId}/frames/${time}`}
function choosePage(pageIndex:number,manual=true){
  const page=pages.value.find(p=>p.pageIndex===pageIndex);if(!page)return
  if(manual)following.value=false
  selectedIndex.value=pageIndex
  const frames=groupFrameTimes(page)
  selectedTime.value=page.representativeFrameTimesMs?.find(time=>frames.includes(time))??frames[0]??null
  thumbnailPage.value=Math.max(0,Math.floor(frames.indexOf(selectedTime.value??-1)/8))
}
function chooseFrame(time:number){if(!times.value.includes(time))return;following.value=false;selectedTime.value=time;thumbnailPage.value=Math.floor(times.value.indexOf(time)/8)}
function follow(){following.value=!following.value;if(following.value&&automatic.value!==undefined)choosePage(automatic.value,false)}
function unavailable(time:number){missing.value=new Set([...missing.value,time])}
watch([()=>props.courseId,()=>props.pages],()=>{
  missing.value=new Set();following.value=true;viewer.value?.close();selectedIndex.value=null;selectedTime.value=null;thumbnailPage.value=0
  if(automatic.value!==undefined)choosePage(automatic.value,false)
},{immediate:true})
watch(automatic,value=>{if(following.value&&value!==undefined)choosePage(value,false)})
</script>
<template>
  <div class="gallery-toolbar"><span>按同页分组 · {{ pages.length }} 组</span><button type="button" :aria-pressed="following" @click="follow">{{ following?'正在跟随播放':'跟随播放' }}</button></div>
  <template v-if="selected">
    <div class="gallery-page-nav"><button type="button" aria-label="上一组课件" :disabled="index<=0" @click="choosePage(pages[index-1]!.pageIndex)">‹</button><div><strong>第 {{ selected.pageIndex }} 组</strong><span>{{ stamp(selected.firstFrameTimeMs) }} – {{ stamp(selected.lastFrameTimeMs) }} · {{ times.length }} 张截图</span></div><button type="button" aria-label="下一组课件" :disabled="index>=pages.length-1" @click="choosePage(pages[index+1]!.pageIndex)">›</button></div>
    <div class="gallery-preview">
      <button v-if="selectedTime!==null&&!missing.has(selectedTime)" type="button" class="gallery-image-button" aria-label="查看课件大图" @click="viewer?.showModal()"><img :key="`${courseId}:${selectedTime}`" :src="url(selectedTime)" :alt="`第 ${selected.pageIndex} 组 ${stamp(selectedTime)} 的截图`" @error="unavailable(selectedTime!)" /></button>
      <div v-else class="gallery-image-missing">截图已清理或暂不可用<br /><small>仍可按时间回放本地原视频</small></div>
      <div class="gallery-preview-caption"><span>{{ selectedTime===null?'无截图':stamp(selectedTime) }} <b v-if="selectedTime!==null&&selected.representativeFrameTimesMs.includes(selectedTime)">代表图</b></span><button v-if="selectedTime!==null" type="button" @click="emit('seek',selectedTime)">▶ 回放此处</button></div>
    </div>
    <div class="gallery-frame-nav"><button type="button" aria-label="上一张同组截图" :disabled="frameIndex<=0" @click="chooseFrame(times[frameIndex-1]!)">上一张</button><span>同组 {{ frameIndex+1 }} / {{ times.length }}</span><button type="button" aria-label="下一张同组截图" :disabled="frameIndex>=times.length-1" @click="chooseFrame(times[frameIndex+1]!)">下一张</button></div>
    <div class="gallery-thumbnails"><button v-for="time in thumbnails" :key="time" type="button" :class="{active:selectedTime===time}" :aria-label="`查看 ${stamp(time)} 的同组截图`" :aria-pressed="selectedTime===time" @click="chooseFrame(time)"><img v-if="!missing.has(time)" loading="lazy" :src="url(time)" alt="" @error="unavailable(time)" /><span v-else class="gallery-thumb-missing">已清理</span><span>{{ stamp(time) }} <b v-if="selected.representativeFrameTimesMs.includes(time)">代表</b></span></button></div>
    <div v-if="thumbnailPages>1" class="gallery-frame-nav"><button type="button" aria-label="上一页截图缩略图" :disabled="thumbnailPage===0" @click="thumbnailPage--">‹</button><span>缩略图 {{ thumbnailPage+1 }} / {{ thumbnailPages }}</span><button type="button" aria-label="下一页截图缩略图" :disabled="thumbnailPage>=thumbnailPages-1" @click="thumbnailPage++">›</button></div>
    <details class="gallery-understanding"><summary>{{ title(selected) }}</summary><p>{{ selected.imageAnalysis?.content||selected.textAnalysis?.content||selected.ocrLines.map(line=>line.text).join('\n')||'暂无页面文字' }}</p></details>
  </template>
  <div class="gallery-group-list"><button v-for="page in pages" :key="page.pageIndex" type="button" :class="{active:selectedIndex===page.pageIndex}" :aria-label="`查看第 ${page.pageIndex} 组课件`" @click="choosePage(page.pageIndex)"><span class="gallery-group-number">{{ String(page.pageIndex).padStart(2,'0') }}</span><span><strong>{{ title(page) }}</strong><small>{{ stamp(page.firstFrameTimeMs) }} – {{ stamp(page.lastFrameTimeMs) }} · {{ groupFrameTimes(page).length }} 张</small></span></button></div>
  <dialog ref="viewer" class="gallery-lightbox" aria-label="课件截图大图" @click="($event.target===viewer)&&viewer?.close()"><div><button type="button" aria-label="关闭课件大图" @click="viewer?.close()">×</button><img v-if="selectedTime!==null" :src="url(selectedTime)" :alt="`${stamp(selectedTime)} 的课件截图`" /><footer>{{ selectedTime===null?'':stamp(selectedTime) }}<button v-if="selectedTime!==null" type="button" @click="emit('seek',selectedTime);viewer?.close()">▶ 回放此处</button></footer></div></dialog>
</template>
