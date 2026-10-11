// Independent decoder: scanning never seeks the visible player.
export async function createRegionCapture(src:string,signal:AbortSignal){
 const video=document.createElement('video');video.muted=true;video.preload='auto';video.crossOrigin='anonymous'
 const canvas=document.createElement('canvas')
 function wait(event:string){return new Promise<void>((resolve,reject)=>{
  let timer:ReturnType<typeof setTimeout>
  const cleanup=()=>{clearTimeout(timer);video.removeEventListener(event,done);video.removeEventListener('error',failed);signal.removeEventListener('abort',cancel)}
  const done=()=>{cleanup();resolve()},failed=()=>{cleanup();reject(new Error('无法读取视频画面，请先使用兼容播放'))},cancel=()=>{cleanup();reject(new DOMException('已取消','AbortError'))}
  video.addEventListener(event,done,{once:true});video.addEventListener('error',failed,{once:true});signal.addEventListener('abort',cancel,{once:true})
  timer=setTimeout(failed,15000);if(signal.aborted)cancel()
 })}
 function dispose(){video.pause();video.removeAttribute('src');video.load();canvas.width=0;canvas.height=0}
 try{const loaded=wait('loadeddata');video.src=src;await loaded}catch(e){dispose();throw e}
 if(!video.videoWidth||!Number.isFinite(video.duration)){dispose();throw new Error('当前文件没有可读取的视频画面')}
 const scale=Math.min(1,960/Math.max(video.videoWidth,video.videoHeight));canvas.width=Math.max(1,Math.round(video.videoWidth*scale));canvas.height=Math.max(1,Math.round(video.videoHeight*scale))
 return {dispose,async capture(timeMs:number){
  if(signal.aborted)throw new DOMException('已取消','AbortError')
  const target=Math.min(timeMs/1000,Math.max(0,video.duration-.05))
  if(Math.abs(video.currentTime-target)>.00001){const seeked=wait('seeked');video.currentTime=target;await seeked}
  if(signal.aborted)throw new DOMException('已取消','AbortError')
  canvas.getContext('2d')!.drawImage(video,0,0,canvas.width,canvas.height)
  return {timeMs,image:canvas.toDataURL('image/jpeg',.85)}
 }}
}
