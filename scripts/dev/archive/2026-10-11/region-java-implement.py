exec(Path(__file__).with_name('region-implement.py').read_text().split("(root/'agent-python/ignored_region.py')")[0]) if False else None
from pathlib import Path
root=Path('E:/workp/videostudy')
def edit(name,changes):
    path=root/name;text=path.read_text(encoding='utf-8')
    for before,after in changes:
        assert before in text,(name,before)
        text=text.replace(before,after)
    path.write_text(text,encoding='utf-8')
base='backend-java/src/main/java/cn/videostudy/api/'
(root/base/'IgnoreRegion.java').write_text('''package cn.videostudy.api;

import com.fasterxml.jackson.databind.ObjectMapper;

/** Rectangle in displayed video coordinates, normalized to [0, 1]. */
public record IgnoreRegion(double x, double y, double width, double height) {
    public IgnoreRegion {
        if (!Double.isFinite(x) || !Double.isFinite(y) || !Double.isFinite(width) || !Double.isFinite(height)
            || x < 0 || y < 0 || width <= 0 || height <= 0 || x + width > 1 + 1e-9
            || y + height > 1 + 1e-9 || width * height > .95)
            throw new IllegalArgumentException("invalid_ignored_region");
        width = Math.min(width, 1 - x); height = Math.min(height, 1 - y);
    }

    public static IgnoreRegion parse(String value) {
        if (value == null || value.isBlank()) return null;
        try {
            var parser = new ObjectMapper();
            try (var tokens = parser.createParser(value)) {
                var node = parser.readTree(tokens);
                if (tokens.nextToken() != null || node == null || !node.isObject() || node.size() != 4)
                    throw new IllegalArgumentException("invalid_ignored_region");
                for (var name : java.util.List.of("x", "y", "width", "height"))
                    if (!node.has(name) || !node.get(name).isNumber())
                        throw new IllegalArgumentException("invalid_ignored_region");
                return new IgnoreRegion(node.get("x").doubleValue(), node.get("y").doubleValue(),
                    node.get("width").doubleValue(), node.get("height").doubleValue());
            }
        } catch (Exception error) { throw new IllegalArgumentException("invalid_ignored_region", error); }
    }
}
''',encoding='utf-8')
(root/'backend-java/src/main/resources/db/migration/V11__ignored_region.sql').write_text('ALTER TABLE transcription_jobs ADD COLUMN ignored_region_json TEXT NULL;\n',encoding='utf-8')
edit(base+'TranscriptionJobStore.java',[
('    public int findCoarseSampleSeconds(String id) {','''    public void createQueued(String id, String visualMode, double threshold, int sampleSeconds, IgnoreRegion region) {
        if (region == null) { createQueued(id, visualMode, threshold, sampleSeconds); return; }
        try {
            jdbc.update("INSERT INTO transcription_jobs (id, status, visual_analysis_mode, coarse_change_percent, coarse_sample_seconds, ignored_region_json) VALUES (?, 'queued', ?, ?, ?, ?)",
                id, visualMode, threshold, sampleSeconds, json.writeValueAsString(region));
        } catch (JsonProcessingException error) { throw new IllegalStateException("Unable to save ignored region", error); }
    }

    public IgnoreRegion findIgnoredRegion(String id) {
        var values = jdbc.query("SELECT ignored_region_json FROM transcription_jobs WHERE id = ?",
            (row, number) -> row.getString(1), id);
        return values.isEmpty() ? null : IgnoreRegion.parse(values.get(0));
    }

    public int findCoarseSampleSeconds(String id) {'''),
])
edit(base+'MediaAnalyzer.java',[
('    default java.util.Map<String,Object> generateSubtitles', '''    default TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualMode,
            double threshold, int sampleSeconds, String callbackToken, IgnoreRegion region) {
        if (region != null) throw new UnsupportedOperationException("Ignored regions are unavailable");
        return analyze(fileId, mode, visualMode, threshold, sampleSeconds, callbackToken);
    }

    default java.util.Map<String,Object> generateSubtitles''')])
edit(base+'HttpMediaAnalyzer.java',[
('        var endpoint = "full".equals(mode) ? "/analyze" : "/transcribe";', '''        return analyze(fileId, mode, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds, subtitleCallbackToken, null);
    }

    @Override public TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode,
            double coarseChangePercent, int coarseSampleSeconds, String subtitleCallbackToken, IgnoreRegion region) {
        var endpoint = "full".equals(mode) ? "/analyze" : "/transcribe";'''),
('        if (subtitleCallbackToken != null)', '        if (region != null) body.put("ignoredRegion", region);\n        if (subtitleCallbackToken != null)'),
])
edit(base+'TranscriptionController.java',[
('                                    @RequestParam(value = "aiSubtitles"', '                                    @RequestParam(value = "ignoredRegion", required = false) String ignoredRegionJson,\n                                    @RequestParam(value = "aiSubtitles"'),
('        if (file.isEmpty())', '''        final IgnoreRegion ignoredRegion;
        try { ignoredRegion = IgnoreRegion.parse(ignoredRegionJson); }
        catch (IllegalArgumentException error) {
            return ResponseEntity.badRequest().body(Map.of("error", "invalid_ignored_region"));
        }
        if (file.isEmpty())'''),
('            store.createQueued(id, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds);', '''            if (ignoredRegion == null) store.createQueued(id, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds);
            else store.createQueued(id, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds, ignoredRegion);'''),
('process(id, path, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds)', 'process(id, path, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds, ignoredRegion)'),
('    public ResponseEntity<?> upload(MultipartFile file, String visualMode, double threshold, boolean', '''    public ResponseEntity<?> upload(MultipartFile file, String visualMode, double threshold, int seconds, boolean aiSubtitles, String targetLanguage) throws IOException {
        return upload(file, visualMode, threshold, seconds, null, aiSubtitles, targetLanguage);
    }
    public ResponseEntity<?> upload(MultipartFile file, String visualMode, double threshold, boolean'''),
('            var coarseSampleSeconds = store.findCoarseSampleSeconds(id);', '            var coarseSampleSeconds = store.findCoarseSampleSeconds(id);\n            var ignoredRegion = store.findIgnoredRegion(id);'),
('coarseChangePercent, coarseSampleSeconds));', 'coarseChangePercent, coarseSampleSeconds, ignoredRegion));'),
('double coarseChangePercent, int coarseSampleSeconds) {','double coarseChangePercent, int coarseSampleSeconds, IgnoreRegion ignoredRegion) {'),
('analyzeWithResume(id, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds)', 'analyzeWithResume(id, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds, ignoredRegion)'),
('double threshold, int sampleSeconds) throws Exception {','double threshold, int sampleSeconds, IgnoreRegion ignoredRegion) throws Exception {'),
('var result = agent.analyze(id, analysisMode, visualMode, threshold, sampleSeconds, callbackToken);','var result = ignoredRegion == null ? agent.analyze(id, analysisMode, visualMode, threshold, sampleSeconds, callbackToken)\n                    : agent.analyze(id, analysisMode, visualMode, threshold, sampleSeconds, callbackToken, ignoredRegion);'),
])
edit('desktop/src/App.vue',[("    form.append('coarseSampleSeconds', String(coarseSampleSeconds.value))", "    form.append('coarseSampleSeconds', String(coarseSampleSeconds.value))\n    if (ignoredRegion.value) form.append('ignoredRegion', JSON.stringify(ignoredRegion.value))")])
edit('desktop/src/VideoWorkspace.vue',[
('当前为前端设置','应用于新分析'),
('区域保存在当前浏览器，并与所选文件关联；尚未接入实际分析。','新分析会忽略框选区域的画面变化。已有任务及重试沿用原设置；截图和 OCR 原始记录完整保留。'),
])
