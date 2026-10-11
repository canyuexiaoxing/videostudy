from pathlib import Path
r=Path('E:/workp/videostudy')
def edit(name,changes):
 p=r/name;s=p.read_text(encoding='utf-8')
 for before,after in changes:
  assert before in s,(name,before)
  s=s.replace(before,after)
 p.write_text(s,encoding='utf-8')
(r/'agent-python/analysis_progress.py').write_text('''"""Best-effort atomic task progress, independent of reusable checkpoint identity."""
import json
import logging
from pathlib import Path
import threading
from uuid import uuid4

class AnalysisProgress:
    def __init__(self, root: Path):
        self.root = root
        self.lock = threading.Lock()
        self.units = set()
        self.value = {}

    def enter(self, stage, completed_stages, total_units=0):
        with self.lock:
            self.units.clear()
            self.value = dict(stage=stage, completedStages=completed_stages, totalStages=5,
                              completedUnits=0, totalUnits=total_units)
            self._publish()

    def unit_done(self, key, stage):
        with self.lock:
            if self.value.get('stage') != stage or key in self.units:
                return
            self.units.add(key)
            self.value['completedUnits'] = min(len(self.units), self.value['totalUnits'])
            self._publish()

    def _publish(self):
        temporary = self.root / f'progress.{uuid4().hex}.tmp'
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(self.value), encoding='utf-8')
            temporary.replace(self.root / 'progress.json')
        except OSError:
            logging.getLogger(__name__).warning('Unable to publish analysis progress')
        finally:
            try: temporary.unlink(missing_ok=True)
            except OSError: pass
''',encoding='utf-8')
edit('agent-python/analysis.py',[
('from checkpoints import Checkpoints','from checkpoints import Checkpoints\nfrom analysis_progress import AnalysisProgress'),
('    started = perf_counter()', '    progress = AnalysisProgress(keyframe_dir / ".analysis")\n    progress.enter("media", 0, 2)\n    started = perf_counter()'),
('        timings[name] = round((perf_counter() - before) * 1000)\n        return value', '''        timings[name] = round((perf_counter() - before) * 1000)
        if name in ('transcription', 'visualOcr'):
            progress.unit_done(name, 'media')
        elif name in ('overview', 'mindMap') and (not isinstance(value, dict) or value.get('status') != 'failed'):
            progress.unit_done(name, 'materials')
        return value'''),
('            before = perf_counter()\n            def coverage():', '            progress.enter("coverage", 1)\n            before = perf_counter()\n            def coverage():'),
('        page_groups, transition_times = timed(', '        progress.enter("grouping", 2)\n        page_groups, transition_times = timed('),
('        if page_groups:\n            by_time', '        progress.enter("pages", 3, len(page_groups))\n        if page_groups:\n            by_time'),
('                page_groups = list(pool.map(lambda page: cached(f\'page:{page["pageIndex"]}\',','                def understand(page):\n                    result = cached(f\'page:{page["pageIndex"]}\','),
('                    page_groups))', '''                    )
                    if (result.get('imageAnalysis') or result.get('textAnalysis') or {}).get('status') != 'failed':
                        progress.unit_done(str(page['pageIndex']), 'pages')
                    return result
                page_groups = list(pool.map(understand, page_groups))'''),
('        with ThreadPoolExecutor(max_workers=2) as pool:\n            overview_job', '''        pages_failed = any((page.get('imageAnalysis') or page.get('textAnalysis') or {}).get('status') == 'failed' for page in page_groups)
        if not pages_failed:
            progress.enter('materials', 4, 2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            overview_job'''),
('map_job=pool.submit(timed,"mindMap",lambda:build_mind_map(transcript[\'segments\'],page_groups,checkpoint=checkpoint))', 'map_job=pool.submit(timed,"mindMap",lambda:build_mind_map(transcript[\'segments\'],page_groups,checkpoint=checkpoint))'),
('        timings["total"] = round(', '''        if not pages_failed and mind_map.get('status') != 'failed' and overview.get('status') != 'failed':
            progress.enter('saving', 4)
        timings["total"] = round('''),
])
for name in ['agent-python/Dockerfile','agent-python/Dockerfile.gpu']:
 edit(name,[('analysis.py visual_evidence.py','analysis.py analysis_progress.py visual_evidence.py')])
java='backend-java/src/main/java/cn/videostudy/api/TranscriptionController.java'
edit(java,[
('return store.find(id).<ResponseEntity<?>>map(ResponseEntity::ok)', 'return store.find(id).<ResponseEntity<?>>map(job -> ResponseEntity.ok(new TranscriptionJob(\n            job.id(), job.status(), job.result(), job.error(), readProgress(job.id(), job.status()))))'),
('                var result = ignoredRegion == null ?', '                clearProgress(id);\n                var result = ignoredRegion == null ?'),
('    private void deleteTaskDirectory(String id, boolean checkpointsOnly)', '''    private Path progressPath(String id) {
        return keyframeDirectory == null ? null : Path.of(keyframeDirectory).toAbsolutePath().normalize()
            .resolve(UUID.fromString(id).toString()).resolve(".analysis").resolve("progress.json");
    }

    private void clearProgress(String id) {
        try { var path = progressPath(id); if (path != null) Files.deleteIfExists(path); }
        catch (IOException | IllegalArgumentException error) { log.debug("Unable to reset task progress {}", id); }
    }

    private AnalysisProgress readProgress(String id, String status) {
        if (!List.of("processing", "failed").contains(status)) return null;
        try {
            var path = progressPath(id);
            if (path == null || !Files.isRegularFile(path) || Files.size(path) > 4096) return null;
            var json = new com.fasterxml.jackson.databind.ObjectMapper().readTree(Files.readString(path));
            if (!json.has("stage") || !json.get("stage").isTextual()) return null;
            for (var key : List.of("completedStages", "totalStages", "completedUnits", "totalUnits"))
                if (!json.has(key) || !json.get(key).isIntegralNumber() || !json.get(key).canConvertToInt()) return null;
            var stage = json.get("stage").textValue();
            int completed = json.get("completedStages").intValue(), total = json.get("totalStages").intValue();
            int units = json.get("completedUnits").intValue(), count = json.get("totalUnits").intValue();
            var stages = Map.of("media", 0, "coverage", 1, "grouping", 2, "pages", 3, "materials", 4, "saving", 4);
            if (!stages.containsKey(stage) || completed != stages.get(stage) || total != 5 || count < 0 || units < 0 || units > count) return null;
            return new AnalysisProgress(stage, completed, total, units, count);
        } catch (IOException | IllegalArgumentException error) { return null; }
    }

    private void deleteTaskDirectory(String id, boolean checkpointsOnly)'''),
('    public record TranscriptionJob(String id, String status, TranscriptResult result, String error) {}', '''    public record AnalysisProgress(String stage, int completedStages, int totalStages, int completedUnits, int totalUnits) {}
    public record TranscriptionJob(String id, String status, TranscriptResult result, String error, AnalysisProgress progress) {
        public TranscriptionJob(String id, String status, TranscriptResult result, String error) {
            this(id, status, result, error, null);
        }
    }'''),
])
(r/'desktop/src/analysisProgress.ts').write_text('''export type AnalysisProgress = {stage:string;completedStages:number;totalStages:number;completedUnits:number;totalUnits:number}
const stages:Record<string,number>={media:0,coverage:1,grouping:2,pages:3,materials:4,saving:4}
const labels:Record<string,string>={media:'语音转写与截图筛选',coverage:'补采检查',grouping:'同页分组',pages:'页面解读',materials:'学习资料生成',saving:'正在保存分析结果'}
export function progressView(state:string, value:AnalysisProgress|null){
 const valid=!!value&&Object.hasOwn(stages,value.stage)&&value.completedStages===stages[value.stage]&&value.totalStages===5&&[value.completedStages,value.completedUnits,value.totalUnits].every(Number.isSafeInteger)&&value.completedUnits>=0&&value.totalUnits>=value.completedUnits
 const p=valid?value:null
 const ratio=p?(p.completedStages+(p.totalUnits>0?p.completedUnits/p.totalUnits:0))/5:0
 const label=p?labels[p.stage]+(p.stage==='pages'?` · 已完成 ${p.completedUnits} / ${p.totalUnits} 页`:p.stage==='materials'?` · 已完成 ${p.completedUnits} / ${p.totalUnits} 项`:''): '正在准备分析…'
 if(state==='completed')return {label:'分析完成',ratio:1,completed:5,indeterminate:false}
 if(state==='uploading')return {label:'正在上传视频…',ratio:0,completed:0,indeterminate:true}
 if(state==='reading')return {label:'正在读取分析进度…',ratio:0,completed:0,indeterminate:true}
 if(state==='queued')return {label:'等待分析任务…',ratio:0,completed:0,indeterminate:true}
 if(state==='failed'||state==='interrupted')return {label:(state==='failed'?'分析未完成':'进度查询或上传中断')+(p?` · ${label}`:''),ratio:Math.min(ratio,.95),completed:p?.completedStages??0,indeterminate:false}
 return {label,ratio:Math.min(ratio,.95),completed:p?.completedStages??0,indeterminate:!p}
}
''',encoding='utf-8')
(r/'desktop/src/AnalysisProgress.vue').write_text('''<script setup lang="ts">
import {computed} from 'vue'
import {progressView} from './analysisProgress'
import type {AnalysisProgress} from './analysisProgress'
const props=defineProps<{state:string;progress:AnalysisProgress|null}>()
const view=computed(()=>progressView(props.state,props.progress))
const steps=['转写与选图','补采检查','同页分组','页面解读','学习资料']
</script>
<template>
 <section v-if="state" class="analysis-progress" :class="{'progress-failed':['failed','interrupted'].includes(state)}" aria-label="视频分析进度">
  <div class="progress-heading"><strong role="status" aria-live="polite">{{view.label}}</strong><span>已完成 {{view.completed}} / 5 个阶段</span></div>
  <div class="progress-track" :class="{'progress-indeterminate':view.indeterminate}" role="progressbar" aria-label="分析阶段完成情况" :aria-valuenow="view.indeterminate?undefined:view.ratio*5" :aria-valuemin="0" :aria-valuemax="5" :aria-valuetext="view.label"><div class="progress-fill" :style="{width:`${view.ratio*100}%`}"></div></div>
  <div class="progress-steps" aria-hidden="true"><span v-for="(step,index) in steps" :key="step" :class="{done:index<view.completed,current:index===view.completed&&state==='processing'}">{{step}}</span></div>
 </section>
</template>
<style scoped>
.analysis-progress{flex-basis:100%;min-width:0;margin:0 0 13px;padding:12px 14px;border:1px solid #e1e8f7;border-radius:10px;background:#f8faff}.progress-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:9px;font-size:12px;color:#617391}.progress-heading strong{font-weight:600;color:#3559ad}.progress-heading>span{white-space:nowrap;font-size:11px}.progress-track{height:7px;background:#e4eafb;border-radius:6px;overflow:hidden}.progress-fill{height:100%;border-radius:6px;background:#5276ee;transition:width .3s ease}.progress-steps{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5px;margin-top:9px;font-size:11px;color:#8796ae}.progress-steps span{text-align:center}.progress-steps .done{color:#4d70c0}.progress-steps .current{color:#315dec;font-weight:600}.progress-indeterminate .progress-fill{width:25%!important;animation:progress-sweep 1.6s ease-in-out infinite}.progress-failed .progress-fill{background:#b77782}.progress-failed .progress-heading strong{color:#a34d60}@keyframes progress-sweep{from{transform:translateX(-100%)}to{transform:translateX(400%)}}@media(prefers-reduced-motion:reduce){.progress-fill{transition:none}.progress-indeterminate .progress-fill{animation:none}}@media(max-width:600px){.progress-heading{align-items:flex-start;flex-direction:column;gap:4px}.progress-steps{font-size:10px}.analysis-progress{padding:10px}}
</style>
''',encoding='utf-8')
edit('desktop/src/App.vue',[
('import VideoWorkspace from', 'import AnalysisProgressBar from \'./AnalysisProgress.vue\'\nimport type { AnalysisProgress } from \'./analysisProgress\'\nimport VideoWorkspace from'),
('type TranscriptionJob = { id: string; status: string;', 'type TranscriptionJob = { id: string; status: string; progress?: AnalysisProgress | null;'),
("const status = ref('请选择本地视频')", "const analysisState = ref('')\nconst analysisProgress = ref<AnalysisProgress|null>(null)\nconst status = ref('请选择本地视频')"),
('function clearLoadedAnalysis() {','function clearLoadedAnalysis() {\n  analysisState.value = \'\'\n  analysisProgress.value = null'),
("      status.value = job.status === 'queued'", "      analysisState.value = job.status\n      analysisProgress.value = job.progress ?? null\n      status.value = job.status === 'queued'"),
("  status.value = '正在临时上传视频…'", "  analysisState.value = 'uploading'\n  analysisProgress.value = null\n  status.value = '正在临时上传视频…'"),
("    await waitForAnalysis(created.id, request)", "    analysisState.value = created.status\n    await waitForAnalysis(created.id, request)"),
("    status.value = '分析未完成'", "    if (analysisState.value !== 'failed') analysisState.value = 'interrupted'\n    status.value = '分析未完成'"),
("  clearLoadedAnalysis()\n  let playbackWarning", "  clearLoadedAnalysis()\n  analysisState.value = 'reading'\n  let playbackWarning"),
("    status.value = '未能读取分析结果'", "    if (analysisState.value !== 'failed') analysisState.value = 'interrupted'\n    status.value = '未能读取分析结果'"),
("  status.value = '正在重新分析保留的上传文件…'", "  analysisState.value = 'queued'\n  analysisProgress.value = null\n  status.value = '正在重新分析保留的上传文件…'"),
('    </header>\n    <aside', '      <AnalysisProgressBar :state="analysisState" :progress="analysisProgress" />\n    </header>\n    <aside'),
])
edit('desktop/src/study-design.css',[('.app-header { grid-column: 1 / -1; display: flex;', '.app-header { grid-column: 1 / -1; display: flex; flex-wrap: wrap; row-gap: 0;')])
