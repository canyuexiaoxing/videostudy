export const PREVIEW_INTERVAL=5
export const PREVIEW_WIDTH=240, PREVIEW_HEIGHT=135, PREVIEW_COLUMNS=5, PREVIEW_TILES=20
export function previewTile(seconds:number,duration:number){
 if(!Number.isFinite(duration)||duration<=0||!Number.isFinite(seconds))return null
 const index=Math.min(Math.ceil(duration/PREVIEW_INTERVAL)-1,Math.max(0,Math.floor(seconds/PREVIEW_INTERVAL)))
 const tile=index%PREVIEW_TILES
 return {index,sheet:Math.floor(index/PREVIEW_TILES),x:tile%PREVIEW_COLUMNS*PREVIEW_WIDTH,y:Math.floor(tile/PREVIEW_COLUMNS)*PREVIEW_HEIGHT}
}
function check(signal:AbortSignal){signal.throwIfAborted()}
export async function generatePreviewSheets(options:{duration:number;signal:AbortSignal;has:(sheet:number)=>Promise<boolean>;permit:()=>Promise<void>;begin:()=>{capture:(index:number,tile:number)=>Promise<void>;finish:()=>Promise<Blob>};save:(sheet:number,blob:Blob)=>Promise<void>}){
 const count=Math.ceil(options.duration/PREVIEW_INTERVAL)
 if(!Number.isFinite(count)||count<=0)return
 for(let sheet=0;sheet<Math.ceil(count/PREVIEW_TILES);sheet++){
  check(options.signal)
  if(await options.has(sheet))continue
  await options.permit();check(options.signal)
  const painter=options.begin()
  for(let index=sheet*PREVIEW_TILES;index<Math.min(count,(sheet+1)*PREVIEW_TILES);index++){
   await options.permit();check(options.signal)
   await painter.capture(index,index%PREVIEW_TILES);check(options.signal)
  }
  await options.permit();check(options.signal)
  const blob=await painter.finish();check(options.signal)
  await options.save(sheet,blob);check(options.signal)
 }
}
export class PreviewMemoryCache {
 private entries=new Map<number,string>()
 private pending=new Map<number,Promise<string|null>>()
 private generation=0
 private limit:number
 private load:(key:number)=>Promise<string|null>
 private dispose:(url:string)=>void
 constructor(limit:number,load:(key:number)=>Promise<string|null>,dispose:(url:string)=>void){this.limit=limit;this.load=load;this.dispose=dispose}
 async get(key:number):Promise<string|null>{
  const cached=this.entries.get(key)
  if(cached){this.entries.delete(key);this.entries.set(key,cached);return cached}
  const inFlight=this.pending.get(key);if(inFlight)return inFlight
  const generation=this.generation
  const promise=this.load(key).then(url=>{
   if(!url)return null
   if(generation!==this.generation){this.dispose(url);return null}
   this.entries.set(key,url)
   while(this.entries.size>this.limit){const first=this.entries.entries().next().value!;this.entries.delete(first[0]);this.dispose(first[1])}
   return url
  }).finally(()=>{if(generation===this.generation)this.pending.delete(key)})
  this.pending.set(key,promise);return promise
 }
 clear(){this.generation++;for(const url of this.entries.values())this.dispose(url);this.entries.clear();this.pending.clear()}
}
