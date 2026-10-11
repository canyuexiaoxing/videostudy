from pathlib import Path
p=Path('E:/workp/videostudy')
f=p/'desktop/src/autoRegionScan.ts';s=f.read_text(encoding='utf-8').replace("import {normalizeIgnoreSetting}", "import {normalizeIgnoreSetting,upsertRegionNode}").replace("import type {RegionNode}", "import type {RegionNode,IgnoreSetting}")
s+='''
export function currentRegionCandidate(setting:IgnoreSetting|null,detection:Detection):ScanResult {
 if(!detection||!Number.isSafeInteger(detection.timeMs)||detection.timeMs<0)throw new Error('识别结果与当前画面不匹配')
 if(detection.status==='absent')throw new Error('当前画面未发现独立摄像头区域，原设置已保留')
 if(detection.status==='uncertain')throw new Error('当前画面的区域无法确定，请手动框选；原设置已保留')
 if(detection.status!=='detected'||!detection.region||!normalizeIgnoreSetting(detection.region))throw new Error('识别区域无效，请手动框选')
 const candidate=upsertRegionNode(setting,detection.timeMs,detection.region)
 if(!('nodes' in candidate))throw new Error('识别区域无法应用')
 return {setting:candidate,samples:[detection],unresolved:[]}
}
'''
f.write_text(s,encoding='utf-8')
f=p/'desktop/src/VideoWorkspace.vue';s=f.read_text(encoding='utf-8').replace('import {scanRegions}', 'import {scanRegions,currentRegionCandidate}')
s=s.replace('const scanBusy=ref(false),scanCount=ref(0),candidate=', "const scanMode=ref<'full'|'current'>('full')\nconst scanBusy=ref(false),scanCount=ref(0),candidate=")
s=s.replace('async function autoScan(){', "async function autoScan(mode:'full'|'current'='full'){")
s=s.replace("media.value?.pause();cancelDrawing();candidate.value=null;error.value='';note.value='';scanCount.value=0", "media.value?.pause();sync();cancelDrawing();candidate.value=null;error.value='';note.value='';scanCount.value=0;scanMode.value=mode\n const capturedTime=Math.round(time.value*1000)")
s=s.replace('  const result=await scanRegions(Math.round(duration.value*1000),async times=>{', '  const detect=async (times:number[])=>{')
s=s.replace('   const data=await response.json();return data.detections\n  },{signal:controller.signal,onProgress:count=>{if(!controller.signal.aborted)scanCount.value=count}})', '''   const data=await response.json();return data.detections
  }
  let result:ScanResult
  if(mode==='current'){
   const detections=await detect([capturedTime])
   if(controller.signal.aborted||scanController!==controller)return
   if(!Array.isArray(detections)||detections.length!==1||detections[0]?.timeMs!==capturedTime)throw new Error('识别结果与当前画面不匹配')
   result=currentRegionCandidate(props.modelValue,detections[0]);scanCount.value=1
  }else result=await scanRegions(Math.round(duration.value*1000),detect,{signal:controller.signal,onProgress:count=>{if(!controller.signal.aborted)scanCount.value=count}})''')
s=s.replace("note.value=`识别完成，共检查 ${result.samples.length} 张画面。请预览后应用。`", "note.value=mode==='current'?`已识别 ${nodeClock(capturedTime)} 的画面，请预览后应用。`:`识别完成，共检查 ${result.samples.length} 张画面。请预览后应用。`")
s=s.replace("scanBusy?`正在扫描 · 已识别 ${scanCount} 张`", "scanBusy?(scanMode==='current'?'正在识别当前画面…':`正在扫描 · 已识别 ${scanCount} 张`)")
s=s.replace('@click="autoScan">AI 扫描全片', '@click="autoScan(\'full\')">AI 扫描全片')
s=s.replace('    <button v-else class="workspace-secondary" type="button" @click="stopScan">取消扫描</button>', '''    <button v-else class="workspace-secondary" type="button" @click="stopScan">{{ scanMode==='current'?'取消识别':'取消扫描' }}</button>
    <button v-if="!scanBusy" class="workspace-secondary" type="button" :disabled="!canDraw||dragging||!!candidate" @click="autoScan('current')">AI 识别当前区域</button>''')
s=s.replace('起始检查 4 张画面，仅变化区间递归，时间粒度约 30 秒。截图会发送至当前配置的 AI 服务。', '当前区域只识别这一帧；全片扫描从 4 张画面开始递归，时间粒度约 30 秒。截图会发送至当前配置的 AI 服务。')
s=s.replace('<strong>候选结果</strong>', "<strong>{{ scanMode==='current'?'当前画面候选区域':'候选结果' }}</strong>")
s=s.replace('<p v-else>请检查是否覆盖课件。相同采样位置之间的短暂移动可能漏检。</p>', '''<p v-else-if="scanMode==='current'">{{ modelValue?`应用后从 ${nodeClock(candidate.samples[0]!.timeMs)} 开始使用，已有后续节点保留。`:'首次应用默认覆盖整段视频。' }}请检查是否覆盖课件。</p><p v-else>请检查是否覆盖课件。相同采样位置之间的短暂移动可能漏检。</p>''')
s=s.replace('@click="applyCandidate">应用自动框选', '@click="applyCandidate">{{ scanMode===\'current\'?\'应用当前区域\':\'应用自动框选\' }}')
f.write_text(s,encoding='utf-8')
