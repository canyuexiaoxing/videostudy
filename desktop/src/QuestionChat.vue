<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { latestRequests } from './mediaBinding'
import type { ReviewCitation } from './practiceReview'
type Message={role:'user'|'assistant';content:string;citations?:ReviewCitation[]}
const props=defineProps<{courseId:string;setId:string;questionId:string;sessionId:string;client:string;playbackReady?:boolean}>()
const emit=defineEmits<{seek:[timeMs:number,sourceId:string]}>()
const messages=ref<Message[]>([]), draft=ref(''), loading=ref(true), sending=ref(false), error=ref('')
const transcript=ref<HTMLElement|null>(null)
const requests=latestRequests()
const historyReady=ref(false)
let retryId='', retryText=''
const url=`http://127.0.0.1:18080/api/transcriptions/${props.courseId}/practice/${props.setId}/questions/${props.questionId}/chat`
function problem(code:string){
 return ({chat_busy:'这道题的答疑正在处理，请稍后重试。',chat_limit:'本题已达到 20 次交流上限。',answer_required:'请先完成本题作答。',chat_provider_failed:'答疑暂时未完成，输入已保留，可以重试。',chat_request_conflict:'请求记录有冲突，请修改问题后再试。'} as Record<string,string>)[code]??'暂时无法读取答疑，请稍后重试。'
}
async function call(method:string,signal:AbortSignal,body?:unknown){
 const response=await fetch(method==='GET'?`${url}?sessionId=${encodeURIComponent(props.sessionId)}`:url,
  {method,signal,headers:{'Content-Type':'application/json','X-Practice-Client':props.client},body:body?JSON.stringify(body):undefined})
 const data=await response.json()
 if(!response.ok)throw new Error(problem(data.error))
 return data
}
async function scroll(){await nextTick();transcript.value?.scrollTo({top:transcript.value.scrollHeight,behavior:'auto'})}
async function load(){
 const ticket=requests.begin();loading.value=true;historyReady.value=false;error.value=''
 try{const data=await call('GET',ticket.signal);if(ticket.current()){messages.value=data;historyReady.value=true;await scroll()}}
 catch(e){if(ticket.current())error.value=e instanceof Error?e.message:'无法读取答疑记录。'}
 finally{if(ticket.current())loading.value=false}
}
async function send(){
 const text=draft.value.trim();if(!text||text.length>2000||sending.value||loading.value||!historyReady.value)return
 if(text!==retryText){retryId=crypto.randomUUID();retryText=text}
 const ticket=requests.begin();sending.value=true;error.value=''
 try{
  const data=await call('POST',ticket.signal,{sessionId:props.sessionId,requestId:retryId,message:text})
  if(!ticket.current())return
  const saved=await call('GET',ticket.signal)
  if(!ticket.current())return
  messages.value=saved;historyReady.value=true
  draft.value='';retryId='';retryText='';await scroll()
 }catch(e){if(ticket.current())error.value=e instanceof Error?e.message:'答疑暂时未完成，输入已保留。'}
 finally{if(ticket.current())sending.value=false}
}
const time=(ms:number)=>`${Math.floor(ms/60000)}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}`
onMounted(load)
onBeforeUnmount(()=>requests.invalidate())
</script>
<template>
 <section class="question-chat" aria-label="本题答疑">
  <p class="chat-intro">围绕这道题提问，或写下你的解题思路。答疑会参考本题知识点和已保存的相关课程分析。</p>
  <p v-if="loading" role="status">正在读取本题对话…</p>
  <div ref="transcript" class="chat-messages" role="log" aria-label="本题对话记录" aria-live="polite">
   <p v-if="!loading&&!messages.length" class="chat-empty">本题还没有对话。可以问“为什么我的选项不对？”或解释你是怎么计算的。</p>
   <article v-for="(message,i) in messages" :key="i" :class="['chat-message',message.role]">
    <strong>{{ message.role==='user'?'你':'本题助教' }}</strong><p>{{ message.content }}</p>
    <div v-if="message.citations?.length" class="chat-citations"><button v-for="citation in message.citations" :key="citation.sourceId" type="button" :disabled="!playbackReady" @click="emit('seek',citation.startMs,citation.sourceId)">回看 {{ time(citation.startMs) }} · {{ citation.quote }}</button></div>
   </article>
  </div>
  <p v-if="!playbackReady&&messages.some(m=>m.citations?.length)" class="chat-note">选择指纹匹配的本地原视频后，可以回放引用。</p>
  <p v-if="sending" role="status">正在结合本题与课程依据回答…</p>
  <p v-if="error" class="chat-error" role="alert">{{ error }} <button v-if="!sending" type="button" @click="load">重新读取</button></p>
  <form @submit.prevent="send"><label :for="`chat-${questionId}`">你的问题或解题思路</label><textarea :id="`chat-${questionId}`" v-model="draft" rows="3" maxlength="2000" :disabled="loading||sending" placeholder="例如：我用了现期作分母，这一步为什么不对？"/><div class="chat-actions"><span>{{ draft.length }}/2000</span><button type="submit" :disabled="loading||sending||!historyReady||!draft.trim()">{{ sending?'正在回答…':'发送' }}</button></div></form>
  <p class="chat-note">每道题单独保存对话，重做同题保留记录。发送会调用 AI；引用可追溯不等于回答一定正确，请结合原课核实。</p>
 </section>
</template>
<style scoped>
.question-chat{margin-top:12px;font-size:13px;color:#33486d}.chat-intro,.chat-note,.chat-empty{font-size:12px;line-height:1.7;color:#6b7c99}.chat-messages{display:grid;gap:12px;max-height:420px;overflow:auto;margin:14px 0;padding:2px}.chat-message{padding:12px;border-radius:10px;border:1px solid #e0e7f5;background:#f5f8ff;min-width:0}.chat-message.user{background:#f2edff;border-color:#e4dbf8;margin-left:18px}.chat-message strong{font-size:11px;color:#61779c}.chat-message p{margin:7px 0 0;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8}.chat-citations{display:grid;gap:6px;margin-top:10px}.chat-citations button{text-align:left;font-size:12px;line-height:1.7;padding:8px;border:1px solid #d7e2f9;background:white;border-radius:7px;color:#4166cc;overflow-wrap:anywhere}.question-chat form{display:grid;gap:7px}.question-chat textarea{box-sizing:border-box;width:100%;min-width:0;resize:vertical;border:1px solid #d9e2f4;border-radius:9px;padding:10px;background:white;font:inherit;color:inherit}.chat-actions{display:flex;align-items:center;justify-content:space-between}.chat-actions span{font-size:11px;color:#8795ad}.chat-actions button{padding:9px 20px;border:0;border-radius:8px;background:#4166ed;color:white}.chat-note{margin-top:12px}.chat-error{color:#a44555;font-size:12px;line-height:1.7}button:disabled{opacity:.5;cursor:default}
</style>
