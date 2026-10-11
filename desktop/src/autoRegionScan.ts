import {normalizeIgnoreSetting,upsertRegionNode} from './videoRegionTimeline.ts'
import type {RegionNode,IgnoreSetting} from './videoRegionTimeline.ts'
import type {VideoRegion} from './videoRegion.ts'
export type Detection={timeMs:number;status:'detected'|'absent'|'uncertain';region:VideoRegion|null;reason?:string}
export type ScanResult={setting:{nodes:RegionNode[]};samples:Detection[];unresolved:{startMs:number;endMs:number}[]}
function same(a:Detection,b:Detection):boolean {
 if(a.status==='uncertain'||b.status==='uncertain'||a.status!==b.status)return false
 if(a.status==='absent')return true
 const x=a.region!,y=b.region!
 const overlap=Math.max(0,Math.min(x.x+x.width,y.x+y.width)-Math.max(x.x,y.x))*Math.max(0,Math.min(x.y+x.height,y.y+y.height)-Math.max(x.y,y.y))
 return overlap/(x.width*x.height+y.width*y.height-overlap)>=.8&&['x','y','width','height'].every(k=>Math.abs(x[k as keyof VideoRegion]-y[k as keyof VideoRegion])<=.025)
}
export async function scanRegions(durationMs:number,detect:(times:number[])=>Promise<Detection[]>,options:{signal?:AbortSignal;onProgress?:(count:number)=>void}={}):Promise<ScanResult>{
 if(!Number.isFinite(durationMs)||durationMs<1||durationMs>Number.MAX_SAFE_INTEGER)throw new Error('视频时长无效')
 const end=Math.max(0,Math.floor(durationMs)-Math.min(100,Math.floor(durationMs/2))),cache=new Map<number,Detection>()
 const unresolved:{startMs:number;endMs:number}[]=[],nodes=new Map<number,VideoRegion|null>()
 const check=()=>{if(options.signal?.aborted)throw new DOMException('已取消','AbortError')}
 async function load(times:number[]){
  for(let i=0;i<times.length;i+=4){
   check();const batch=times.slice(i,i+4),reply=await detect(batch);check()
   if(!Array.isArray(reply)||reply.length!==batch.length)throw new Error('识别结果不完整')
   for(let j=0;j<batch.length;j++){
    const d=reply[j]
    if(!d||d.timeMs!==batch[j]||!['detected','absent','uncertain'].includes(d.status))throw new Error('识别结果与截图不匹配')
    if(d.status==='detected'&&(!d.region||!normalizeIgnoreSetting(d.region)))throw new Error('识别区域无效')
    if(d.status!=='detected'&&d.region!==null)throw new Error('识别区域状态无效')
    cache.set(d.timeMs,d)
   }
   options.onProgress?.(cache.size)
  }
 }
 const initial=[...new Set([0,Math.min(end,Math.floor(durationMs/3)),Math.min(end,Math.floor(durationMs*2/3)),end])]
 await load(initial);nodes.set(0,cache.get(0)!.region)
 let intervals=initial.slice(1).map((t,i)=>[initial[i],t] as [number,number])
 function unknown(left:number,right:number){unresolved.push({startMs:left,endMs:right});nodes.set(left,null);nodes.set(right,cache.get(right)?.region??null)}
 while(intervals.length){
  check();const splits:[number,number,number][]=[],needed:number[]=[]
  for(const [left,right] of intervals){
   const a=cache.get(left)!,b=cache.get(right)!
   if(a.status==='uncertain'||b.status==='uncertain'){unknown(left,right);continue}
   if(same(a,b)){
    // Check against the retained mask too: adjacent tolerances can accumulate.
    const retained=[...nodes].filter(([t])=>t<=left).sort((x,y)=>y[0]-x[0])[0]?.[1]
    if(a.status!=='detected'||!retained||!same({timeMs:left,status:'detected',region:retained},a)||same({timeMs:left,status:'detected',region:retained},b))continue
   }
   if(right-left<=30000){nodes.set(Math.floor((left+right)/2),b.region);continue}
   const mid=Math.floor((left+right)/2)
   if(cache.size+needed.length>=64){unknown(left,right);continue}
   if(!cache.has(mid))needed.push(mid)
   splits.push([left,mid,right])
  }
  await load([...new Set(needed)])
  intervals=splits.flatMap(([l,m,r])=>[[l,m],[m,r]] as [number,number][])
 }
 const ordered=[...nodes].sort((a,b)=>a[0]-b[0]).map(([timeMs,region])=>({timeMs,region}))
 const compact=ordered.filter((node,i)=>i===0||JSON.stringify(node.region)!==JSON.stringify(ordered[i-1].region))
 const setting=normalizeIgnoreSetting({nodes:compact})
 if(!setting||!('nodes' in setting))throw new Error('扫描结果无法应用')
 return {setting,samples:[...cache.values()].sort((a,b)=>a.timeMs-b.timeMs),unresolved}
}

export function currentRegionCandidate(setting:IgnoreSetting|null,detection:Detection):ScanResult {
 if(!detection||!Number.isSafeInteger(detection.timeMs)||detection.timeMs<0)throw new Error('识别结果与当前画面不匹配')
 if(detection.status==='absent')throw new Error('当前画面未发现独立摄像头区域，原设置已保留')
 if(detection.status==='uncertain')throw new Error('当前画面的区域无法确定，请手动框选；原设置已保留')
 if(detection.status!=='detected'||!detection.region||!normalizeIgnoreSetting(detection.region))throw new Error('识别区域无效，请手动框选')
 const candidate=upsertRegionNode(setting,detection.timeMs,detection.region)
 if(!('nodes' in candidate))throw new Error('识别区域无法应用')
 return {setting:candidate,samples:[detection],unresolved:[]}
}
