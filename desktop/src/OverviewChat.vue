<script setup lang="ts">
import MathText from './MathText.vue'
import {ref,watch,onBeforeUnmount,nextTick} from 'vue'
import StudyIcon from './StudyIcon.vue'
import {latestRequests} from './mediaBinding'
type Citation={sourceId:string;startMs:number;endMs:number;quote:string}
type Message={role:'user'|'assistant';content:string;citations?:Citation[]}
const props=defineProps<{courseId:string;overviewReady:boolean;overviewRevision:string;playbackReady:boolean}>()
const emit=defineEmits<{seek:[timeMs:number,sourceId:string]}>()
const messages=ref<Message[]>([]),draft=ref(''),loading=ref(false),sending=ref(false),error=ref(''),contextKey=ref(''),contextMode=ref(''),historyReady=ref(false)
const transcript=ref<HTMLElement|null>(null),requests=latestRequests()
const drafts=new Map<string,string>();let previousCourse='',retryId='',retryText=''
function client(){const key='framewise:study-chat-client:v1';let value=localStorage.getItem(key);if(!value||!/^[a-f0-9-]{36}$/i.test(value)){value=crypto.randomUUID();localStorage.setItem(key,value)}return value}
function problem(code:string){return ({overview_not_completed:'请先等待 AI 解读完成。',overview_context_changed:'课程解读已更新，请重新读取后继续对话。',chat_busy:'正在回答前一个问题，请稍后重试。',chat_limit:'本次课程对话已达到 40 次交流上限。',chat_request_conflict:'请求记录冲突，请修改问题后再试。'} as Record<string,string>)[code]||'暂时无法完成对话，输入已保留，可以重试。'}
async function call(method:string,signal:AbortSignal,body?:unknown){
 const response=await fetch(`http://127.0.0.1:18080/api/transcriptions/${props.courseId}/overview/chat`,{method,signal,headers:{'Content-Type':'application/json','X-Study-Client':client()},body:body?JSON.stringify(body):undefined});const data=await response.json();if(!response.ok)throw new Error(problem(data.error));return data
}
async function scroll(){await nextTick();transcript.value?.scrollTo({top:transcript.value.scrollHeight,behavior:'smooth'})}
async function load(){
 const ticket=requests.begin();loading.value=true;sending.value=false;historyReady.value=false;error.value=''
 try{const data=await call('GET',ticket.signal);if(!ticket.current())return;messages.value=data.messages??[];contextKey.value=data.contextKey??'';contextMode.value=data.contextMode??'';historyReady.value=data.status==='ready';await scroll()}
 catch(e){if(ticket.current())error.value=e instanceof Error?e.message:'无法读取课程对话。'}finally{if(ticket.current())loading.value=false}
}
async function send(){
 const text=draft.value.trim();if(!text||text.length>2000||sending.value||!historyReady.value)return
 if(text!==retryText){retryId=crypto.randomUUID();retryText=text}
 const ticket=requests.begin();sending.value=true;error.value=''
 try{await call('POST',ticket.signal,{contextKey:contextKey.value,requestId:retryId,message:text});if(!ticket.current())return;
  const saved=await call('GET',ticket.signal);if(!ticket.current())return;messages.value=saved.messages??[];contextMode.value=saved.contextMode??contextMode.value;contextKey.value=saved.contextKey??'';historyReady.value=saved.status==='ready';draft.value='';retryId='';retryText='';await scroll()
 }catch(e){if(ticket.current())error.value=e instanceof Error?e.message:'回答未完成，输入已保留。'}finally{if(ticket.current())sending.value=false}
}
watch(()=>[props.courseId,props.overviewReady,props.overviewRevision] as const,([course,ready])=>{
 if(previousCourse!==course){if(previousCourse)drafts.set(previousCourse,draft.value);draft.value=drafts.get(course)||'';previousCourse=course}
 requests.invalidate();messages.value=[];contextKey.value='';historyReady.value=false;loading.value=false;sending.value=false;error.value='';retryId='';retryText=''
 if(course&&ready)void load()
},{immediate:true})
onBeforeUnmount(()=>requests.invalidate())
const time=(ms:number)=>`${Math.floor(ms/60000)}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}`
</script>
<template>
 <section class="panel overview-chat" aria-label="课程对话">
  <header class="chat-heading"><div><h2><StudyIcon name="chat"/>课程对话</h2><p class="chat-intro">接着 AI 解读继续聊，结合本课内容理清疑问。</p></div><span class="chat-context">本课专属对话</span></header>
  <div ref="transcript" class="chat-messages" role="log" aria-label="课程对话记录" aria-live="polite">
   <div v-if="!messages.length" class="chat-empty"><span class="chat-empty-icon"><StudyIcon name="chat"/></span><strong>{{ loading?'正在读取课程对话…':!overviewReady?'AI 解读完成后，就可以继续聊':'这节课哪里还没想明白？' }}</strong><p>{{ overviewReady?'可以请 AI 解释某个步骤，或按照老师的思路再讲一遍。':'先选择课程并完成 AI 解读，对话会沿用它的课程材料。' }}</p></div>
   <article v-for="(message,i) in messages" :key="i" :class="['chat-message',message.role]"><strong>{{ message.role==='user'?'你':'课程助教' }}</strong><p><MathText :text="message.content" /></p><div v-if="message.citations?.length" class="chat-citations"><button v-for="citation in message.citations" :key="citation.sourceId" type="button" :disabled="!playbackReady" @click="emit('seek',citation.startMs,citation.sourceId)">回看 {{ time(citation.startMs) }} · {{ citation.quote }}</button></div></article>
  </div>
  <p v-if="contextMode==='restored'&&historyReady" class="chat-note">本课对话已根据保存的课程材料与 AI 解读恢复上下文。</p>
  <p v-if="sending" role="status">正在结合本课内容回答…</p>
  <p v-if="error" class="chat-error" role="alert">{{ error }} <button type="button" :disabled="sending" @click="load">重新读取</button></p>
  <form @submit.prevent="send"><label for="course-chat-input">你的问题</label><textarea id="course-chat-input" v-model="draft" rows="3" maxlength="2000" :disabled="loading||sending||!historyReady" placeholder="例如：按老师的方法，把这个推导的第二步再讲细一点。"/><div class="chat-actions"><span>{{ draft.length }}/2000</span><button type="submit" :disabled="loading||sending||!historyReady||!draft.trim()">{{ sending?'正在回答…':'发送问题 →' }}</button></div></form>
 </section>
</template>
<style scoped>
 .overview-chat{padding:26px;margin:18px 0 0;border:1px solid #e1e8fa;border-radius:18px;background:var(--panel-background,white);font-size:14px;color:#33486d}
.chat-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.chat-heading h2{margin:0;font-size:17px;color:#20345b}.chat-intro{margin:6px 0 0;font-size:12px;line-height:1.7;color:#667b9d}.chat-context{flex:none;padding:5px 8px;border-radius:6px;background:#f0f4ff;font-size:11px;color:#536fb4}
.chat-messages{display:grid;gap:14px;max-height:420px;overflow:auto;margin:20px 0;padding:2px}.chat-empty{display:grid;justify-items:center;text-align:center;gap:8px;padding:24px 16px;border:1px dashed #cfdbf8;border-radius:12px;background:#f8faff}.chat-empty-icon{display:grid;place-items:center;width:40px;height:40px;background:#eaf0ff;border-radius:12px;color:#4166ed}.chat-empty strong{color:#354f7e;font-size:14px}.chat-empty p{margin:0;line-height:1.8;font-size:12px;color:#6b7c99}
.chat-message{padding:14px;border-radius:12px;border:1px solid #e0e7f5;background:#f5f8ff;min-width:0;margin-right:20px}.chat-message.user{background:#f2edff;border-color:#e4dbf8;margin-left:20px;margin-right:0}.chat-message strong{font-size:12px;color:#526fa5}.chat-message p{margin:8px 0 0;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.9}.chat-citations{display:grid;gap:6px;margin-top:10px}.chat-citations button{text-align:left;font-size:12px;line-height:1.7;padding:8px;border:1px solid #d7e2f9;background:white;border-radius:7px;color:#4166cc;overflow-wrap:anywhere}
.overview-chat form{display:grid;gap:10px}.overview-chat label{font-weight:650;color:#304a79;font-size:13px}.overview-chat textarea{box-sizing:border-box;width:100%;min-width:0;min-height:116px;resize:vertical;border:1px solid #c8d6f8;border-radius:12px;padding:14px;background:#fcfdff;font:inherit;color:inherit;line-height:1.7}.overview-chat textarea:focus{outline:2px solid #91a9ff;outline-offset:2px;border-color:#4166ed}.overview-chat textarea::placeholder{color:#8493ab}
.chat-actions{display:flex;align-items:center;justify-content:space-between;gap:10px}.chat-actions span{font-size:11px;color:#7a8ba7}.chat-actions button{padding:11px 18px;border:0;border-radius:10px;background:#4166ed;color:white;font:inherit;font-size:13px;font-weight:650;cursor:pointer}.chat-actions button:hover:not(:disabled){background:#3054d5}.chat-actions button:focus-visible{outline:3px solid #91a9ff;outline-offset:2px}.chat-note{margin:14px 0 0;font-size:11px;line-height:1.8;color:#7283a0}.chat-error{color:#a44555;font-size:12px;line-height:1.7}button:disabled{opacity:.5;cursor:default}
@media(max-width:600px){.overview-chat{padding:16px}.chat-heading{flex-wrap:wrap}.chat-heading h2{font-size:16px}.chat-message{margin-right:10px}.chat-message.user{margin-left:10px}.chat-empty{padding:20px 12px}}
.chat-heading h2{display:flex;align-items:center;gap:10px;font-size:20px}.chat-heading h2 svg{color:#4166ed;width:22px;height:22px}
</style>
