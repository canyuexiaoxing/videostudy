import { NoteStorage } from './noteStorage.ts'
import type { StudyNote } from './noteStorage.ts'
import type { NoteStroke } from './noteDrawing.ts'
type ImageData = {type:string;base64:string}
type ArchivedNote = Omit<StudyNote,'image'|'annotation'> & {image?:ImageData;annotation?:{base:ImageData;strokes:NoteStroke[]}}
export type NotesArchive = {format:'framewise-renderer';version:1;notes:ArchivedNote[];localStorage:Record<string,string>}
const fixedKeys = new Set(['analysisHistory:v1','lastAnalysisId','framewise:appearance:v1','subtitleAppearance:v1','framewise:workspace-split:v1','videostudy:practice-client','framewise:study-chat-client:v1'])
export function archiveStorageKey(key:string):boolean {
 return fixedKeys.has(key) || /^(analysisMedia:|videoIgnoreRegion:v1:|videoAnalysisRegion:v1:|videoPersonSelection:v1:)[A-Za-z0-9:._-]{1,256}$/.test(key)
}
function invalid():never { throw Error('invalid_notes_backup') }
function object(value:unknown):Record<string,unknown> { if(!value || typeof value!=='object' || Array.isArray(value))return invalid();return value as Record<string,unknown> }
function text(value:unknown,max:number):string {if(typeof value!=='string'||value.length>max)return invalid();return value}
async function imageOut(blob:Blob):Promise<ImageData> {
 const bytes = new Uint8Array(await blob.arrayBuffer());let binary=''
 for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768))
 return {type:blob.type,base64:btoa(binary)}
}
function imageIn(raw:unknown):Blob {
 const image=object(raw),mime=text(image.type,40),data=text(image.base64,48*1024*1024)
 if(!['image/png','image/jpeg','image/webp'].includes(mime)||data.length%4!==0||!/^[A-Za-z0-9+/]*={0,2}$/.test(data))return invalid()
 const binary=atob(data),bytes=new Uint8Array(binary.length)
 for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i)
 return new Blob([bytes],{type:mime})
}
function strokesIn(raw:unknown):NoteStroke[] {
 if(!Array.isArray(raw)||raw.length>10000)return invalid()
 let points=0
 return raw.map(item=>{const s=object(item);if(!['pen','highlight','arrow','rectangle','ellipse','eraser'].includes(String(s.tool))||typeof s.color!=='string'||!/^#[a-f0-9]{3,8}$/i.test(s.color)||typeof s.size!=='number'||!Number.isFinite(s.size)||s.size<=0||s.size>1000||typeof s.dashed!=='boolean'||!Array.isArray(s.points))return invalid()
 points+=s.points.length;if(points>1000000)return invalid()
 return {tool:s.tool as NoteStroke['tool'],color:s.color,size:s.size,dashed:s.dashed,points:s.points.map(rawPoint=>{const p=object(rawPoint);if(typeof p.x!=='number'||typeof p.y!=='number'||!Number.isFinite(p.x)||!Number.isFinite(p.y)||Math.abs(p.x)>100000||Math.abs(p.y)>100000)return invalid();return {x:p.x,y:p.y}})} })
}
export async function serializeNote(note:StudyNote):Promise<ArchivedNote> {
 return {id:note.id,scope:note.scope,timeMs:note.timeMs,text:note.text,createdAt:note.createdAt,...(note.image?{image:await imageOut(note.image)}:{}),...(note.annotation?{annotation:{base:await imageOut(note.annotation.base),strokes:JSON.parse(JSON.stringify(note.annotation.strokes))}}:{})}
}
/** Decode everything before opening a write transaction or changing preferences. */
export function validateNotesArchive(raw:unknown):{notes:StudyNote[];localStorage:Record<string,string>} {
 const archive=object(raw);if(archive.format!=='framewise-renderer'||archive.version!==1||!Array.isArray(archive.notes)||archive.notes.length>100000)return invalid()
 const ids=new Set<string>();let bytes=0
 const notes=archive.notes.map(rawNote=>{const note=object(rawNote),id=text(note.id,256),scope=text(note.scope,1024),content=text(note.text,2*1024*1024),createdAt=text(note.createdAt,100)
 if(!id||!scope||ids.has(id)||typeof note.timeMs!=='number'||!Number.isFinite(note.timeMs)||note.timeMs<0||!Number.isFinite(Date.parse(createdAt)))return invalid();ids.add(id)
 const image=note.image===undefined?undefined:imageIn(note.image),annotation=note.annotation===undefined?undefined:object(note.annotation)
 const document=annotation?{base:imageIn(annotation.base),strokes:strokesIn(annotation.strokes)}:undefined
 bytes+=(image?.size||0)+(document?.base.size||0)+content.length;if(bytes>512*1024*1024)return invalid()
 return {id,scope,text:content,timeMs:note.timeMs,createdAt,...(image?{image}:{}),...(document?{annotation:document}:{})}
 })
 const preferences=object(archive.localStorage),local:Record<string,string>={};let total=0
 for(const [key,value] of Object.entries(preferences)){if(!archiveStorageKey(key))return invalid();const clean=text(value,8*1024*1024);total+=clean.length;if(total>32*1024*1024)return invalid();local[key]=clean}
 return {notes,localStorage:local}
}
export async function exportNotesArchive():Promise<NotesArchive> {
 const storage=new NoteStorage()
 try {await storage.migrateLegacy();const notes=await storage.all(),preferences:Record<string,string>={}
  for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(key&&archiveStorageKey(key))preferences[key]=localStorage.getItem(key)||''}
  const archive:NotesArchive={format:'framewise-renderer',version:1,notes:await Promise.all(notes.map(serializeNote)),localStorage:preferences}
  validateNotesArchive(archive);return archive
 } finally {await storage.close()}
}
export async function applyNotesArchive(raw:unknown,localStorage:Storage,createStorage:()=>Pick<NoteStorage,'replaceAll'|'close'>=()=>new NoteStorage()):Promise<void> {
 const validated=validateNotesArchive(raw),previous:Record<string,string>={}
 for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(key&&archiveStorageKey(key))previous[key]=localStorage.getItem(key)||''}
 function replace(values:Record<string,string>){const keys:string[]=[];for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(key&&archiveStorageKey(key))keys.push(key)}for(const key of keys)localStorage.removeItem(key);for(const [key,value] of Object.entries(values))localStorage.setItem(key,value)}
 const storage=createStorage()
 try {replace(validated.localStorage);await storage.replaceAll(validated.notes)}catch(error){replace(previous);throw error}finally{await storage.close()}
}
export async function importNotesArchive(raw:unknown):Promise<void> {await applyNotesArchive(raw,localStorage)}
declare global {interface Window {framewiseExportNotes:typeof exportNotesArchive;framewiseImportNotes:typeof importNotesArchive}}
