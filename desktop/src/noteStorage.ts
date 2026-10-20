import type {NoteAnnotation} from './noteDrawing'
export type StudyNote={id:string;scope:string;timeMs:number;text:string;createdAt:string;image?:Blob;annotation?:NoteAnnotation}
const DATABASE='framewise-study-notes'
function request<T>(req:IDBRequest<T>){return new Promise<T>((resolve,reject)=>{req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)})}
function committed(tx:IDBTransaction){return new Promise<void>((resolve,reject)=>{tx.oncomplete=()=>resolve();tx.onabort=tx.onerror=()=>reject(tx.error||new Error('note_storage_failed'))})}
export class NoteStorage{
 private db:Promise<IDBDatabase>
 constructor(){this.db=new Promise((resolve,reject)=>{const req=indexedDB.open(DATABASE,1);req.onupgradeneeded=()=>{const notes=req.result.createObjectStore('notes',{keyPath:'id'});notes.createIndex('scope','scope');req.result.createObjectStore('meta')};req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);req.onblocked=()=>reject(new Error('note_storage_blocked'))})}
 async all(){const db=await this.db;return request<StudyNote[]>(db.transaction('notes').objectStore('notes').getAll())}
 async put(note:StudyNote){const db=await this.db,tx=db.transaction('notes','readwrite'),done=committed(tx);tx.objectStore('notes').put({...note,annotation:note.annotation?{base:note.annotation.base,strokes:JSON.parse(JSON.stringify(note.annotation.strokes))}:undefined});await done}
 async remove(id:string){const db=await this.db,tx=db.transaction('notes','readwrite'),done=committed(tx);tx.objectStore('notes').delete(id);await done}
 async removeScope(scope:string){const db=await this.db,tx=db.transaction('notes','readwrite'),done=committed(tx),req=tx.objectStore('notes').index('scope').openCursor(IDBKeyRange.only(scope));req.onsuccess=()=>{const c=req.result;if(c){c.delete();c.continue()}};await done}
 async migrateLegacy(){
  let raw:string|null=null;try{raw=localStorage.getItem('studyNotes:v1')}catch{return}
  if(!raw)return
  let values:unknown;try{values=JSON.parse(raw)}catch{return}if(!Array.isArray(values))return
  const valid=values.filter((n):n is StudyNote=>!!n&&typeof n.id==='string'&&typeof n.scope==='string'&&typeof n.text==='string'&&Number.isFinite(n.timeMs)&&typeof n.createdAt==='string')
  const db=await this.db
  if(await request(db.transaction('meta').objectStore('meta').get('legacy-v1')))return
  const tx=db.transaction(['notes','meta'],'readwrite'),done=committed(tx),store=tx.objectStore('notes')
  tx.objectStore('meta').put(true,'legacy-v1')
  for(const note of valid){const req=store.get(note.id);req.onsuccess=()=>{if(!req.result)store.add(note)}}
  await done
  try{localStorage.removeItem('studyNotes:v1')}catch{/* The durable migration marker prevents deleted notes being restored. */}
 }
 async replaceAll(notes:StudyNote[]){
  const db=await this.db,tx=db.transaction(['notes','meta'],'readwrite'),done=committed(tx)
  tx.objectStore('notes').clear();tx.objectStore('meta').clear();tx.objectStore('meta').put(true,'legacy-v1')
  for(const note of notes)tx.objectStore('notes').put(note)
  await done
 }
 async close(){(await this.db).close()}
}
