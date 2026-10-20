/** Persist associations only; the backend owns copy expiry and explicit deletion. */
type Media={size:number;fingerprint:string}
type Storage=Pick<globalThis.Storage,'getItem'|'setItem'|'removeItem'>
export type CompatibilityState={id:string;status:'queued'|'processing'|'completed';progress?:number}
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
function key(media:Media){if(!Number.isSafeInteger(media.size)||media.size<0||!/^[a-f0-9]{64}$/.test(media.fingerprint))throw Error('invalid_media_identity');return `compatibilityCopy:v1:${media.fingerprint}:${media.size}`}
export function rememberCompatibility(storage:Storage,media:Media,id:string){if(!uuid.test(id))throw Error('invalid_compatibility_id');const name=key(media);try{storage.setItem(name,JSON.stringify({id}))}catch{/* Current playback still works if browser storage is full. */}}
export function forgetCompatibility(storage:Storage,media:Media,id?:string){const name=key(media);try{const entry=JSON.parse(storage.getItem(name)||'null');if(!id||entry?.id===id)storage.removeItem(name)}catch{}}
export async function lookupCompatibility(storage:Storage,media:Media,request:typeof fetch,base:string):Promise<CompatibilityState|null>{
 const name=key(media);let entry
 try{entry=JSON.parse(storage.getItem(name)||'null')}catch{return null}
 if(!entry||typeof entry.id!=='string'||!uuid.test(entry.id))return null
 const response=await request(`${base}/compatibility/${entry.id}`)
 if(response.status===404||response.status===410){forgetCompatibility(storage,media,entry.id);return null}
 if(!response.ok)throw Error('暂时无法读取已有兼容副本，请稍后重试')
 const result=await response.json()
 if(result.id!==entry.id)throw Error('兼容副本信息校验失败')
 if(result.status==='failed'){forgetCompatibility(storage,media,entry.id);return null}
 if(!['queued','processing','completed'].includes(result.status))throw Error('兼容副本状态无效')
 return {id:entry.id,status:result.status,progress:typeof result.progress==='number'?result.progress:undefined}
}
