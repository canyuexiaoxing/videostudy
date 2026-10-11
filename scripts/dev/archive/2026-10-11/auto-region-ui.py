from pathlib import Path
p=Path('E:/workp/videostudy')
(p/'desktop/src/regionCapture.ts').write_text('''// Independent decoder: scanning never seeks the visible player.
export async function createRegionCapture(src:string,signal:AbortSignal){
 const video=document.createElement('video');video.muted=true;video.preload='auto'
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
''',encoding='utf-8')
f=p/'desktop/src/VideoWorkspace.vue';s=f.read_text(encoding='utf-8')
s=s.replace("import type {IgnoreSetting} from './videoRegionTimeline'", "import type {IgnoreSetting} from './videoRegionTimeline'\nimport {scanRegions} from './autoRegionScan'\nimport type {ScanResult} from './autoRegionScan'\nimport {createRegionCapture} from './regionCapture'")
s=s.replace("const nodes=computed(()=>regionNodes(props.modelValue))", "const scanBusy=ref(false),scanCount=ref(0),candidate=ref<ScanResult|null>(null)\nlet scanController:AbortController|null=null\nconst displaySetting=computed(()=>candidate.value?.setting??props.modelValue)\nconst nodes=computed(()=>regionNodes(displaySetting.value))")
s=s.replace('videoWidth.value>0&&!props.checking)', 'videoWidth.value>0&&!props.checking&&!scanBusy.value)')
s=s.replace('draft.value=regionAt(props.modelValue,Math.round(time.value*1000))', 'draft.value=regionAt(displaySetting.value,Math.round(time.value*1000))')
s=s.replace('if(!canDraw.value||event.button!==0||anchor)return', 'if(!canDraw.value||candidate.value||event.button!==0||anchor)return')
s=s.replace("function close(){media.value?.pause();emit('close')}", '''function stopScan(){scanController?.abort();scanController=null;scanBusy.value=false}
function discardCandidate(){candidate.value=null;refresh();note.value='已保留原有设置。'}
function applyCandidate(){if(!candidate.value)return;const value=candidate.value.setting;candidate.value=null;emit('update:modelValue',value);note.value='已应用自动识别的时间节点，可继续手动调整。';refresh()}
async function autoScan(){
 if(!canDraw.value||!duration.value)return
 media.value?.pause();cancelDrawing();candidate.value=null;error.value='';note.value='';scanCount.value=0
 const controller=new AbortController();scanController=controller;scanBusy.value=true
 let decoder:Awaited<ReturnType<typeof createRegionCapture>>|undefined
 try{
  decoder=await createRegionCapture(props.src,controller.signal)
  const result=await scanRegions(Math.round(duration.value*1000),async times=>{
   const frames=[];for(const t of times)frames.push(await decoder!.capture(t))
   const response=await fetch('http://127.0.0.1:18080/api/video-region-detections',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({frames}),signal:AbortSignal.any([controller.signal,AbortSignal.timeout(65000)])})
   if(!response.ok)throw new Error(response.status===429?'识别服务繁忙，请稍后重试':response.status===422||response.status===400?'截图无法识别，请尝试兼容播放':'AI 自动识别暂时不可用，请检查模型配置或使用手动框选')
   const data=await response.json();return data.detections
  },{signal:controller.signal,onProgress:count=>{if(!controller.signal.aborted)scanCount.value=count}})
  if(scanController!==controller||controller.signal.aborted)return
  candidate.value=result;refresh();note.value=`识别完成，共检查 ${result.samples.length} 张画面。请预览后应用。`
 }catch(e){if(!controller.signal.aborted&&scanController===controller)error.value=e instanceof Error?e.message:'自动识别失败，请手动框选'}
 finally{decoder?.dispose();if(scanController===controller){scanController=null;scanBusy.value=false}}
}
function close(){stopScan();media.value?.pause();emit('close')}''')
s=s.replace("watch(()=>props.src,()=>{media.value?.pause();", "watch(()=>props.src,()=>{stopScan();candidate.value=null;media.value?.pause();")
s=s.replace('watch(()=>props.modelValue,refresh)', 'watch(()=>props.modelValue,()=>{candidate.value=null;refresh()})')
s=s.replace('onBeforeUnmount(()=>{observer?.disconnect();', 'onBeforeUnmount(()=>{stopScan();observer?.disconnect();')
s=s.replace("{{ checking?'正在确认当前文件…':editing||dragging?'正在调整区域':nodes.length?`已设置 ${nodes.length} 个时间节点`:'未设置忽略区域' }}", "{{ scanBusy?`正在扫描 · 已识别 ${scanCount} 张`:candidate?'自动识别结果 · 尚未应用':checking?'正在确认当前文件…':editing||dragging?'正在调整区域':nodes.length?`已设置 ${nodes.length} 个时间节点`:'未设置忽略区域' }}")
s=s.replace('    <button class="workspace-primary" type="button" :disabled="!canDraw||dragging"', '''    <button v-if="!scanBusy" class="workspace-primary" type="button" :disabled="!canDraw||dragging||!!candidate" @click="autoScan">AI 扫描全片</button>
    <button v-else class="workspace-secondary" type="button" @click="stopScan">取消扫描</button>
    <p class="workspace-auto-hint">起始检查 4 张画面，仅变化区间递归，时间粒度约 30 秒。截图会发送至当前配置的 AI 服务。</p>
    <div v-if="candidate" class="workspace-candidate"><strong>候选结果</strong><p>{{ candidate.setting.nodes.length }} 个区域节点 · {{ candidate.samples.length }} 张检测画面</p><p v-if="candidate.unresolved.length" class="workspace-error">{{ candidate.unresolved.length }} 个区间无法确定，暂不忽略：{{ candidate.unresolved.map(r=>`${nodeClock(r.startMs)}—${nodeClock(r.endMs)}`).join('、') }}。请人工检查。</p><p v-else>请检查是否覆盖课件。相同采样位置之间的短暂移动可能漏检。</p><button type="button" class="workspace-primary" @click="applyCandidate">应用自动框选</button><button type="button" class="workspace-secondary" @click="discardCandidate">放弃结果，保留原设置</button></div>
    <button class="workspace-primary" type="button" :disabled="!canDraw||dragging||!!candidate"''')
s=s.replace(':disabled="!modelValue||dragging"', ':disabled="!modelValue||dragging||scanBusy||!!candidate"')
s=s.replace(':disabled="!ready||dragging"', ':disabled="!ready||dragging||scanBusy"')
s=s.replace(':disabled="dragging" :aria-label="`删除区域节点', ':disabled="dragging||scanBusy||!!candidate" :aria-label="`删除区域节点')
s=s.replace("node.timeMs===0?'默认区域':node.region?'新位置':'暂停忽略'", "!node.region?'暂停忽略':node.timeMs===0?'默认区域':'新位置'")
s=s.replace('@media(max-width:1000px)', '.workspace-auto-hint{grid-column:1/-1;font-size:11px!important}.workspace-candidate{grid-column:1/-1;margin-top:15px;padding:12px;border:1px solid #b8caff;border-radius:9px;background:#f3f6ff;font-size:12px;overflow-wrap:anywhere}.workspace-candidate p{font-size:11px;line-height:1.8;color:#6f809b}\n@media(max-width:1000px)')
f.write_text(s,encoding='utf-8')
(p/'backend-java/src/test/java/cn/videostudy/api/VideoRegionControllerTest.java').write_text('''package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.http.MediaType;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;
class VideoRegionControllerTest {
 @Test void forwardsBatchWithoutChangingTimes(){
  var builder=RestClient.builder().baseUrl("http://agent");var server=MockRestServiceServer.bindTo(builder).build();
  server.expect(requestTo("http://agent/video-region-detections")).andExpect(jsonPath("$.frames[0].timeMs").value(1234)).andRespond(withSuccess("{\\"detections\\":[{\\"timeMs\\":1234,\\"status\\":\\"absent\\",\\"region\\":null}]}",MediaType.APPLICATION_JSON));
  var controller=new VideoRegionController(builder.build());assertEquals(200,controller.detect(new VideoRegionController.Batch(List.of(new VideoRegionController.Frame(1234,"data:image/jpeg;base64,AA==")))).getStatusCode().value());server.verify();
 }
 @Test void rejectsInvalidOrDuplicateFramesBeforeCallingAgent(){
  var controller=new VideoRegionController(RestClient.create("http://unreachable"));
  assertEquals(400,controller.detect(new VideoRegionController.Batch(List.of())).getStatusCode().value());
  var frame=new VideoRegionController.Frame(0,"data:image/jpeg;base64,AA==");
  assertEquals(400,controller.detect(new VideoRegionController.Batch(List.of(frame,frame))).getStatusCode().value());
  assertEquals(400,controller.detect(new VideoRegionController.Batch(List.of(new VideoRegionController.Frame(-1,frame.image())))).getStatusCode().value());
 }
}
''',encoding='utf-8')
