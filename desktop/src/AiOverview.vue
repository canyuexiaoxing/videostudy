<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import AiNoteSection from './AiNoteSection.vue'
import type { Note } from './AiNoteSection.vue'
type Citation={sourceId:string;startMs:number;endMs:number;quote:string}
type Item={text:string;citations:Citation[]}
type Overview={status:string;headline:string;summary:Item[];objectives:Item[];keyPoints:Item[];pitfalls:Item[];highlights:Item[];notes?:Note[]}
const props=defineProps<{courseId:string;ready:boolean}>()
const emit=defineEmits<{seek:[time:number]}>()
const refresh=ref(0)
const requested=ref(false)
const result=ref<Overview|null>(null),status=ref('not_requested')
const errorCode=ref('')
const analysis=computed(()=>{
  const parts=[...new Set((result.value?.summary??[]).map(item=>item.text.trim()).filter(Boolean))]
  return parts.map(text=>/[。！？.!?]$/.test(text)?text:`${text}。`).join('')
})
let controller:AbortController|undefined
let previousCourseId=''
watch(()=>[props.courseId,props.ready,refresh.value] as const,async ([id,ready])=>{
  if(id!==previousCourseId){requested.value=false;previousCourseId=id}
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
        if(!['queued','processing'].includes(job.status) && requested.value){
          response=await fetch(`${endpoint}?refresh=true`,{method:'POST',signal:current.signal})
          if(!response.ok)throw new Error(String(response.status))
          job=await response.json()
        }
        if(current.signal.aborted)return
        requested.value=false
        errors=0;status.value=job.status;errorCode.value=job.error??''
        if(job.status==='completed'){result.value=job.result;return}
        if(job.status==='failed'||job.status==='not_requested'&&attempt>=3)return
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
    <button type="button" class="text-link" @click="requested=true;refresh++">{{ result.notes?.length ? '重新生成笔记' : '生成详细学习笔记' }}</button>
    <AiNoteSection v-for="(note,i) in result.notes ?? []" :key="i" :note="note" :course-id="courseId" :depth="1" @seek="emit('seek',$event)" />
  </div>
  <div v-else class="sidebar-empty compact" role="status"><span v-if="['queued','processing'].includes(status)" class="activity-spinner"></span><h3>{{ ['queued','processing'].includes(status)?'正在生成 AI 课程笔记…':status==='failed'?'AI 解读暂未生成':result?.status==='empty'?'暂无可解读内容':'还没有课程解读' }}</h3><p>{{ errorCode==='overview_provider_payment_required'?'模型服务返回余额或额度不足，恢复后可继续生成。':status==='failed'?'本次解读未完成，其他学习功能仍可使用。':ready?'笔记根据导图与课程依据整理，生成期间导图和练习可以继续使用。':'导图生成成功后，将在这里继续整理课程介绍与学习笔记。' }}</p><button v-if="ready && ['not_requested','failed'].includes(status)" type="button" class="secondary" @click="requested=true;refresh++">{{ status==='failed'?'重试生成笔记':'生成课程笔记' }}</button></div>
</template>

<style scoped>
.overview-analysis{margin:0;padding:4px 0;font-size:14px;line-height:1.9;color:#405779;overflow-wrap:anywhere}
</style>
