from pathlib import Path
p=Path('E:/workp/videostudy')
f=p/'desktop/src/videoRegionTimeline.ts';s=f.read_text(encoding='utf-8').replace('normalizeIgnoreSetting(value: unknown)', 'normalizeIgnoreSetting(value: unknown, allowFull=false)').replace('region.width * region.height > .95', 'region.width * region.height > (allowFull?1:.95)').replace('region.width * region.height <= .95', 'region.width * region.height <= (allowFull?1:.95)').replace('region: VideoRegion | null): IgnoreSetting {','region: VideoRegion | null, allowFull=false): IgnoreSetting {').replace('normalizeIgnoreSetting({nodes})','normalizeIgnoreSetting({nodes},allowFull)');f.write_text(s,encoding='utf-8')
f=p/'desktop/src/App.vue';s=f.read_text(encoding='utf-8').replace('const ignoredRegion = ref<IgnoreSetting|null>(null)', 'const ignoredRegion = ref<IgnoreSetting|null>(null)\nconst analysisRegion = ref<IgnoreSetting|null>(null)')
s=s.replace("  catch { ignoredRegion.value = null }", "  catch { ignoredRegion.value = null }\n  try { analysisRegion.value=fingerprint?normalizeIgnoreSetting(JSON.parse(localStorage.getItem(`videoAnalysisRegion:v1:${fingerprint}`)??'null'),true):null }catch {analysisRegion.value=null}",1)
s=s.replace('function openVideoWorkspace()', '''function saveAnalysisRegion(region:IgnoreSetting|null){
 analysisRegion.value=normalizeIgnoreSetting(region,true)
 if(!selectedFingerprint.value)return
 try{const key=`videoAnalysisRegion:v1:${selectedFingerprint.value}`;if(analysisRegion.value)localStorage.setItem(key,JSON.stringify(analysisRegion.value));else localStorage.removeItem(key)}catch{}
}
function openVideoWorkspace()''',1)
s=s.replace("    if (ignoredRegion.value) form.append('ignoredRegion', JSON.stringify(ignoredRegion.value))", "    if (analysisRegion.value||ignoredRegion.value) form.append('ignoredRegion',JSON.stringify(analysisRegion.value?{analysisRegion:analysisRegion.value,ignoredRegion:ignoredRegion.value}:ignoredRegion.value))")
s=s.replace('v-if="ignoredRegion" class="workspace-entry-dot"','v-if="ignoredRegion||analysisRegion" class="workspace-entry-dot"').replace('aria-label="已保存忽略区域"','aria-label="已保存画面区域"')
s=s.replace(':model-value="ignoredRegion" :time-ms=', ':model-value="ignoredRegion" :analysis-region="analysisRegion" @update:analysis-region="saveAnalysisRegion" :time-ms=')
f.write_text(s,encoding='utf-8')
f=p/'desktop/src/VideoWorkspace.vue';s=f.read_text(encoding='utf-8').replace('modelValue:IgnoreSetting|null;timeMs:', 'modelValue:IgnoreSetting|null;analysisRegion:IgnoreSetting|null;timeMs:')
s=s.replace("'update:modelValue':[region:IgnoreSetting|null]", "'update:modelValue':[region:IgnoreSetting|null];'update:analysisRegion':[region:IgnoreSetting|null]")
s=s.replace("const displaySetting=computed(()=>candidate.value?.setting??props.modelValue)", "const areaMode=ref<'ignore'|'analysis'>('ignore')\nconst selectedSetting=computed(()=>areaMode.value==='analysis'?props.analysisRegion:props.modelValue)\nconst displaySetting=computed(()=>candidate.value?.setting??selectedSetting.value)")
s=s.replace('const regionStyle=computed(', '''const otherRegion=computed(()=>regionAt(areaMode.value==='analysis'?props.modelValue:props.analysisRegion,Math.round(time.value*1000)))
const otherStyle=computed(()=>otherRegion.value?{left:`${otherRegion.value.x*100}%`,top:`${otherRegion.value.y*100}%`,width:`${otherRegion.value.width*100}%`,height:`${otherRegion.value.height*100}%`}:{})
const overlapNote=computed(()=>{
 const a=areaMode.value==='analysis'?draft.value:otherRegion.value,b=areaMode.value==='ignore'?draft.value:otherRegion.value
 if(!a||!b)return ''
 if(b.x+b.width<=a.x||a.x+a.width<=b.x||b.y+b.height<=a.y||a.y+a.height<=b.y)return '忽略区域位于分析范围外，当前不生效。'
 return '只分析绿色框内内容，并排除与蓝色框重叠的部分。'
})
function commitRegion(value:IgnoreSetting|null){if(areaMode.value==='analysis')emit('update:analysisRegion',value);else emit('update:modelValue',value)}
function selectMode(mode:'ignore'|'analysis'){if(scanBusy.value||candidate.value)return;cancelDrawing();areaMode.value=mode;refresh()}
const regionStyle=computed(''')
s=s.replace("if(draft.value.width*draft.value.height>.95)", "if(areaMode.value==='ignore'&&draft.value.width*draft.value.height>.95)")
s=s.replace("emit('update:modelValue',upsertRegionNode(props.modelValue,finished.timeMs,draft.value))", '''const a=areaMode.value==='analysis'?draft.value:regionAt(props.analysisRegion,finished.timeMs),b=areaMode.value==='ignore'?draft.value:regionAt(props.modelValue,finished.timeMs)
  if(a&&b&&b.x<=a.x&&b.y<=a.y&&b.x+b.width>=a.x+a.width&&b.y+b.height>=a.y+a.height)throw new Error('忽略框覆盖了整个分析区域，请保留需要分析的内容')
  commitRegion(upsertRegionNode(selectedSetting.value,finished.timeMs,draft.value,areaMode.value==='analysis'))''')
s=s.replace("emit('update:modelValue',null);note.value='已清除全部区域节点。'", "commitRegion(null);note.value=areaMode.value==='analysis'?'已清除分析范围，恢复完整画面。':'已清除忽略区域节点。'")
s=s.replace("emit('update:modelValue',removeRegionNode(props.modelValue,timeMs))", "commitRegion(removeRegionNode(selectedSetting.value,timeMs))")
s=s.replace('watch(()=>props.modelValue,()=>{candidate.value=null;refresh()})','watch(()=>[props.modelValue,props.analysisRegion],()=>{candidate.value=null;refresh()})')
s=s.replace('<button type="button" aria-current="page"><StudyIcon name="slides"/>忽略区域</button><p>框选摄像头等区域，设置画面变化检测的排除范围。</p>', '''<button type="button" :aria-current="areaMode==='analysis'?'page':undefined" :disabled="scanBusy||!!candidate" @click="selectMode('analysis')"><StudyIcon name="slides"/>分析区域</button><button type="button" :aria-current="areaMode==='ignore'?'page':undefined" :disabled="scanBusy||!!candidate" @click="selectMode('ignore')"><StudyIcon name="slides"/>忽略区域</button><p>绿色框限定分析范围，蓝色框排除干扰，两种区域可以叠加。</p>''')
s=s.replace('<div v-if="draft" class="workspace-region" :style="regionStyle"><span>忽略区域 · 当前时段</span>', '''<div v-if="otherRegion" :class="['workspace-region','workspace-other',{analysis:areaMode==='ignore'}]" :style="otherStyle"><span>{{ areaMode==='ignore'?'分析区域':'忽略区域' }}</span></div>
      <div v-if="draft" :class="['workspace-region',{analysis:areaMode==='analysis'}]" :style="regionStyle"><span>{{ areaMode==='analysis'?'分析区域':'忽略区域' }} · 当前时段</span>''')
s=s.replace('<h3 id="ignore-title">忽略画面区域</h3><p>首次框选默认应用于整段视频。', "<h3 id=\"ignore-title\">{{ areaMode==='analysis'?'只分析框内内容':'忽略画面区域' }}</h3><p>首次框选默认应用于整段视频。")
s=s.replace('v-if="!scanBusy" class="workspace-primary"', 'v-if="!scanBusy&&areaMode===\'ignore\'" class="workspace-primary"')
s=s.replace('v-else class="workspace-secondary" type="button" @click="stopScan"', 'v-else-if="scanBusy" class="workspace-secondary" type="button" @click="stopScan"')
s=s.replace('v-if="!scanBusy" class="workspace-secondary"', 'v-if="!scanBusy&&areaMode===\'ignore\'" class="workspace-secondary"')
s=s.replace('<p class="workspace-auto-hint">', '<p v-if="areaMode===\'ignore\'" class="workspace-auto-hint">')
s=s.replace(':disabled="!modelValue||dragging||scanBusy||!!candidate"', ':disabled="!selectedSetting||dragging||scanBusy||!!candidate"')
s=s.replace('清除全部节点</button>', '{{ areaMode===\'analysis\'?\'清除分析范围\':\'清除全部节点\' }}</button>')
s=s.replace('<strong>区域时间节点</strong>', "<strong>{{ candidate?'候选时间节点 · 未应用':areaMode==='analysis'?'分析区域时间节点':'忽略区域时间节点' }}</strong>")
s=s.replace("!node.region?'暂停忽略':node.timeMs===0?'默认区域':'新位置'", "!node.region?(areaMode==='analysis'?'完整画面':'暂停忽略'):node.timeMs===0?'默认区域':'新位置'")
s=s.replace('<p v-if="note" class="workspace-note"', '<p v-if="overlapNote" class="workspace-note" role="status">{{ overlapNote }}</p><p v-if="note" class="workspace-note"')
s=s.replace('新分析按时间节点忽略区域的画面变化。', '新分析只处理分析框内、忽略框外的画面内容。没有分析框时使用全画面。')
s=s.replace('@media(max-width:1000px)', ".workspace-region{z-index:2}.workspace-other{z-index:1;pointer-events:none}.workspace-region.analysis{border-color:#26a77d;background:#20a87824}.workspace-region.analysis span{background:#16775de6}.workspace-nav button:not([aria-current]){background:#fff;border-color:#e4eaf4;color:#6b7e9b}\n@media(max-width:1000px)")
f.write_text(s,encoding='utf-8')
f=p/'backend-java/src/test/java/cn/videostudy/api/AnalysisRegionTest.java';s=f.read_text(encoding='utf-8').replace('assertEquals(json.readTree(input),json.readTree(json.writeValueAsString(IgnoreRegion.parse(input))))','assertEquals(IgnoreRegion.parse(input),IgnoreRegion.parse(json.writeValueAsString(IgnoreRegion.parse(input))))');f.write_text(s,encoding='utf-8')
f=p/'agent-python/page_understanding.py';s=f.read_text(encoding='utf-8').replace('    result = dict(page)\n    context', "    result = {k:v for k,v in page.items() if k!='_visualRegions'}\n    context");f.write_text(s,encoding='utf-8')
