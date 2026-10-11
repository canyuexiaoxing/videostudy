from pathlib import Path
root=Path(r'E:\workp\videostudy')
def edit(name,old,new,count=1):
 p=root/name;s=p.read_text(encoding='utf-8');assert s.count(old)==count,(name,old,s.count(old));p.write_text(s.replace(old,new),encoding='utf-8')
edit('desktop/src/App.vue',"const coarseChangePercent = ref('2')","const coarseChangePercent = ref('2')\nconst coarseSampleSeconds = ref(2)")
edit('desktop/src/App.vue',"    form.append('coarseChangePercent', coarseChangePercent.value)","    form.append('coarseChangePercent', coarseChangePercent.value)\n    form.append('coarseSampleSeconds', String(coarseSampleSeconds.value))")
edit('desktop/src/App.vue','每隔 2 秒比较一次画面。','按所选采样间隔比较画面。')
edit('desktop/src/App.vue','          <div class="advanced-row">\n            <label for="coarse-change-percent">','''          <div class="advanced-row">
            <span id="coarse-sample-label">粗选采样间隔</span>
            <div class="sampling-options" role="group" aria-labelledby="coarse-sample-label">
              <button v-for="seconds in [2, 3, 4]" :key="seconds" type="button" :aria-pressed="coarseSampleSeconds === seconds" :disabled="isAnalysisPending" @click="coarseSampleSeconds = seconds">{{ seconds }} 秒{{ seconds === 2 ? '（默认）' : '' }}</button>
            </div>
          </div>
          <p class="advanced-help">间隔越长，扫描预览帧越少，但可能漏掉短暂出现的公式、表格或板书。仅影响新分析；重试沿用原任务设置。</p>
          <div class="advanced-row">
            <label for="coarse-change-percent">''')
p=root/'desktop/src/study-design.css';p.write_text(p.read_text(encoding='utf-8')+'''
.sampling-options { display:flex; flex-wrap:wrap; gap:6px; }
.sampling-options button { border:1px solid #d8e1f4; border-radius:7px; padding:7px 12px; color:#536387; background:#fff; cursor:pointer; }
.sampling-options button[aria-pressed="true"] { color:#244fe0; border-color:#9eb6ff; background:#edf2ff; }
.sampling-options button:focus-visible { outline:2px solid #315df5; outline-offset:2px; }
.sampling-options button:disabled { opacity:.5; cursor:default; }
''',encoding='utf-8')
edit('agent-python/app.py','    coarseChangePercent: float = 2.0','    coarseChangePercent: float = 2.0\n    coarseSampleSeconds: Literal[2, 3, 4] = 2')
edit('agent-python/app.py','                                request.subtitleCallbackToken)','                                request.subtitleCallbackToken, coarse_sample_seconds=request.coarseSampleSeconds)')
edit('agent-python/app.py','        return analyze_file(request.fileId, request.visualAnalysisMode, request.coarseChangePercent)','        return analyze_file(request.fileId, request.visualAnalysisMode, request.coarseChangePercent,\n                            coarse_sample_seconds=request.coarseSampleSeconds)')
edit('agent-python/analysis.py','                 subtitle_callback_token: str | None = None) -> dict:','                 subtitle_callback_token: str | None = None, coarse_sample_seconds: int = 2) -> dict:')
edit('agent-python/analysis.py','    UUID(file_id)','    if coarse_sample_seconds not in (2, 3, 4):\n        raise ValueError("coarseSampleSeconds must be 2, 3 or 4")\n    UUID(file_id)')
edit('agent-python/analysis.py',"        'mode': visual_analysis_mode, 'threshold': coarse_change_percent,","        'mode': visual_analysis_mode, 'threshold': coarse_change_percent, 'sampleSeconds': coarse_sample_seconds,")
edit('agent-python/analysis.py','                             page_change_fraction=coarse_change_percent / 100) as visual_worker:','                             page_change_fraction=coarse_change_percent / 100,\n                             sample_seconds=coarse_sample_seconds) as visual_worker:')
edit('agent-python/analysis.py','            "coarseChangePercent": coarse_change_percent,','            "coarseChangePercent": coarse_change_percent,\n            "coarseSampleSeconds": coarse_sample_seconds,')
edit('agent-python/visual_evidence.py','def _candidate_times(path: Path, page_change_fraction: float = PAGE_CHANGE_FRACTION) -> list[int]:','def _candidate_times(path: Path, page_change_fraction: float = PAGE_CHANGE_FRACTION,\n                     sample_seconds: int = SAMPLE_SECONDS) -> list[int]:\n    if sample_seconds not in (2, 3, 4):\n        raise ValueError("sample_seconds must be 2, 3 or 4")')
edit('agent-python/visual_evidence.py','f"fps=1/{SAMPLE_SECONDS},scale=','f"fps=1/{sample_seconds},scale=')
edit('agent-python/visual_evidence.py','time_ms = index * SAMPLE_SECONDS * 1000','time_ms = index * sample_seconds * 1000')
edit('agent-python/visual_evidence.py','                    page_change_fraction: float = PAGE_CHANGE_FRACTION) -> list[dict]:','                    page_change_fraction: float = PAGE_CHANGE_FRACTION,\n                    sample_seconds: int = SAMPLE_SECONDS) -> list[dict]:')
edit('agent-python/visual_evidence.py','_candidate_times(path, page_change_fraction))','_candidate_times(path, page_change_fraction, sample_seconds))')
edit('agent-python/visual_evidence.py','    page_change_fraction = PAGE_CHANGE_FRACTION\n    checkpoint = None','    page_change_fraction = PAGE_CHANGE_FRACTION\n    sample_seconds = SAMPLE_SECONDS\n    checkpoint = None')
edit('agent-python/visual_evidence.py','                    page_change_fraction = request["pageChangeFraction"]','                    page_change_fraction = request["pageChangeFraction"]\n                    sample_seconds = request["sampleSeconds"]')
edit('agent-python/visual_evidence.py','                                               page_change_fraction=page_change_fraction)','                                               page_change_fraction=page_change_fraction, sample_seconds=sample_seconds)')
edit('agent-python/visual_evidence.py','                 page_change_fraction: float = PAGE_CHANGE_FRACTION):','                 page_change_fraction: float = PAGE_CHANGE_FRACTION, sample_seconds: int = SAMPLE_SECONDS):\n        if sample_seconds not in (2, 3, 4):\n            raise ValueError("sample_seconds must be 2, 3 or 4")')
edit('agent-python/visual_evidence.py','                          pageChangeFraction=page_change_fraction)','                          pageChangeFraction=page_change_fraction, sampleSeconds=sample_seconds)')
p=root/'backend-java/src/main/resources/db/migration/V10__coarse_sample_seconds.sql';p.write_text('ALTER TABLE transcription_jobs ADD COLUMN coarse_sample_seconds INT NOT NULL DEFAULT 2;\n',encoding='utf-8')
edit('backend-java/src/main/java/cn/videostudy/api/TranscriptionJobStore.java','    public String findVisualAnalysisMode(String id) {','''    public void createQueued(String id, String visualAnalysisMode, double coarseChangePercent, int sampleSeconds) {
        jdbc.update("INSERT INTO transcription_jobs (id, status, visual_analysis_mode, coarse_change_percent, coarse_sample_seconds) VALUES (?, 'queued', ?, ?, ?)",
            id, visualAnalysisMode, coarseChangePercent, sampleSeconds);
    }

    public int findCoarseSampleSeconds(String id) {
        return jdbc.query("SELECT coarse_sample_seconds FROM transcription_jobs WHERE id = ?",
            (row, number) -> row.getInt(1), id).stream().findFirst().orElse(2);
    }

    public String findVisualAnalysisMode(String id) {''')
edit('backend-java/src/main/java/cn/videostudy/api/MediaAnalyzer.java','    default java.util.Map<String,Object> generateSubtitles','''    default TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode,
            double coarseChangePercent, int coarseSampleSeconds, String subtitleCallbackToken) {
        return subtitleCallbackToken == null ? analyze(fileId, mode, visualAnalysisMode, coarseChangePercent)
            : analyze(fileId, mode, visualAnalysisMode, coarseChangePercent, subtitleCallbackToken);
    }

    default java.util.Map<String,Object> generateSubtitles''')
edit('backend-java/src/main/java/cn/videostudy/api/HttpMediaAnalyzer.java','        var endpoint = "full".equals(mode) ? "/analyze" : "/transcribe";','''        return analyze(fileId, mode, visualAnalysisMode, coarseChangePercent, 2, subtitleCallbackToken);
    }

    @Override public TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode,
            double coarseChangePercent, int coarseSampleSeconds, String subtitleCallbackToken) {
        var endpoint = "full".equals(mode) ? "/analyze" : "/transcribe";''')
edit('backend-java/src/main/java/cn/videostudy/api/HttpMediaAnalyzer.java','        body.put("coarseChangePercent", coarseChangePercent);','        body.put("coarseChangePercent", coarseChangePercent);\n        body.put("coarseSampleSeconds", coarseSampleSeconds);')
name='backend-java/src/main/java/cn/videostudy/api/TranscriptionController.java'
edit(name,'                                    @RequestParam(value = "aiSubtitles",','                                    @RequestParam(value = "coarseSampleSeconds", defaultValue = "2") int coarseSampleSeconds,\n                                    @RequestParam(value = "aiSubtitles",')
edit(name,'        if (file.isEmpty())','        if (!List.of(2, 3, 4).contains(coarseSampleSeconds))\n            return ResponseEntity.badRequest().body(Map.of("error", "invalid_coarse_sample_seconds"));\n        if (file.isEmpty())')
edit(name,'store.createQueued(id, visualAnalysisMode, coarseChangePercent);','store.createQueued(id, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds);')
edit(name,'process(id, path, visualAnalysisMode, coarseChangePercent)','process(id, path, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds)')
edit(name,'    public ResponseEntity<?> upload(MultipartFile file, String visualMode, double threshold) throws IOException {','''    public ResponseEntity<?> upload(MultipartFile file, String visualMode, double threshold, boolean aiSubtitles, String targetLanguage) throws IOException {
        return upload(file, visualMode, threshold, 2, aiSubtitles, targetLanguage);
    }
    public ResponseEntity<?> upload(MultipartFile file, String visualMode, double threshold) throws IOException {''')
edit(name,'            var coarseChangePercent = store.findCoarseChangePercent(id);','            var coarseChangePercent = store.findCoarseChangePercent(id);\n            var coarseSampleSeconds = store.findCoarseSampleSeconds(id);')
edit(name,'                                          coarseChangePercent));','                                          coarseChangePercent, coarseSampleSeconds));')
edit(name,'private void process(String id, Path path, String visualAnalysisMode, double coarseChangePercent)','private void process(String id, Path path, String visualAnalysisMode, double coarseChangePercent, int coarseSampleSeconds)')
edit(name,'analyzeWithResume(id, visualAnalysisMode, coarseChangePercent)','analyzeWithResume(id, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds)')
edit(name,'private TranscriptResult analyzeWithResume(String id, String visualMode, double threshold)','private TranscriptResult analyzeWithResume(String id, String visualMode, double threshold, int sampleSeconds)')
edit(name,'''                var result = callbackToken == null ? agent.analyze(id, analysisMode, visualMode, threshold)
                    : agent.analyze(id, analysisMode, visualMode, threshold, callbackToken);''','''                var result = agent.analyze(id, analysisMode, visualMode, threshold, sampleSeconds, callbackToken);''')
# Existing verification of task creation now includes the new default setting.
p=root/'backend-java/src/test/java/cn/videostudy/api/TranscriptionControllerTest.java';s=p.read_text(encoding='utf-8');s=s.replace('org.mockito.ArgumentMatchers.eq(2.0));','org.mockito.ArgumentMatchers.eq(2.0), org.mockito.ArgumentMatchers.eq(2));').replace('org.mockito.ArgumentMatchers.eq(3.0));','org.mockito.ArgumentMatchers.eq(3.0), org.mockito.ArgumentMatchers.eq(2));');p.write_text(s,encoding='utf-8')
p=root/'docs/superpowers/specs/2026-10-10-coarse-sampling-interval.md';p.write_text('''# 粗选采样间隔
用户要求在高级选项加入按钮。提供2秒、3秒、4秒，默认2秒；处理中禁用切换。
仅影响新分析任务的低分辨率预览采样，变化阈值和0.5秒补采时间粒度不变。
前端上传 coarseSampleSeconds，Java验证并用V10保存，失败重试复用原设置；旧任务默认2秒。
Python验证并传入常驻视觉工作进程，FFmpeg采样滤镜及时间计算使用同一间隔；分析缓存包含间隔，避免跨设置复用。
验证实际滤镜及候选时间计算、参数传递、持久化、重试、非法输入和缓存隔离，前端构建及浏览器操作。不调用付费模型或重跑整课。
''',encoding='utf-8')
