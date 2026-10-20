<script setup lang="ts">
import { API_ORIGIN } from './apiOrigin' 
import MathText from './MathText.vue'
import { computed, ref, watch, onBeforeUnmount, nextTick } from 'vue'
import StudyIcon from './StudyIcon.vue'
import { resolvePracticeScope } from './practiceScope'
import PracticeScopePicker from './PracticeScopePicker.vue'
import QuestionChat from './QuestionChat.vue'
import PracticeFigure, { type Diagram } from './PracticeFigure.vue'
import { reviewTargets } from './practiceReview'
import type { ReviewCitation } from './practiceReview'
type Node={id:string;title:string;children?:Node[];details?:Node[]}
type Question={id:string;nodeTitle:string;kind:string;title:string;prompt:string;options:string[];diagram?:Diagram|null;scenario?:string}
type Citation=ReviewCitation
type Feedback={questionId:string;selectedIndex:number;answerIndex:number;correct:boolean;explanation:string;takeaway:string;selectedReason:string;citations:Citation[]}
type SetData={id:string;title:string;status:string;error?:string;questions?:Question[];rejectedCount?:number;practiceMode?:string;historyRounds?:number;historyQuestions?:number}
const props=defineProps<{courseId?:string;hasMedia?:boolean;playbackReady?:boolean;mindMap?:{root:Node}|null;selectedNodeId?:string;ready?:boolean}>()
const emit=defineEmits<{seek:[timeMs:number,sourceId:string]}>()
const base=API_ORIGIN + '/api/transcriptions'
const clientKey='videostudy:practice-client'
let client=localStorage.getItem(clientKey)
if(!client){client=crypto.randomUUID();localStorage.setItem(clientKey,client)}
const count=ref(0), difficulty=ref('basic'), scope=ref('')

const practiceMode=ref<'map_context'|'related_materials'>('related_materials')
const practiceModes=[{value:'map_context',label:'整课导图资料'},{value:'related_materials',label:'当前范围资料'}] as const
const practiceError=(code?:string)=>({practice_provider_invalid_json:'模型返回的题目格式无法读取，可重新生成。',practice_format_repair_failed:'题目格式已尝试自动修复一次，仍未通过检查，可重新生成。',practice_map_context_missing:'这门课未保存导图上下文，请重新生成导图，或选择相关资料出题。',practice_map_context_changed:'导图或原图已变化，请重新生成导图后再沿用上下文。',practice_images_missing:'所需课件截图缺失，请恢复课程资料或重新分析；本次未裁减图片出题。',practice_images_invalid:'图片来源无法核对，请检查课程资料。',practice_evidence_missing:'缺少有效课程依据，请检查导图与原始资料。',practice_context_too_large:'模型拒绝了过大的图片或上下文请求；可以缩小范围或改用相关资料出题，本次未自动裁减。',practice_provider_rejected:'模型服务不接受这次请求，请核对多图支持和上下文限制。',practice_provider_payment_required:'模型服务余额或额度不足，请恢复后重试。'}[code??''] ?? '出题失败，请重试。')
const sets=ref<SetData[]>([]), active=ref<SetData|null>(null), session=ref(''), index=ref(0)
const feedback=ref<Record<string,Feedback>>({}), busy=ref(false), pending=ref(false), error=ref('')
const chartDialog=ref<HTMLDialogElement|null>(null)
let epoch=0, timer:ReturnType<typeof setTimeout>|undefined
const showDemo=ref(false)
const demo=computed(()=>showDemo.value&&!props.courseId&&!props.hasMedia)
watch(()=>props.hasMedia,()=>{showDemo.value=false})
const sample:Question[]=[
 {id:'demo-1',nodeTitle:'增长量与增长率',kind:'single',title:'增长量',prompt:'体重从 160 斤增加到 192 斤，增长量是多少？',options:['20%','32 斤','160 斤','192 斤'],scenario:'adapted'},
 {id:'demo-2',nodeTitle:'增长量与增长率',kind:'single',title:'图表应用',prompt:'根据图表，2025 年销量比 2024 年增长了百分之多少？',options:['16.7%','20%','25%','30%'],scenario:'adapted',diagram:{kind:'bar',title:'某商店销量（示例数据）',unit:'万件',values:[{label:'2023 年',value:120},{label:'2024 年',value:150},{label:'2025 年',value:180}]}},
]
const questions=computed(()=>demo.value?sample:active.value?.questions??[])
const question=computed(()=>questions.value[index.value])
const current=computed(()=>question.value?feedback.value[question.value.id]:undefined)
const reviewCard=ref<HTMLElement|null>(null)
const chatOpen=ref(false)
const targets=computed(()=>current.value&&!current.value.correct&&question.value
  ?reviewTargets(current.value.citations,question.value.nodeTitle,current.value.takeaway,current.value.selectedReason):[])
const preferredTarget=computed(()=>targets.value[0])
const wrongQuestions=computed(()=>questions.value.map((q,i)=>({question:q,index:i})).filter(item=>feedback.value[item.question.id]?.correct===false))
async function openWrongQuestion(i:number){index.value=i;await nextTick();reviewCard.value?.scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'})}
const answered=computed(()=>questions.value.filter(q=>feedback.value[q.id]).length)
const correct=computed(()=>questions.value.filter(q=>feedback.value[q.id]?.correct).length)
const letters=['A','B','C','D']
watch([index,session,active],()=>{chatOpen.value=false;chartDialog.value?.close()})
watch(()=>props.selectedNodeId,id=>{if(id)scope.value=resolvePracticeScope(props.mindMap?.root,id)})
watch(()=>props.mindMap?.root,root=>{scope.value=resolvePracticeScope(root,props.selectedNodeId||scope.value)})
async function api(path:string,method='GET',body?:unknown,course=props.courseId){
 const response=await fetch(`${base}/${course}/practice${path}`,{method,headers:{'Content-Type':'application/json','X-Practice-Client':client!},body:body===undefined?undefined:JSON.stringify(body)})
 if(!response.ok)throw new Error('请求未完成，请稍后重试。')
 return response.json()
}
async function restore(set:SetData,version=epoch){
 if(version!==epoch)return
 busy.value=true
 const course=props.courseId
 const loaded=await api(`/${set.id}`,'GET',undefined,course)
 if(version!==epoch)return
 active.value=loaded;index.value=0;feedback.value={};session.value=''
 if(loaded.status==='completed'&&loaded.questions?.length){
   const data=await api(`/${set.id}/sessions`,'POST',{fresh:false},course)
   if(version!==epoch)return
   session.value=data.id;feedback.value=Object.fromEntries(data.feedback.map((f:Feedback)=>[f.questionId,f]))
   index.value=Math.max(0,loaded.questions.findIndex((q:Question)=>!feedback.value[q.id]))
   busy.value=false
 }else if(['queued','processing'].includes(loaded.status)){busy.value=true;poll(set.id,version,course!,Date.now())}
 else {busy.value=false;if(loaded.status==='failed')error.value=practiceError(loaded.error);else if(loaded.status==='completed')error.value='本次未生成有效题目，请点击重新生成重试。'}
}
async function refresh(version:number){
 try{const data=await api('');if(version!==epoch)return;sets.value=data;if(data[0])await restore(data[0],version)}
 catch{if(version===epoch){busy.value=false;error.value='暂时无法读取已保存的练习。'}}
}
watch(()=>props.courseId,()=>{epoch++;if(timer)clearTimeout(timer);busy.value=false;pending.value=false;active.value=null;sets.value=[];feedback.value={};index.value=0;error.value='';scope.value='';session.value='';showDemo.value=false;if(props.courseId)void refresh(epoch)}, {immediate:true})
onBeforeUnmount(()=>{epoch++;if(timer)clearTimeout(timer)})
function poll(id:string,version:number,course:string,started:number){
 timer=setTimeout(async()=>{
   if(version!==epoch)return
   try{
     const set=await api(`/${id}`,'GET',undefined,course);if(version!==epoch)return;active.value=set
     if(['queued','processing'].includes(set.status)){
       if(Date.now()-started>15*60*1000){busy.value=false;error.value='生成仍在后台进行，可稍后重新打开查看。';return}
       poll(id,version,course,started);return
     }
     if(set.status==='failed'){busy.value=false;error.value=practiceError(set.error);return}
     await restore(set,version);sets.value=await api('','GET',undefined,course)
   }catch{if(version===epoch){busy.value=false;error.value='暂时无法获取出题进度，可重新打开查看。'}}
 },1500)
}
async function generate(){
 const version=epoch,course=props.courseId!;busy.value=true;error.value='';session.value=''
 try{const set=await api('','POST',{nodeId:scope.value||null,count:count.value,difficulty:difficulty.value,retry:true,mode:practiceMode.value},course);if(version!==epoch)return;active.value=set;feedback.value={};index.value=0
   if(['queued','processing'].includes(set.status))poll(set.id,version,course,Date.now());else await restore(set,version)
 }catch{if(version===epoch){busy.value=false;error.value='暂时无法出题，请确认思维导图已经生成。'}}
}
async function choose(choice:number){
 const q=question.value;if(!q||current.value||pending.value||busy.value)return
 if(demo.value){const answer=1;feedback.value[q.id]={questionId:q.id,selectedIndex:choice,answerIndex:answer,correct:choice===answer,explanation:q.id==='demo-1'?'增长量＝192－160＝32 斤。20% 是增长率。':'增长率＝（180－150）÷150×100%＝20%。',takeaway:'增长量表示增加的数量；增长率的分母是基期量。',selectedReason:choice===answer?'':'注意区分数量与比例，并选对基期。',citations:[]};return}
 const version=epoch,setId=active.value!.id,sessionId=session.value,course=props.courseId!
 pending.value=true;error.value=''
 try{const f=await api(`/${setId}/sessions/${sessionId}/answers`,'POST',{questionId:q.id,selectedIndex:choice},course);if(version===epoch&&active.value?.id===setId&&session.value===sessionId)feedback.value[q.id]=f}
 catch{if(version===epoch)error.value='答案未保存，请再点一次选项。'}finally{if(version===epoch)pending.value=false}
}
async function reset(){
 if(demo.value){feedback.value={};index.value=0;return}
 const version=epoch,setId=active.value!.id;pending.value=true
 try{const data=await api(`/${setId}/sessions`,'POST',{fresh:true});if(version!==epoch)return;session.value=data.id;feedback.value={};index.value=0}catch{if(version===epoch)error.value='未能创建新一轮练习。'}finally{if(version===epoch)pending.value=false}
}
async function switchSet(id:string){if(busy.value||pending.value)return;epoch++;error.value='';try{await restore(sets.value.find(s=>s.id===id)!,epoch)}catch{busy.value=false;error.value='暂时无法读取练习。'}}
const time=(ms:number)=>`${Math.floor(ms/60000).toString().padStart(2,'0')}:${Math.floor(ms/1000)%60<10?'0':''}${Math.floor(ms/1000)%60}`
</script>
<template>
 <div class="practice">
  <div class="practice-heading"><div><span class="eyebrow">LEARN BY DOING</span><h3>AI 练习</h3></div><span class="practice-demo">{{ demo?'静态演示':courseId?'知识点练习':'未选择课程' }}</span></div>
  <p class="practice-intro">点击选项，立即查看对错与解析。</p>
  <div v-if="courseId&&!demo" class="practice-mode-options" role="group" aria-label="出题参考资料">
   <span>参考资料</span><button v-for="mode in practiceModes" :key="mode.value" type="button" :aria-pressed="practiceMode===mode.value" :disabled="busy||pending" @click="practiceMode=mode.value">{{ mode.label }}</button>
  </div>
  <p v-if="courseId&&!demo" class="practice-intro">{{ practiceMode==='map_context'?'参考生成导图时的整课资料和导图，按选定范围出题。':'参考选定范围的知识点、相关例题原图和讲解出题。' }}</p>
  <p v-if="courseId&&!demo" class="practice-intro">同一课程连续出题，会参考已出的题尽量避免重复；这两个选项只决定参考资料范围。每道题的答疑分别保存。</p>
  <p v-if="active?.historyRounds" class="practice-intro">本次已参考 {{ active.historyRounds }} 轮出题历史，共 {{ active.historyQuestions }} 道题。</p>
  <button v-if="!courseId&&!hasMedia" type="button" class="practice-secondary" @click="showDemo=!showDemo;feedback={};index=0">{{ demo?'关闭示例题':'查看示例题' }}</button>
  <div v-if="courseId&&!demo" class="practice-settings">
   <PracticeScopePicker v-model="scope" :root="mindMap?.root" :disabled="busy||pending"/>
   <label>题量<select v-model.number="count" :disabled="busy"><option :value="0">智能推荐</option><option v-for="n in [3,5,10]" :key="n" :value="n">{{ n }} 道</option></select></label>
   <label>难度<select aria-label="难度" v-model="difficulty" :disabled="busy||pending"><option value="basic">基础巩固</option><option value="application">应用练习</option><option value="advanced">进阶挑战</option></select></label>
   <button class="practice-primary" type="button" :disabled="busy||pending||!ready||!mindMap" @click="generate">{{ busy?'正在出题…':active&&(active.status==='failed'||(active.status==='completed'&&!questions.length))?'重新生成':'生成练习' }}</button>
  </div>

  <label v-if="sets.length" class="saved-set">已保存的练习<select :value="active?.id" :disabled="busy||pending" @change="switchSet(($event.target as HTMLSelectElement).value)"><option v-for="set in sets" :key="set.id" :value="set.id">{{ set.title }} · {{ set.status==='completed'?'已生成':set.status==='failed'?'失败':'生成中' }} · {{ set.id.slice(0,6) }}</option></select></label>
  <p v-if="error" class="practice-error" role="alert">{{ error }}</p>
  <p v-if="busy" class="practice-intro" role="status">正在根据知识点出题并检查答案，完成后自动显示。</p>
  <div v-else-if="!questions.length" class="practice-empty">{{ !courseId&&!hasMedia?'请先选择并分析视频，或从历史记录打开课程，随后显示对应练习。':active?.status==='failed'?'本次出题失败，可点击重新生成重试。':active?.status==='completed'?'本次没有通过检查的题目，可点击重新生成，或调整范围和难度后再试。':!mindMap?'分析完成并生成思维导图后，就可以练习。':'选择范围、题量和难度，生成本课练习。' }}</div>
  <template v-if="questions.length&&question&&!busy">
   <div class="practice-course"><span class="practice-course-icon"><StudyIcon name="practice"/></span><div><strong>{{ demo?'增长量与增长率':active?.title }}</strong><span>{{ questions.length }} 道题 · 按知识点生成 · 选择后自动判分</span></div></div>
   <p v-if="active?.rejectedCount" class="practice-intro">{{ active.rejectedCount }} 道题未通过检查，已剔除。</p>
   <div class="practice-progress"><span>已完成 {{ answered }} / {{ questions.length }} 题</span><span>答对 {{ correct }} 题</span></div>
   <div class="practice-track" role="progressbar" aria-label="练习完成进度" :aria-valuenow="answered" :aria-valuemin="0" :aria-valuemax="questions.length"><span :style="{width:`${answered/questions.length*100}%`}"/></div>
   <nav class="practice-steps" aria-label="选择题目"><button v-for="(q,i) in questions" :key="q.id" type="button" :disabled="pending" :class="{current:index===i,done:!!feedback[q.id]}" :aria-current="index===i?'step':undefined" @click="index=i">{{ String(i+1).padStart(2,'0') }}<span>{{ feedback[q.id]?'已答':'待答' }}</span></button></nav>
   <article :key="question.id" class="practice-question">
    <div class="practice-question-meta"><span>第 {{ index+1 }} 题 · {{ question.kind==='true_false'?'判断':'单选' }}</span><span>{{ question.nodeTitle }}</span><span>{{ question.scenario==='adapted'?'应用题 · 设定数据':'课程知识题' }}</span></div>
    <fieldset><legend><MathText :text="question.prompt" /></legend>
     <figure v-if="question.diagram" class="practice-figure"><PracticeFigure :diagram="question.diagram"/><figcaption><span>按题目条件绘制 · 可放大查看</span><button type="button" @click="chartDialog?.showModal()">放大查看 ↗</button></figcaption></figure>
     <label v-for="(option,i) in question.options" :key="i" class="practice-option" :class="{selected:current?.selectedIndex===i,correct:current?.answerIndex===i,incorrect:current?.selectedIndex===i&&!current.correct}"><input type="radio" :name="`practice-${question.id}`" :checked="current?.selectedIndex===i" :disabled="pending||!!current||(!demo&&!session)" @click="choose(i)"/><span class="practice-letter">{{ letters[i] }}</span><span><MathText :text="option" /></span><span v-if="current?.answerIndex===i" class="practice-option-note">正确答案</span><span v-else-if="current?.selectedIndex===i" class="practice-option-note">你的选择</span></label>
    </fieldset>
    <p v-if="pending" role="status">正在保存答案…</p>
    <div v-if="current" class="practice-feedback" :class="{'needs-review':!current.correct}" role="status"><strong>{{ current.correct?'答对了':'答错了，看看解题思路' }}</strong><h4>答案解析</h4><p><MathText :text="current.explanation" /></p><p v-if="current.selectedReason" class="choice-reason">你的选项：<MathText :text="current.selectedReason" /></p><div class="practice-takeaway"><StudyIcon name="spark"/><span><MathText :text="current.takeaway" /></span></div><section v-if="!current.correct" ref="reviewCard" class="practice-review" aria-label="错题精准回看">
      <div class="review-heading"><StudyIcon name="play"/><strong>错题精准回看</strong></div>
      <p class="review-knowledge">复习知识点：{{ question.nodeTitle }}</p>
      <template v-if="preferredTarget">
       <p class="review-hint">{{ preferredTarget.matched?'优先回看与该知识点、解法更相关的课程原句。':'现有引用不足以区分哪一段最相关，先查看以下课程依据。' }}</p>
       <blockquote>{{ preferredTarget.quote }}</blockquote>
       <button class="review-play" type="button" :disabled="!playbackReady" @click="emit('seek',preferredTarget.startMs,preferredTarget.sourceId)"><StudyIcon name="play"/>回看讲解 {{ time(preferredTarget.startMs) }}<span v-if="preferredTarget.endMs">～{{ time(preferredTarget.endMs) }}</span></button>
       <p v-if="!playbackReady" class="review-hint">请先选择指纹匹配的本地原视频，再回放这一段。</p>
       <details v-if="targets.length>1" class="review-other"><summary>其他相关讲解（{{ targets.length-1 }} 段）</summary><button v-for="ref in targets.slice(1)" :key="ref.sourceId" type="button" :disabled="!playbackReady" @click="emit('seek',ref.startMs,ref.sourceId)">{{ time(ref.startMs) }} · {{ ref.quote }}</button></details>
      </template>
      <p v-else class="review-hint">{{ demo?'示例题没有对应视频片段。':'这道题暂时没有可用的课程时间依据，无法精准定位；可以先复习上面的解法。' }}</p>
     </section><div v-if="current.correct" class="practice-citations"><button v-for="ref in current.citations" :key="ref.sourceId" type="button" @click="emit('seek',ref.startMs,ref.sourceId)">回看 {{ time(ref.startMs) }} · {{ ref.quote }}</button></div></div>
    <section v-if="current&&!demo&&courseId&&active&&session" class="practice-chat-entry">
     <button class="practice-chat-toggle" type="button" :aria-expanded="chatOpen" :aria-controls="`question-chat-${question.id}`" @click="chatOpen=!chatOpen">
      <span class="practice-chat-icon"><StudyIcon name="chat"/></span>
      <span class="practice-chat-copy"><strong>本题答疑 <span>AI 助教</span></strong><small>看不懂解析？聊聊你的解题思路</small></span>
      <span class="practice-chat-action">{{ chatOpen?'收起':'打开答疑' }} <span aria-hidden="true">{{ chatOpen?'⌃':'⌄' }}</span></span>
     </button>
     <QuestionChat v-if="chatOpen" :id="`question-chat-${question.id}`" :key="`${courseId}:${active.id}:${question.id}:${session}`" :course-id="courseId" :set-id="active.id" :question-id="question.id" :session-id="session" :client="client!" :playback-ready="playbackReady" @seek="(ms,id)=>emit('seek',ms,id)"/>
    </section>
    <div class="practice-actions"><button class="practice-secondary" type="button" :disabled="index===0||pending" @click="index--">上一题</button><button v-if="index<questions.length-1" class="practice-primary" type="button" :disabled="pending" @click="index++">下一题 →</button><button v-else class="practice-secondary" type="button" :disabled="pending" @click="reset">重新练习</button></div>
   </article>
   <div v-if="answered===questions.length" class="practice-summary" role="status"><StudyIcon name="practice"/><div><strong>本轮完成 · {{ correct }} / {{ questions.length }} 题正确</strong><p>{{ wrongQuestions.length ? `本轮有 ${wrongQuestions.length} 道错题，可以按知识点回看讲解。` : '本轮全部答对，可以尝试更有挑战的练习。' }}</p><div v-if="wrongQuestions.length" class="review-wrong-list"><button v-for="item in wrongQuestions" :key="item.question.id" type="button" @click="openWrongQuestion(item.index)">第 {{ item.index+1 }} 题 · {{ item.question.nodeTitle }} <span>查看错题 →</span></button></div></div></div>
   <dialog ref="chartDialog" class="practice-chart-dialog" aria-label="放大的题目图表" @click="($event.target===chartDialog)&&chartDialog?.close()"><div class="practice-dialog-header"><strong>题目图表</strong><button type="button" @click="chartDialog?.close()">关闭 ×</button></div><PracticeFigure v-if="question.diagram" :diagram="question.diagram"/></dialog>
  </template>
  <p class="practice-disclaimer">{{ demo?'当前为固定示例，不保存成绩。':'题目与答题记录关联本次解析并保存。再次练习不重复调用 AI；删除解析时一并删除。' }} AI 题目仍可能存在理解偏差，请结合课程依据判断。</p>
 </div>
</template>
<style scoped src="./AiPractice.css">
.practice-question legend{box-sizing:border-box;width:100%;max-width:100%;min-width:0}.practice-option>span:nth-of-type(2){flex:1;min-width:0}.practice-steps{flex-wrap:wrap}
</style>
<style scoped>
.practice-chat-entry{margin-top:22px;border:1px solid #bdccfb;border-radius:16px;overflow:hidden;background:#f7f9ff;box-shadow:0 5px 18px #4166ed0b}
.practice-chat-toggle{display:flex;align-items:center;gap:13px;width:100%;padding:18px;text-align:left;border:0;background:linear-gradient(115deg,#eaf0ff,#f6f3ff);color:#254aab;cursor:pointer;font:inherit}
.practice-chat-toggle:hover{background:#e5edff}.practice-chat-toggle:focus-visible{outline:3px solid #4166ed;outline-offset:-3px}
.practice-chat-icon{display:grid;place-items:center;flex:none;width:44px;height:44px;border-radius:13px;background:#4166ed;color:white}.practice-chat-icon svg{width:24px;height:24px}
.practice-chat-copy{flex:1;min-width:0}.practice-chat-copy strong{display:flex;align-items:center;gap:9px;font-size:16px;color:#203764}.practice-chat-copy strong span{padding:3px 7px;border-radius:6px;background:#fff;color:#536cb6;font-size:10px;font-weight:600}.practice-chat-copy small{display:block;margin-top:5px;line-height:1.6;font-size:12px;color:#5f7297}
.practice-chat-action{flex:none;font-size:12px;font-weight:700;color:#355dd8}.practice-chat-action span{margin-left:5px}
@media(max-width:600px){.practice-chat-toggle{gap:10px;padding:14px}.practice-chat-icon{width:36px;height:36px}.practice-chat-copy strong{font-size:14px}.practice-chat-copy small{font-size:11px}.practice-chat-action{font-size:11px}}

.practice-review{margin-top:18px;padding:16px;border:1px solid #d8e1ff;border-radius:12px;background:linear-gradient(130deg,#edf3ff,#f8f5ff)}.review-heading{display:flex;align-items:center;gap:8px;color:#3759ca;font-size:14px}.review-heading svg{width:17px;height:17px}.practice-review .review-knowledge{margin-top:10px;color:#25395f;font-weight:650}.practice-review .review-hint{margin-top:8px;font-size:12px;color:#62749a}.practice-review blockquote{margin:12px 0;padding:10px 13px;border-left:3px solid #9cb3f7;background:#ffffffb0;font-size:13px;line-height:1.8;color:#405779;white-space:pre-wrap}.review-play{display:flex;align-items:center;justify-content:center;gap:6px;flex-wrap:wrap;width:100%;padding:12px;border:0;border-radius:9px;background:#4166ed;color:white;font-size:13px;font-weight:650}.review-play svg{width:15px;height:15px}.review-other{margin-top:12px;font-size:12px;color:#526998}.review-other button{display:block;width:100%;margin-top:8px;padding:9px;border:1px solid #dce6ff;border-radius:7px;background:white;color:#4166cc;text-align:left;font-size:12px;line-height:1.7}.review-wrong-list{display:grid;gap:8px;margin-top:12px}.review-wrong-list button{padding:10px;border:1px solid #e0dafa;border-radius:8px;background:#fff;color:#6850b2;text-align:left;font-size:12px;line-height:1.7}.review-wrong-list button span{display:block;font-size:11px}.practice-summary>div{min-width:0;flex:1}
.practice-settings{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:16px;background:#f5f8ff;border:1px solid #e0e7fb;border-radius:13px;margin-bottom:18px}.practice-settings label,.saved-set{display:grid;gap:7px;font-size:12px;color:#53698f}.practice-settings select,.saved-set select{min-width:0;width:100%;padding:10px;border:1px solid #dce4f7;border-radius:8px;background:#fff;color:#25395f}.practice-settings .practice-primary{justify-content:center;align-self:end;padding:12px;border-radius:9px}.saved-set{margin-bottom:16px}.practice-empty{padding:30px 20px;background:#f7faff;border:1px dashed #d6e2fb;border-radius:12px;color:#62779c;font-size:13px;line-height:1.8}.practice-error{padding:12px;background:#fff4f3;color:#a44555;border-radius:8px;font-size:13px}.choice-reason{margin-top:12px!important}.practice-citations{display:grid;gap:8px;margin-top:14px}.practice-citations button{text-align:left;padding:10px;border:1px solid #dce6ff;background:#fff;border-radius:8px;color:#4166cc;font-size:12px;line-height:1.8}button:disabled{opacity:.5;cursor:default}fieldset:disabled label{cursor:default}

.practice-question legend{box-sizing:border-box;width:100%;max-width:100%;min-width:0}.practice-option>span:nth-of-type(2){flex:1;min-width:0}.practice-steps{flex-wrap:wrap}
</style>
