<script setup lang="ts">
import {computed,onMounted,onUnmounted,reactive,ref,watch} from 'vue'
import NoteImage from './NoteImage.vue'
import NoteAnnotationDialog from './NoteAnnotationDialog.vue'
import {NoteStorage} from './noteStorage'
import type {StudyNote} from './noteStorage'
import type {NoteAnnotation} from './noteDrawing'
const props=defineProps<{scopes:string[];video:HTMLVideoElement|null;timeMs:number}>(),emit=defineEmits<{seek:[time:number]}>()
type Draft={text:string;image?:Blob;annotation?:NoteAnnotation;timeMs?:number;editingId?:string}
const drafts=reactive<Record<string,Draft>>({}),notes=ref<StudyNote[]>([]),error=ref(''),loading=ref(true),saving=ref(false),capturing=ref(false)
let store=new NoteStorage(),initializing:Promise<void>=Promise.resolve(),disposed=false
const scope=computed(()=>props.scopes[0]||''),draft=computed(()=>{if(!drafts[scope.value])drafts[scope.value]={text:''};return drafts[scope.value]!})
const visible=computed(()=>notes.value.filter(n=>props.scopes.includes(n.scope)).sort((a,b)=>b.createdAt.localeCompare(a.createdAt)))
const annotation=ref<{scope:string;document:NoteAnnotation;timeMs:number}|null>(null)
const mediaReady=ref(false)
function syncMediaReady(){mediaReady.value=!!props.video&&props.video.readyState>=2&&!props.video.seeking}
watch(()=>props.video,(media,previous)=>{
 for(const event of ['loadeddata','canplay','seeking','seeked','emptied']){previous?.removeEventListener(event,syncMediaReady);media?.addEventListener(event,syncMediaReady)}
 syncMediaReady()
},{immediate:true})
onUnmounted(()=>{for(const event of ['loadeddata','canplay','seeking','seeked','emptied'])props.video?.removeEventListener(event,syncMediaReady)})
const canCapture=computed(()=>!!scope.value&&mediaReady.value)
const time=(ms:number)=>new Date(Math.max(0,ms)).toISOString().slice(11,19)
function diagnostic(stage:string,start:number,cause:unknown){console.warn('[Framewise notes]',{task:scope.value||'local',stage,result:'failed',elapsedMs:Math.round(performance.now()-start),errorType:cause instanceof Error?cause.name:'unknown'})}
async function load(){loading.value=true;error.value='';const start=performance.now();try{await store.migrateLegacy();const rows=await store.all();if(!disposed)notes.value=rows}catch(cause){error.value='本机笔记暂时无法读取，请重试。';diagnostic('load',start,cause)}finally{loading.value=false}}
function retry(){void store.close().catch(()=>{});store=new NoteStorage();initializing=load()}
onMounted(()=>{initializing=load()});onUnmounted(()=>{disposed=true;void store.close().catch(()=>{})})
watch(scope,()=>{annotation.value=null;error.value=''})
async function save(){
 const current=draft.value,target=scope.value;if(!target||loading.value||saving.value||(!current.text.trim()&&!current.image))return
 saving.value=true;error.value='';const start=performance.now(),id=current.editingId||crypto.randomUUID()
 const old=notes.value.find(n=>n.id===id),note:StudyNote={id,scope:old?.scope||target,text:current.text.trim(),timeMs:current.timeMs??props.timeMs,createdAt:old?.createdAt||new Date().toISOString(),image:current.image,annotation:current.annotation}
 try{await store.put(note);notes.value=[note,...notes.value.filter(n=>n.id!==id)];current.text='';delete current.image;delete current.annotation;delete current.timeMs;delete current.editingId}
 catch(cause){error.value='保存失败，文字和图片仍保留在草稿中。请检查本机存储空间后重试。';diagnostic('save',start,cause)}finally{saving.value=false}
}
async function remove(note:StudyNote){if(saving.value)return;error.value='';try{await store.remove(note.id);notes.value=notes.value.filter(n=>n.id!==note.id);if(draft.value.editingId===note.id)cancelEdit()}catch{error.value='删除失败，笔记仍然保留，请重试。'}}
function edit(note:StudyNote){drafts[scope.value]={text:note.text,image:note.image,annotation:note.annotation,timeMs:note.timeMs,editingId:note.id}}
function cancelEdit(){drafts[scope.value]={text:''}}
async function capture(){
 const media=props.video,target=scope.value;if(!media||!target||media.readyState<2||media.seeking||capturing.value)return
 capturing.value=true;error.value='';const start=performance.now(),at=Math.round(media.currentTime*1000);media.pause()
 try{const canvas=document.createElement('canvas'),scale=Math.min(1,2560/Math.max(media.videoWidth,media.videoHeight));canvas.width=Math.round(media.videoWidth*scale);canvas.height=Math.round(media.videoHeight*scale);canvas.getContext('2d')!.drawImage(media,0,0,canvas.width,canvas.height);const blob=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('capture_failed')),'image/png'));if(target===scope.value)annotation.value={scope:target,document:{base:blob,strokes:[]},timeMs:at}}
 catch(cause){error.value='当前画面无法截图，请稍后重试，或添加本地图片。';diagnostic('capture',start,cause)}finally{capturing.value=false}
}
async function chooseImage(event:Event){const input=event.target as HTMLInputElement,file=input.files?.[0];input.value='';if(!file||!scope.value)return;if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>12*1024*1024){error.value='请选择不超过 12 MB 的 PNG、JPG 或 WebP 图片。';return}error.value='';annotation.value={scope:scope.value,document:{base:file,strokes:[]},timeMs:draft.value.timeMs??props.timeMs}}
function annotateDraft(){if(draft.value.image)annotation.value={scope:scope.value,document:draft.value.annotation||{base:draft.value.image,strokes:[]},timeMs:draft.value.timeMs??props.timeMs}}
function useImage(image:Blob,document:NoteAnnotation){const session=annotation.value;if(session&&session.scope===scope.value){draft.value.image=image;draft.value.annotation=document;draft.value.timeMs=session.timeMs}annotation.value=null}
function removeImage(){delete draft.value.image;delete draft.value.annotation;if(!draft.value.editingId)delete draft.value.timeMs}
async function deleteScope(value:string){await initializing;await store.removeScope(value);notes.value=notes.value.filter(n=>n.scope!==value);delete drafts[value]}
defineExpose({deleteScope})
</script>
<template>
 <div class="sidebar-pane-heading"><div><span class="eyebrow">MY NOTES</span><h3>随手笔记</h3></div><span>{{ visible.length }} 条</span></div>
 <div class="note-editor study-note-editor"><p>{{ draft.editingId?'编辑笔记':'记录播放位置' }} <strong>{{ time(draft.timeMs??timeMs) }}</strong></p>
 <div class="note-media-tools"><button type="button" class="secondary" :disabled="!canCapture||loading||saving||capturing" @click="capture">{{ capturing?'正在截图…':'标注当前画面' }}</button><label class="secondary note-file-label" :class="{'is-disabled':!scope||loading||saving}">添加图片<input type="file" accept="image/png,image/jpeg,image/webp" :disabled="!scope||loading||saving" @change="chooseImage" /></label></div>
 <textarea v-model="draft.text" rows="4" maxlength="2000" :disabled="loading||saving||!scope" aria-label="笔记文字" placeholder="记下自己的理解、疑问…可以只写文字、只存图片，或图文一起保存。" />
 <div v-if="draft.image" class="note-image-draft"><NoteImage :image="draft.image"/><div class="note-media-tools"><button type="button" class="text-link" :disabled="saving" @click="annotateDraft">继续标注</button><button type="button" class="text-link" :disabled="saving" @click="removeImage">移除图片</button></div></div>
 <div class="note-save-row"><span>仅保存在当前设备</span><button v-if="draft.editingId" type="button" class="text-link" :disabled="saving" @click="cancelEdit">取消编辑</button><button type="button" class="run" :disabled="loading||saving||(!draft.text.trim()&&!draft.image)||!scope" @click="save">{{ saving?'正在保存…':draft.editingId?'保存修改':'保存笔记' }}</button></div></div>
 <p v-if="error" class="sidebar-message note-error" role="alert">{{ error }} <button v-if="!saving" type="button" class="text-link" @click="retry">重新读取</button></p>
 <p v-if="loading" class="sidebar-message">正在读取本机笔记…</p><p v-else-if="!scope" class="sidebar-message">选择视频或读取分析结果后即可记笔记。</p>
 <div v-if="visible.length" class="sidebar-note-list"><article v-for="note in visible" :key="note.id" class="note-item"><div><button type="button" class="text-link time" @click="emit('seek',note.timeMs)">{{ time(note.timeMs) }} · 回放</button><span class="note-item-actions"><button type="button" class="text-link" :disabled="saving" @click="edit(note)">编辑</button><button type="button" class="note-delete" :disabled="saving" :aria-label="`删除 ${time(note.timeMs)} 的笔记`" @click="remove(note)">删除</button></span></div><NoteImage v-if="note.image" :image="note.image"/><p v-if="note.text">{{ note.text }}</p></article></div>
 <p v-else-if="scope&&!loading" class="sidebar-message">还没有笔记。可以保存文字、画面标注，或图文笔记。</p>
 <NoteAnnotationDialog v-if="annotation" :annotation="annotation.document" @save="useImage" @cancel="annotation=null" />
</template>
<style scoped>
.study-note-editor .note-media-tools{display:flex;justify-content:flex-start;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px}.note-file-label{position:relative;cursor:pointer;display:inline-flex;align-items:center}.note-file-label input{position:absolute;width:1px;height:1px;clip-path:inset(50%);overflow:hidden}.note-file-label:focus-within{outline:2px solid #6f94fa;outline-offset:2px}.note-file-label.is-disabled{opacity:.5;cursor:default}.note-image-draft{margin:12px 0}.note-image-draft .note-media-tools{margin:8px 0 0}.note-save-row{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}.note-item-actions{display:flex;align-items:center;gap:14px}.note-error{color:#a04646}.note-item>.note-picture{margin-top:12px}.note-item p{white-space:pre-wrap;overflow-wrap:anywhere}
</style>
