<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
type Citation={sourceId:string;startMs:number;endMs:number;quote:string}
type Item={text:string;citations:Citation[]}
type Overview={status:string;headline:string;summary:Item[];objectives:Item[];keyPoints:Item[];pitfalls:Item[];highlights:Item[]}
const props=defineProps<{courseId:string;ready:boolean}>()
const emit=defineEmits<{seek:[timeMs:number,sourceId:string]}>()
const result=ref<Overview|null>(null),status=ref('not_requested')
const errorCode=ref('')
const sections=[{key:'summary',title:'内容摘要'},{key:'objectives',title:'学习目标'},{key:'keyPoints',title:'课程重点'},{key:'pitfalls',title:'易错与注意事项'},{key:'highlights',title:'重点回看片段'}] as const
let controller:AbortController|undefined
function stamp(ms:number){const seconds=Math.floor(ms/1000);return `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`}
watch(()=>[props.courseId,props.ready] as const,async ([id,ready])=>{
  controller?.abort();result.value=null;status.value='not_requested';errorCode.value=''
  if(!id||!ready)return
  const current=new AbortController();controller=current;let errors=0
  const endpoint=`http://127.0.0.1:18080/api/transcriptions/${id}/overview`
  try {
    for(let attempt=0;attempt<900&&!current.signal.aborted;attempt++){
      try {
        let response=await fetch(endpoint,{signal:current.signal})
        if(!response.ok)throw new Error(String(response.status))
        let job=await response.json()
        if(job.status==='not_requested'){
          response=await fetch(endpoint,{method:'POST',signal:current.signal})
          if(!response.ok)throw new Error(String(response.status))
          job=await response.json()
        }
        if(current.signal.aborted)return
        errors=0;status.value=job.status;errorCode.value=job.error??''
        if(job.status==='completed'){result.value=job.result;return}
        if(job.status==='failed')return
      }catch(error){
        if(current.signal.aborted)return
        const code=Number((error as Error).message)
        if(code>=400&&code<500&&![408,429].includes(code)||++errors>=3)throw error
      }
      await new Promise(resolve=>setTimeout(resolve,1500))
    }
    if(!current.signal.aborted)status.value='failed'
  }catch{if(!current.signal.aborted)status.value='failed'}
},{immediate:true})
onUnmounted(()=>controller?.abort())
</script>
<template>
  <div class="overview-heading"><span class="eyebrow">AI COURSE INSIGHTS</span><h3>AI 解读</h3><p>先了解课程，再带着重点观看</p></div>
  <div v-if="result?.status==='completed'" class="overview-content">
    <div class="overview-headline"><span aria-hidden="true">✦</span><span>{{ result.headline }}</span></div>
    <section v-for="section in sections" :key="section.key" class="overview-section">
      <h4>{{ section.title }}</h4>
      <article v-for="(item,i) in result[section.key]" :key="i" class="overview-item">
        <p>{{ item.text }}</p>
        <div class="overview-citations"><button v-for="citation in item.citations" :key="citation.sourceId" type="button" :title="citation.quote" :aria-label="`回放 ${stamp(citation.startMs)} 的讲解：${citation.quote}`" @click="emit('seek',citation.startMs,citation.sourceId)">▶ {{ stamp(citation.startMs) }}</button></div>
      </article>
      <p v-if="!result[section.key].length" class="overview-muted">课程中没有提取到明确内容。</p>
    </section>
    <p class="overview-footnote">依据课程转写及页面理解生成，可能存在识别误差；点击时间回看原讲解。</p>
  </div>
  <div v-else class="sidebar-empty compact" role="status"><span v-if="['queued','processing'].includes(status)" class="activity-spinner"></span><h3>{{ ['queued','processing'].includes(status)?'正在概括课程…':status==='failed'?'AI 解读暂未生成':result?.status==='empty'?'暂无可解读内容':'还没有课程解读' }}</h3><p>{{ errorCode==='overview_provider_payment_required'?'模型服务返回余额或额度不足，恢复后可继续生成。':status==='failed'?'本次解读未完成，其他学习功能仍可使用。':'分析完成后，将根据语音与页面理解概括课程内容，并提供回看依据。' }}</p></div>
</template>
