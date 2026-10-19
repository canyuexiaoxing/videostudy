type Identity={size:number;fingerprint:string}
type Storage=Pick<globalThis.Storage,'getItem'|'setItem'>
type Hooks={signal?:AbortSignal;onUpdate?:(media:Identity|null)=>void;onConflict?:()=>void;onError?:(error:unknown)=>void}
function valid(value:unknown):value is Identity {const m=value as Identity;return !!m&&Number.isSafeInteger(m.size)&&m.size>=0&&typeof m.fingerprint==='string'&&/^[a-f0-9]{64}$/.test(m.fingerprint)}
export function localMediaIdentity(storage:Storage,id:string):Identity|null{
 try{const value=JSON.parse(storage.getItem(`analysisMedia:${id}`)||'null');if(!valid(value)||(value as Identity & {conflict?:boolean}).conflict||!['automatic_upload','server','legacy_auto',undefined].includes((value as Identity & {bindingSource?:string}).bindingSource))return null;return {size:value.size,fingerprint:value.fingerprint}}catch{return null}
}
export async function resolveMediaIdentity(id:string,storage:Storage,request:typeof fetch,hooks:Hooks={}):Promise<Identity|null>{
 const local=localMediaIdentity(storage,id),url=`http://127.0.0.1:18080/api/transcriptions/${id}/media`
 const sync=async()=>{
  let response=await request(url,{signal:hooks.signal})
  if(response.status===410&&local)response=await request(url,{method:'PUT',signal:hooks.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({...local,bindingSource:'legacy_auto'})})
  if(hooks.signal?.aborted)throw new DOMException('Aborted','AbortError')
  if(response.status===410){hooks.onUpdate?.(null);return null}
  const conflict=()=>{try{storage.setItem(`analysisMedia:${id}`,JSON.stringify({...local,conflict:true}))}catch{}hooks.onConflict?.();throw new Error('media_identity_conflict')}
  if(response.status===409)return conflict()
  if(!response.ok)throw new Error(`无法核对课程视频：HTTP ${response.status}`)
  const value=await response.json();if(!valid(value))throw new Error('课程视频指纹无效')
  const media={size:value.size,fingerprint:value.fingerprint}
  if(local&&(local.size!==media.size||local.fingerprint!==media.fingerprint))return conflict()
  try{const old=JSON.parse(storage.getItem(`analysisMedia:${id}`)||'null');storage.setItem(`analysisMedia:${id}`,JSON.stringify({name:old?.name||'',...media,bindingSource:'server'}))}catch{}
  hooks.onUpdate?.(media);return media
 }
 if(local){void sync().catch(error=>{if(!hooks.signal?.aborted)hooks.onError?.(error)});return local}
 return sync()
}
