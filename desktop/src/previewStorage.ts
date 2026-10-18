/** Compressed sprite sheets on the user's device; no video or images are uploaded. */
export type PreviewSheet={id:string;key:string;sheet:number;blob:Blob;size:number;touched:number}
const DATABASE='framewise-timeline-previews',DISK_LIMIT=1024*1024*1024
function result<T>(request:IDBRequest<T>):Promise<T>{return new Promise((resolve,reject)=>{request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)})}
function committed(tx:IDBTransaction){return new Promise<void>((resolve,reject)=>{tx.oncomplete=()=>resolve();tx.onabort=tx.onerror=()=>reject(tx.error||new Error('preview_storage_failed'))})}
export class PreviewStorage{
 private db:Promise<IDBDatabase>
 constructor(){this.db=new Promise((resolve,reject)=>{const req=indexedDB.open(DATABASE,1);req.onupgradeneeded=()=>{req.result.createObjectStore('sheets',{keyPath:'id'})};req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);req.onblocked=()=>reject(new Error('preview_storage_blocked'))})}
 async has(key:string,sheet:number){const db=await this.db;return (await result(db.transaction('sheets').objectStore('sheets').count(key+'|'+sheet)))>0}
 async get(key:string,sheet:number){const db=await this.db;const row=await result<PreviewSheet|undefined>(db.transaction('sheets').objectStore('sheets').get(key+'|'+sheet));if(row){const tx=db.transaction('sheets','readwrite');row.touched=Date.now();const done=committed(tx);tx.objectStore('sheets').put(row);await done;}return row?.blob||null}
 async prune(keepKey:string,limit=DISK_LIMIT,enforce=true){
  const db=await this.db;const rows:{id:string;key:string;size:number;touched:number}[]=[]
  await new Promise<void>((resolve,reject)=>{const req=db.transaction('sheets').objectStore('sheets').openCursor();req.onerror=()=>reject(req.error);req.onsuccess=()=>{const c=req.result;if(!c){resolve();return}const r=c.value as PreviewSheet;rows.push({id:r.id,key:r.key,size:r.size,touched:r.touched});c.continue()}})
  let size=rows.reduce((sum,r)=>sum+r.size,0);const tx=db.transaction('sheets','readwrite'),done=committed(tx)
  for(const r of rows.filter(r=>r.key!==keepKey).sort((a,b)=>a.touched-b.touched)){if(size<=limit)break;tx.objectStore('sheets').delete(r.id);size-=r.size}
  await done;if(enforce&&size>limit)throw new Error('preview_cache_limit')
 }
 async save(key:string,sheet:number,blob:Blob){
  const db=await this.db
  await this.prune(key,DISK_LIMIT-blob.size)
  const write=async()=>{const tx=db.transaction('sheets','readwrite'),done=committed(tx);tx.objectStore('sheets').put({id:key+'|'+sheet,key,sheet,blob,size:blob.size,touched:Date.now()} satisfies PreviewSheet);await done}
  try{await write()}catch(error){if(!(error instanceof DOMException)||error.name!=='QuotaExceededError')throw error;await this.prune(key,0,false);await write()}
 }
 async close(){(await this.db).close()}
}
