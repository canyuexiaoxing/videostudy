import { API_ORIGIN } from './apiOrigin.ts'
import { generatePreviewSheets, PreviewMemoryCache, PREVIEW_COLUMNS, PREVIEW_HEIGHT, PREVIEW_INTERVAL, PREVIEW_TILES, PREVIEW_WIDTH } from './timelinePreview'
import { PreviewStorage } from './previewStorage'
export type PreviewState='waiting'|'generating'|'completed'|'unavailable'
type Settings={src:string;fingerprint:string;courseId:string;duration:number;localIdle:()=>boolean;onSheet:()=>void;onState:(state:PreviewState)=>void}
function delay(ms:number,signal:AbortSignal){return new Promise<void>((resolve,reject)=>{const abort=()=>{clearTimeout(timer);reject(new DOMException('Aborted','AbortError'))};const timer=setTimeout(()=>{signal.removeEventListener('abort',abort);resolve()},ms);if(signal.aborted)abort();else signal.addEventListener('abort',abort,{once:true})})}
function mediaEvent(media:HTMLVideoElement,event:string,action:()=>void,signal:AbortSignal){return new Promise<void>((resolve,reject)=>{const cleanup=()=>{clearTimeout(timer);media.removeEventListener(event,ready);media.removeEventListener('error',failed);signal.removeEventListener('abort',aborted)};const ready=()=>{cleanup();resolve()};const failed=()=>{cleanup();reject(new Error('preview_decode_failed'))};const aborted=()=>{cleanup();reject(new DOMException('Aborted','AbortError'))};const timer=setTimeout(failed,10000);media.addEventListener(event,ready,{once:true});media.addEventListener('error',failed,{once:true});signal.addEventListener('abort',aborted,{once:true});if(signal.aborted)aborted();else action()})}
export class BrowserPreview{
 private settings:Settings
 private control=new AbortController()
 private storage:PreviewStorage
 private memory:PreviewMemoryCache
 private key:string
 private decoder:HTMLVideoElement|null=null
 private disposed=false
 private serverUntil=0
 private nextCheck=0
 private permissionWarned=false
 private lastFrame=0
 private state:PreviewState='waiting'
 private generated=0
 private failure:string|undefined
 private started=performance.now()
 constructor(settings:Settings){
  this.settings=settings;this.key=`v1:${settings.fingerprint}:${Math.round(settings.duration*1000)}`
  this.storage=new PreviewStorage()
  this.memory=new PreviewMemoryCache(4,async sheet=>{const blob=await this.storage.get(this.key,sheet);return blob?URL.createObjectURL(blob):null},url=>URL.revokeObjectURL(url))
  void this.run()
 }
 private diagnostic(stage:string){const record={task:this.settings.courseId,stage,status:this.state,sheets:this.generated,errorType:this.failure,elapsedMs:Math.round(performance.now()-this.started),time:new Date().toISOString()};console.info('timeline_preview',record);try{localStorage.setItem('framewise:preview:last-run',JSON.stringify(record))}catch{/* Cache diagnostics must never block playback. */}}
 private update(state:PreviewState){if(this.state!==state){this.state=state;this.settings.onState(state);if(state!=='generating')this.diagnostic('preview_'+state)}}
 private async permit(){
  const signal=this.control.signal
  for(;;){
   signal.throwIfAborted()
   if(this.settings.localIdle()){
    const now=performance.now()
    if(now>=this.nextCheck){
     this.nextCheck=now+2000;this.serverUntil=0
     const request=new AbortController(),cancel=()=>request.abort(),timeout=setTimeout(cancel,4000)
     signal.addEventListener('abort',cancel,{once:true})
     try{const response=await fetch(`${API_ORIGIN}/api/transcriptions/${encodeURIComponent(this.settings.courseId)}/preview-permission`,{signal:request.signal,cache:'no-store'});if(response.ok){const p=await response.json();this.permissionWarned=false;if(p.allowed===true&&p.leaseMs>0)this.serverUntil=performance.now()+Math.min(2000,p.leaseMs)}}catch(error){if(!this.permissionWarned){console.debug('preview_permission_unavailable',error instanceof Error?error.name:'unknown');this.permissionWarned=true}signal.throwIfAborted()}
     finally{clearTimeout(timeout);signal.removeEventListener('abort',cancel)}
    }
    if(performance.now()<this.serverUntil&&this.settings.localIdle()){
     await delay(Math.max(25,180-(performance.now()-this.lastFrame)),signal)
     const win=window as Window & {requestIdleCallback?:(cb:(d:{timeRemaining:()=>number})=>void)=>number;cancelIdleCallback?:(id:number)=>void}
     const available=await new Promise<boolean>((resolve,reject)=>{
      if(!win.requestIdleCallback){resolve(true);return}
      const abort=()=>{if(win.cancelIdleCallback)win.cancelIdleCallback(id);reject(new DOMException('Aborted','AbortError'))}
      const id=win.requestIdleCallback(d=>{signal.removeEventListener('abort',abort);resolve(d.timeRemaining()>8)})
      signal.addEventListener('abort',abort,{once:true})
     })
     if(available&&this.settings.localIdle()&&performance.now()<this.serverUntil){this.lastFrame=performance.now();this.update('generating');return}
    }
   }
   this.update('waiting');await delay(350,signal)
  }
 }
 private async capture(canvas:HTMLCanvasElement,index:number,tile:number){
  const signal=this.control.signal
  if(!this.decoder){this.decoder=document.createElement('video');this.decoder.crossOrigin='anonymous';this.decoder.muted=true;this.decoder.preload='metadata';await mediaEvent(this.decoder,'loadeddata',()=>{this.decoder!.src=this.settings.src;this.decoder!.load()},signal)}
  const video=this.decoder,target=Math.min(index*PREVIEW_INTERVAL,Math.max(0,video.duration-.05))
  if(video.readyState<2||Math.abs(video.currentTime-target)>.025)await mediaEvent(video,'seeked',()=>{video.currentTime=target},signal)
  signal.throwIfAborted()
  const context=canvas.getContext('2d')!
  const x=tile%PREVIEW_COLUMNS*PREVIEW_WIDTH,y=Math.floor(tile/PREVIEW_COLUMNS)*PREVIEW_HEIGHT
  const scale=Math.min(PREVIEW_WIDTH/video.videoWidth,PREVIEW_HEIGHT/video.videoHeight)
  if(!Number.isFinite(scale)||scale<=0)throw new Error('preview_no_video_track')
  context.fillStyle='#111';context.fillRect(x,y,PREVIEW_WIDTH,PREVIEW_HEIGHT)
  context.drawImage(video,x+(PREVIEW_WIDTH-video.videoWidth*scale)/2,y+(PREVIEW_HEIGHT-video.videoHeight*scale)/2,video.videoWidth*scale,video.videoHeight*scale)
 }
 private async run(){
  try{
   // Serialize producers across tabs. Cached reads never wait for this lock.
   const generate=()=>generatePreviewSheets({duration:this.settings.duration,signal:this.control.signal,
    has:sheet=>this.storage.has(this.key,sheet),permit:()=>this.permit(),
    begin:()=>{const canvas=document.createElement('canvas');canvas.width=PREVIEW_WIDTH*PREVIEW_COLUMNS;canvas.height=PREVIEW_HEIGHT*(PREVIEW_TILES/PREVIEW_COLUMNS);return {capture:(index:number,tile:number)=>this.capture(canvas,index,tile),finish:()=>new Promise<Blob>((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('preview_encode_failed')),'image/jpeg',.72))}},
    save:async(sheet,blob)=>{await this.storage.save(this.key,sheet,blob);this.generated++;if(!this.disposed)this.settings.onSheet()}})
   if(navigator.locks)await navigator.locks.request('framewise-preview:'+this.key,{signal:this.control.signal},generate)
   else await generate()
   if(!this.disposed)this.update('completed')
  }catch(error){if(!this.control.signal.aborted){const safe=new Set(['preview_decode_failed','preview_no_video_track','preview_encode_failed','preview_storage_blocked','preview_cache_limit','preview_storage_failed']);this.failure=error instanceof Error?(safe.has(error.message)?error.message:error.name):'UnknownError';this.update('unavailable')}}
  finally{if(this.decoder){this.decoder.pause();this.decoder.removeAttribute('src');this.decoder.load();this.decoder=null}}
 }
 async sheet(index:number){if(this.disposed)return null;try{return await this.memory.get(index)}catch{return null}}
 dispose(){this.disposed=true;this.control.abort();this.memory.clear();void this.storage.close().catch(()=>{})}
}
