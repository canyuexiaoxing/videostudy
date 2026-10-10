<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
type Citation={sourceId:string;startMs:number;endMs:number;quote:string}
type Item={text:string;citations:Citation[]}
type Overview={status:string;headline:string;summary:Item[];objectives:Item[];keyPoints:Item[];pitfalls:Item[];highlights:Item[]}
const props=defineProps<{courseId:string;ready:boolean}>()
const result=ref<Overview|null>(null),status=ref('not_requested')
const errorCode=ref('')
const analysis=computed(()=>{
  const parts=[...new Set((result.value?.summary??[]).map(item=>item.text.trim()).filter(Boolean))]
  return parts.map(text=>/[。！？.!?]$/.test(text)?text:`${text}。`).join('')
})
let controller:AbortController|undefined
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
  <div v-if="result?.status==='completed'" class="overview-content">
    <p class="overview-analysis">{{ analysis }}</p>
  </div>
  <div v-else class="sidebar-empty compact" role="status"><span v-if="['queued','processing'].includes(status)" class="activity-spinner"></span><h3>{{ ['queued','processing'].includes(status)?'正在概括课程…':status==='failed'?'AI 解读暂未生成':result?.status==='empty'?'暂无可解读内容':'还没有课程解读' }}</h3><p>{{ errorCode==='overview_provider_payment_required'?'模型服务返回余额或额度不足，恢复后可继续生成。':status==='failed'?'本次解读未完成，其他学习功能仍可使用。':'分析完成后，将根据语音与页面理解概括课程内容。' }}</p></div>
</template>

<style scoped>
.overview-analysis{margin:0;padding:4px 0;font-size:14px;line-height:1.9;color:#405779;overflow-wrap:anywhere}
</style>
