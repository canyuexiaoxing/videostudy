package cn.videostudy.api;

import jakarta.annotation.PreDestroy;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.time.Instant;
import java.time.Duration;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@RestController
@RequestMapping("/api/transcriptions")
@CrossOrigin(origins = {"http://localhost:5173", "http://127.0.0.1:5173"})
public class TranscriptionController {
    private static final Logger log = LoggerFactory.getLogger(TranscriptionController.class);
    private final Path uploadRoot;
    private final MediaAnalyzer agent;
    private final String analysisMode;
    private final TranscriptionJobStore store;
    @org.springframework.beans.factory.annotation.Autowired(required = false)
    private SubtitleService subtitles;
    @org.springframework.beans.factory.annotation.Autowired(required = false)
    private ChapterController chapters;
    @org.springframework.beans.factory.annotation.Autowired(required = false)
    private OverviewController overviews;
    @Value("${analysis.stage-attempts:2}") private int stageAttempts = 2;
    @Value("${keyframe.dir:../.local/keyframes}") private String keyframeDirectory;
    private final Object runLock = new Object();
    private final java.util.Map<String,Object> activeRuns = new java.util.concurrent.ConcurrentHashMap<>();
    private final ThreadPoolExecutor worker = new ThreadPoolExecutor(
        1, 1, 0L, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(4));

    public TranscriptionController(@Value("${media.temp-dir}") String tempDir,
                                   @Value("${analysis.mode:transcription}") String analysisMode,
                                   TranscriptionJobStore store,
                                   MediaAnalyzer agent) {
        uploadRoot = Path.of(tempDir).toAbsolutePath().normalize();
        if (!analysisMode.equals("transcription") && !analysisMode.equals("full")) {
            throw new IllegalArgumentException("ANALYSIS_MODE must be transcription or full");
        }
        this.analysisMode = analysisMode;
        this.store = store;
        this.agent = agent;
    }

    @PostMapping
    public ResponseEntity<?> upload(@RequestParam("file") MultipartFile file,
                                    @RequestParam(value = "visualAnalysisMode", defaultValue = "both") String visualAnalysisMode,
                                    @RequestParam(value = "coarseChangePercent", defaultValue = "3") double coarseChangePercent,
                                    @RequestParam(value = "coarseSampleSeconds", defaultValue = "2") int coarseSampleSeconds,
                                    @RequestParam(value = "ignoredRegion", required = false) String ignoredRegionJson,
                                    @RequestParam(value = "groupedAnalysis", defaultValue = "false") boolean groupedAnalysis,
                                    @RequestParam(value = "aiSubtitles", defaultValue = "false") boolean aiSubtitles,
                                    @RequestParam(value = "subtitleTargetLanguage", defaultValue = "source") String subtitleTargetLanguage,
                                    @RequestParam(value = "mindMapMode", required = false) String requestedMapMode,
                                    @RequestParam(value = "personSelectionMode", required = false) String personSelectionMode)
                                    throws IOException {
        if (personSelectionMode != null && !List.of("off","adjacent").contains(personSelectionMode))
            return ResponseEntity.badRequest().body(Map.of("error","invalid_person_selection_mode"));
        final String mindMapMode=requestedMapMode==null?(groupedAnalysis?"grouped":"legacy"):requestedMapMode;
        if (!List.of("legacy","grouped","direct").contains(mindMapMode))
            return ResponseEntity.badRequest().body(Map.of("error","invalid_mind_map_mode"));
        groupedAnalysis="grouped".equals(mindMapMode);
        if (!"legacy".equals(mindMapMode) && (!"both".equals(visualAnalysisMode) || !"full".equals(analysisMode)))
            return ResponseEntity.badRequest().body(Map.of("error","mind_map_mode_requires_full_images"));
        if (!List.of("source", "zh", "en").contains(subtitleTargetLanguage))
            return ResponseEntity.badRequest().body(Map.of("error", "invalid_subtitle_target_language"));
        if (!List.of("ocr_only", "both").contains(visualAnalysisMode))
            return ResponseEntity.badRequest().body(Map.of("error", "invalid_visual_analysis_mode"));
        if (groupedAnalysis && !"both".equals(visualAnalysisMode))
            return ResponseEntity.badRequest().body(Map.of("error", "grouped_analysis_requires_images"));
        if (coarseChangePercent != 0.5 && coarseChangePercent != 1.0 &&
            coarseChangePercent != 2.0 && coarseChangePercent != 3.0 &&
            coarseChangePercent != 4.0 && coarseChangePercent != 5.0)
            return ResponseEntity.badRequest().body(Map.of("error", "invalid_coarse_change_percent"));
        if (!List.of(2, 3, 4).contains(coarseSampleSeconds))
            return ResponseEntity.badRequest().body(Map.of("error", "invalid_coarse_sample_seconds"));
        final IgnoreRegion ignoredRegion;
        try { ignoredRegion = IgnoreRegion.parse(ignoredRegionJson); }
        catch (IllegalArgumentException error) {
            return ResponseEntity.badRequest().body(Map.of("error", "invalid_ignored_region"));
        }
        if (file.isEmpty()) return ResponseEntity.badRequest().body(Map.of("error", "empty_file"));
        Files.createDirectories(uploadRoot);
        var id = UUID.randomUUID().toString();
        var path = uploadRoot.resolve(id);
        file.transferTo(path);
        var job = new TranscriptionJob(id, "queued", null, null);
        try {
            if (ignoredRegion == null) store.createQueued(id, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds);
            else store.createQueued(id, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds, ignoredRegion);
            store.saveGroupedAnalysis(id, groupedAnalysis);
            store.saveMindMapMode(id,mindMapMode);
            if (personSelectionMode != null) store.savePersonSelectionMode(id,personSelectionMode);
            store.saveOriginalFilename(id, file.getOriginalFilename());
            if (aiSubtitles && subtitles != null) subtitles.createUploadRequest(id, subtitleTargetLanguage);
        } catch (RuntimeException error) {
            store.delete(id);
            Files.deleteIfExists(path);
            throw error;
        }
        try {
            queueAnalysis(id, path, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds, ignoredRegion, groupedAnalysis, mindMapMode, personSelectionMode);
        } catch (RejectedExecutionException error) {
            store.delete(id);
            Files.deleteIfExists(path);
            return ResponseEntity.status(429).body(Map.of("error", "analysis_queue_full"));
        }
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(job);
    }

    public ResponseEntity<?> upload(MultipartFile file, String visualMode, double threshold, int seconds, String ignoredRegion, boolean groupedAnalysis, boolean aiSubtitles, String targetLanguage, String mindMapMode) throws IOException {
        return upload(file,visualMode,threshold,seconds,ignoredRegion,groupedAnalysis,aiSubtitles,targetLanguage,mindMapMode,null);
    }
    public ResponseEntity<?> upload(MultipartFile file, String visualMode, double threshold, int seconds, String ignoredRegion, boolean groupedAnalysis, boolean aiSubtitles, String targetLanguage) throws IOException {
        return upload(file,visualMode,threshold,seconds,ignoredRegion,groupedAnalysis,aiSubtitles,targetLanguage,null);
    }
    public ResponseEntity<?> upload(MultipartFile file, String visualMode, double threshold, int seconds, String ignoredRegion, boolean aiSubtitles, String targetLanguage) throws IOException {
        return upload(file, visualMode, threshold, seconds, ignoredRegion, false, aiSubtitles, targetLanguage);
    }
    public ResponseEntity<?> upload(MultipartFile file, String visualMode, double threshold, int seconds, boolean aiSubtitles, String targetLanguage) throws IOException {
        return upload(file, visualMode, threshold, seconds, null, aiSubtitles, targetLanguage);
    }
    public ResponseEntity<?> upload(MultipartFile file, String visualMode, double threshold, boolean aiSubtitles, String targetLanguage) throws IOException {
        return upload(file, visualMode, threshold, 2, aiSubtitles, targetLanguage);
    }
    public ResponseEntity<?> upload(MultipartFile file, String visualMode, double threshold) throws IOException {
        return upload(file, visualMode, threshold, true, "source");
    }
    public ResponseEntity<?> upload(MultipartFile file) throws IOException { return upload(file, "both", 3.0); }

    @GetMapping
    public List<TranscriptionJobStore.HistoryItem> history() { return store.listHistory(); }

    @GetMapping("/{id}")
    public ResponseEntity<?> get(@PathVariable String id) {
        return store.find(id).<ResponseEntity<?>>map(job -> ResponseEntity.ok(new TranscriptionJob(
            job.id(), job.status(), job.result(), job.error(), readProgress(job.id(), job.status()))))
            .orElseGet(() -> ResponseEntity.status(404).body(Map.of("error", "job_not_found")));
    }

    @PostMapping("/{id}/retry")
    public ResponseEntity<?> retry(@PathVariable String id) {
        var existing = store.find(id);
        if (existing.isEmpty()) return ResponseEntity.status(404).body(Map.of("error", "job_not_found"));
        if (!"failed".equals(existing.get().status())) return ResponseEntity.status(409).body(Map.of("error", "job_not_failed"));
        var path = uploadRoot.resolve(id);
        if (!Files.isRegularFile(path)) return ResponseEntity.status(410).body(Map.of("error", "upload_no_longer_available"));
        synchronized (runLock) {
            try { agent.resetAnalysis(id); }
            catch (RuntimeException error) { return ResponseEntity.status(502).body(Map.of("error", "analysis_reset_failed")); }
            if (!store.markQueuedIfFailed(id)) return ResponseEntity.status(409).body(Map.of("error", "job_not_failed"));
        }
        try {
            var visualAnalysisMode = store.findVisualAnalysisMode(id);
            var coarseChangePercent = store.findCoarseChangePercent(id);
            var coarseSampleSeconds = store.findCoarseSampleSeconds(id);
            var ignoredRegion = store.findIgnoredRegion(id);
            var groupedAnalysis = store.findGroupedAnalysis(id);
            var mindMapMode=store.findMindMapMode(id);
            var personSelectionMode=store.findPersonSelectionMode(id);
            if (mindMapMode==null) mindMapMode=groupedAnalysis?"grouped":"legacy";
            queueAnalysis(id, path, visualAnalysisMode == null ? "both" : visualAnalysisMode,
                                          coarseChangePercent, coarseSampleSeconds, ignoredRegion, groupedAnalysis, mindMapMode, personSelectionMode);
        } catch (RejectedExecutionException error) {
            store.markFailed(id, "analysis_queue_full");
            return ResponseEntity.status(429).body(Map.of("error", "analysis_queue_full"));
        }
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(new TranscriptionJob(id, "queued", null, null));
    }

    @PostMapping("/{id}/cancel")
    public ResponseEntity<?> cancel(@PathVariable String id) {
        if (!SubtitleController.validId(id)) return ResponseEntity.badRequest().build();
        if (store.find(id).isEmpty()) return ResponseEntity.notFound().build();
        boolean notified = true;
        synchronized (runLock) {
            if (!store.cancel(id)) return ResponseEntity.status(409).body(Map.of("error", "job_not_active"));
            activeRuns.remove(id);
            try { agent.cancelAnalysis(id); }
            catch (RuntimeException error) { notified = false; log.warn("Agent cancellation notification failed for {}", id); }
        }
        return ResponseEntity.ok(Map.of("status", "cancelled", "agentNotified", notified));
    }

    @Scheduled(fixedDelayString = "${media.cleanup-interval-ms:3600000}")
    public void cleanupStaleUploads() {
        var cutoff = Instant.now().minus(Duration.ofHours(24));
        for (var id : store.findOldFailedIds(cutoff)) {
            try {
                store.markExpired(id);
                Files.deleteIfExists(uploadRoot.resolve(id));
                deleteTaskDirectory(id, false);
            } catch (Exception error) {
                log.warn("Unable to clean failed upload {}", id, error);
            }
        }
        for (var id : store.findOldCompletedIds(cutoff)) {
            try { Files.deleteIfExists(uploadRoot.resolve(id)); }
            catch (IOException error) { log.warn("Unable to clean completed upload {}", id, error); }
        }
    }

    @EventListener(ApplicationReadyEvent.class)
    public void recoverInterruptedJobs() {
        int count = store.recoverInterruptedJobs();
        if (count > 0) log.info("Marked {} interrupted analysis jobs as retryable", count);
    }

    private void queueAnalysis(String id, Path path, String visualMode, double threshold, int seconds, IgnoreRegion region, boolean groupedAnalysis, String mindMapMode, String personSelectionMode) {
        var token = new Object();
        activeRuns.put(id, token);
        try { worker.execute(() -> process(id, path, visualMode, threshold, seconds, region, groupedAnalysis, mindMapMode, personSelectionMode, token)); }
        catch (RejectedExecutionException error) { activeRuns.remove(id, token); throw error; }
    }
    private void process(String id, Path path, String visualAnalysisMode, double coarseChangePercent, int coarseSampleSeconds, IgnoreRegion ignoredRegion, boolean groupedAnalysis, String mindMapMode, String personSelectionMode, Object token) {
        boolean saved = false;
        try {
            synchronized (runLock) {
                if (activeRuns.get(id) != token) return;
                store.markProcessing(id);
                if (personSelectionMode != null) log.info("Analysis {} person filtering {}", id, personSelectionMode);
            }
            var result = analyzeWithResume(id, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds, ignoredRegion, groupedAnalysis, mindMapMode, personSelectionMode, token);
            if (result == null) throw new IllegalStateException("Agent returned no transcription result");
            if (result.mindMap() != null && !MindMapValidator.isGrounded(result.mindMap(), result.segments(), result.visualEvidence()))
                throw new IllegalStateException("Agent returned an ungrounded mind map");
            if (analysisMode.equals("full") &&
                (result.review() == null || !List.of("completed", "not_applicable").contains(result.review().status()))) {
                throw new IllegalStateException("Full analysis has not completed Agent review");
            }
            synchronized (runLock) {
                if (activeRuns.get(id) != token) return;
                store.complete(id, result);
                saved = true;
                activeRuns.remove(id, token);
            }
            if (overviews != null && result.mindMap()!=null && "completed".equals(result.mindMap().status())) {
                try { overviews.request(id); }
                catch (RuntimeException error) { log.warn("Overview dispatch deferred for {}", id); }
            }
            if (chapters != null) {
                try { chapters.request(id); }
                catch (RuntimeException error) { log.warn("Chapter dispatch deferred for {}", id); }
            }
            if (subtitles != null) {
                try { subtitles.captureFallback(id, result); }
                catch (RuntimeException error) { log.warn("Subtitle source fallback deferred for {} ({})", id, error.getClass().getSimpleName()); }
            }
            Files.deleteIfExists(path);
            deleteTaskDirectory(id, true);
        } catch (Exception error) {
            log.warn("Transcription job {} failed", id, error);
            synchronized (runLock) {
                if (!saved && activeRuns.get(id) == token) {
                    try { store.markFailed(id, analysisMode.equals("full") ? "analysis_failed" : "transcription_failed"); }
                    catch (RuntimeException persistenceError) { log.error("Unable to persist failure for job {}", id, persistenceError); }
                    if (subtitles != null) subtitles.sourceUnavailable(id);
                }
            }
        } finally { activeRuns.remove(id, token); }
    }

    private TranscriptResult analyzeWithResume(String id, String visualMode, double threshold, int sampleSeconds, IgnoreRegion ignoredRegion, boolean groupedAnalysis, String mindMapMode, String personSelectionMode, Object token) throws Exception {
        String callbackToken = null;
        if (subtitles != null) {
            try { callbackToken = subtitles.callbackToken(id); }
            catch (RuntimeException error) { log.warn("Subtitle callback unavailable for {} ({})", id, error.getClass().getSimpleName()); }
        }
        for (int attempt = 1; ; attempt++) {
            try {
                clearProgress(id);
                if (activeRuns.get(id) != token) throw new IllegalStateException("Analysis cancelled");
                var result = personSelectionMode != null ? agent.analyze(id, analysisMode, visualMode, threshold, sampleSeconds, callbackToken, ignoredRegion, groupedAnalysis, mindMapMode, personSelectionMode)
                    : "direct".equals(mindMapMode) ? agent.analyze(id, analysisMode, visualMode, threshold, sampleSeconds, callbackToken, ignoredRegion, false, "direct")
                    : groupedAnalysis ? agent.analyze(id, analysisMode, visualMode, threshold, sampleSeconds, callbackToken, ignoredRegion, true)
                    : ignoredRegion == null ? agent.analyze(id, analysisMode, visualMode, threshold, sampleSeconds, callbackToken)
                    : agent.analyze(id, analysisMode, visualMode, threshold, sampleSeconds, callbackToken, ignoredRegion);
                if (result != null && analysisMode.equals("full") && "legacy".equals(mindMapMode)) {
                    if (result.mindMap() != null && "failed".equals(result.mindMap().status()))
                        throw new IllegalStateException("Mind-map chunks incomplete; resume successful checkpoints");
                    if (result.pageGroups() != null && result.pageGroups().stream().anyMatch(page ->
                        (page.imageAnalysis() != null && "failed".equals(page.imageAnalysis().status())) ||
                        (page.textAnalysis() != null && "failed".equals(page.textAnalysis().status()))))
                        throw new IllegalStateException("Page analysis incomplete; resume successful checkpoints");
                }
                return result;
            } catch (Exception error) {
                boolean permanent = error instanceof org.springframework.web.client.RestClientResponseException response &&
                    response.getStatusCode().is4xxClientError() && response.getStatusCode().value() != 429;
                if (activeRuns.get(id) != token || permanent || attempt >= Math.max(1, stageAttempts) || Thread.currentThread().isInterrupted()) throw error;
                log.warn("Job {} automatically resuming after attempt {}: {}", id, attempt, error.getClass().getSimpleName());
                Thread.sleep(500);
            }
        }
    }

    private Path progressPath(String id) {
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
            if (json == null || !json.isObject() || !json.has("stage") || !json.get("stage").isTextual()) return null;
            for (var key : List.of("completedStages", "totalStages", "completedUnits", "totalUnits"))
                if (!json.has(key) || !json.get(key).isIntegralNumber() || !json.get(key).canConvertToInt()) return null;
            var stage = json.get("stage").textValue();
            int completed = json.get("completedStages").intValue(), total = json.get("totalStages").intValue();
            int units = json.get("completedUnits").intValue(), count = json.get("totalUnits").intValue();
            var stages = Map.of("media", 0, "coverage", 1, "grouping", 2, "pages", 3, "groups", 3, "materials", 4, "saving", 4);
            if (!stages.containsKey(stage) || completed != stages.get(stage) || total != 5 || count < 0 || units < 0 || units > count) return null;
            return new AnalysisProgress(stage, completed, total, units, count, json.path("phase").asText(null), nullableInt(json,"readyGroups"), nullableInt(json,"completedGroups"), nullableInt(json,"totalGroups"), json.path("groupPhase").asText(null));
        } catch (IOException | IllegalArgumentException error) { return null; }
    }

    private static Integer nullableInt(com.fasterxml.jackson.databind.JsonNode json, String name) {
        var value = json.get(name);
        return value != null && value.isIntegralNumber() && value.canConvertToInt() && value.intValue() >= 0 ? value.intValue() : null;
    }

    private void deleteTaskDirectory(String id, boolean checkpointsOnly) throws IOException {
        // Unit-test constructor calls may not have Spring-injected storage configuration.
        if (keyframeDirectory == null) return;
        var root = Path.of(keyframeDirectory).toAbsolutePath().normalize();
        var target = root.resolve(UUID.fromString(id).toString());
        if (checkpointsOnly) target = target.resolve(".analysis");
        if (!target.startsWith(root) || target.equals(root)) throw new IllegalArgumentException("Invalid task path");
        if (!Files.exists(target)) return;
        Files.walkFileTree(target, new java.nio.file.SimpleFileVisitor<>() {
            @Override public java.nio.file.FileVisitResult visitFile(Path file, java.nio.file.attribute.BasicFileAttributes attrs) throws IOException {
                Files.delete(file); return java.nio.file.FileVisitResult.CONTINUE;
            }
            @Override public java.nio.file.FileVisitResult postVisitDirectory(Path dir, IOException error) throws IOException {
                if (error != null) throw error;
                Files.delete(dir); return java.nio.file.FileVisitResult.CONTINUE;
            }
        });
    }

    @PreDestroy
    public void close() { worker.shutdownNow(); }

    public record TranscriptSegment(String id, long startMs, long endMs, String text) {}
    public record OcrBlock(String text, double score, List<List<Integer>> polygon) {}
    public record ImageAnalysis(String status, String title, String content, List<String> visualElements,
                                List<String> uncertainties) {}
    public record VisualEvidence(long frameTimeMs, List<OcrBlock> ocrBlocks, ImageAnalysis imageAnalysis) {}
    public record OcrLine(String text, long sourceFrameTimeMs, int sourceBlockIndex) {}
    public record PageGroup(int pageIndex, long firstFrameTimeMs, long lastFrameTimeMs,
                            List<Long> memberFrameTimesMs, List<Long> representativeFrameTimesMs,
                            String decision, String decisionReason, List<OcrLine> ocrLines,
                            ImageAnalysis imageAnalysis, ImageAnalysis textAnalysis, Map<String,Object> groupUnderstanding) {
        public PageGroup(int pageIndex, long firstFrameTimeMs, long lastFrameTimeMs, List<Long> memberFrameTimesMs, List<Long> representativeFrameTimesMs, String decision, String decisionReason, List<OcrLine> ocrLines, ImageAnalysis imageAnalysis, ImageAnalysis textAnalysis) {
            this(pageIndex, firstFrameTimeMs, lastFrameTimeMs, memberFrameTimesMs, representativeFrameTimesMs, decision, decisionReason, ocrLines, imageAnalysis, textAnalysis, null);
        }
        public PageGroup(int pageIndex, long firstFrameTimeMs, long lastFrameTimeMs,
                         List<Long> memberFrameTimesMs, List<Long> representativeFrameTimesMs,
                         String decision, String decisionReason, List<OcrLine> ocrLines,
                         ImageAnalysis imageAnalysis) {
            this(pageIndex, firstFrameTimeMs, lastFrameTimeMs, memberFrameTimesMs,
                 representativeFrameTimesMs, decision, decisionReason, ocrLines, imageAnalysis, null);
        }
    }
    public record ReviewResult(String status, String provider, String modelId, String promptVersion,
                               List<Long> resampledTimesMs, List<String> concerns) {}
    public record MindMapEvidence(String sourceType, String sourceId, long startMs, long endMs, String quote) {}
    public record MindMapNode(String id, String title, long startMs, long endMs,
                              List<MindMapEvidence> evidenceRefs, List<MindMapNode> children, List<MindMapNode> details) {
        public MindMapNode(String id, String title, long startMs, long endMs, List<MindMapEvidence> evidenceRefs, List<MindMapNode> children) {
            this(id, title, startMs, endMs, evidenceRefs, children, null);
        }
    }
    public record MindMapResult(String status, String provider, String modelId, String promptVersion,
                                String createdAt, MindMapNode root, List<MindMapNode> examples, List<String> uncertainties) {
        public MindMapResult(String status, String provider, String modelId, String promptVersion, String createdAt, MindMapNode root, List<MindMapNode> examples) {
            this(status, provider, modelId, promptVersion, createdAt, root, examples, null);
        }
        public MindMapResult(String status, String provider, String modelId, String promptVersion, String createdAt, MindMapNode root) {
            this(status, provider, modelId, promptVersion, createdAt, root, null);
        }
        public MindMapResult(String status, String modelId, String promptVersion, MindMapNode root) {
            this(status, null, modelId, promptVersion, null, root);
        }
    }
    public record TranscriptResult(String language, List<TranscriptSegment> segments,
                                   List<VisualEvidence> visualEvidence, String ocrModelId,
                                   String imageModelId, ReviewResult review,
                                   List<PageGroup> pageGroups, List<Long> transitionFrameTimesMs,
                                   String visualAnalysisMode, String groupingVersion, Double coarseChangePercent,
                                   MindMapResult mindMap, Map<String, Long> stageTimingsMs,
                                   Map<String, Integer> reusedCheckpoints, Map<String,Object> overview) {
        public TranscriptResult(String language,List<TranscriptSegment> segments,List<VisualEvidence> visualEvidence,
                                String ocrModelId,String imageModelId,ReviewResult review,List<PageGroup> pageGroups,
                                List<Long> transitionFrameTimesMs,String visualAnalysisMode,String groupingVersion,
                                Double coarseChangePercent,MindMapResult mindMap,Map<String,Long> stageTimingsMs,
                                Map<String,Integer> reusedCheckpoints) {
            this(language,segments,visualEvidence,ocrModelId,imageModelId,review,pageGroups,transitionFrameTimesMs,
                 visualAnalysisMode,groupingVersion,coarseChangePercent,mindMap,stageTimingsMs,reusedCheckpoints,null);
        }
        public TranscriptResult(String language, List<TranscriptSegment> segments,
                                List<VisualEvidence> visualEvidence, String ocrModelId,
                                String imageModelId, ReviewResult review,
                                List<PageGroup> pageGroups, List<Long> transitionFrameTimesMs,
                                String visualAnalysisMode, String groupingVersion, Double coarseChangePercent,
                                MindMapResult mindMap) {
            this(language, segments, visualEvidence, ocrModelId, imageModelId, review, pageGroups,
                 transitionFrameTimesMs, visualAnalysisMode, groupingVersion, coarseChangePercent,
                 mindMap, null, null);
        }
        public TranscriptResult withMindMap(MindMapResult updated) {
            return new TranscriptResult(language, segments, visualEvidence, ocrModelId, imageModelId, review,
                pageGroups, transitionFrameTimesMs, visualAnalysisMode, groupingVersion, coarseChangePercent, updated,
                stageTimingsMs, reusedCheckpoints, overview);
        }
        public TranscriptResult(String language, List<TranscriptSegment> segments,
                                List<VisualEvidence> visualEvidence, String ocrModelId,
                                String imageModelId, ReviewResult review,
                                List<PageGroup> pageGroups, List<Long> transitionFrameTimesMs,
                                String visualAnalysisMode, String groupingVersion, Double coarseChangePercent) {
            this(language, segments, visualEvidence, ocrModelId, imageModelId, review,
                 pageGroups, transitionFrameTimesMs, visualAnalysisMode, groupingVersion, coarseChangePercent, null);
        }
        public TranscriptResult(String language, List<TranscriptSegment> segments,
                                List<VisualEvidence> visualEvidence, String ocrModelId,
                                String imageModelId, ReviewResult review,
                                List<PageGroup> pageGroups, List<Long> transitionFrameTimesMs,
                                String visualAnalysisMode, String groupingVersion) {
            this(language, segments, visualEvidence, ocrModelId, imageModelId, review,
                 pageGroups, transitionFrameTimesMs, visualAnalysisMode, groupingVersion, null, null);
        }
        public TranscriptResult(String language, List<TranscriptSegment> segments,
                                List<VisualEvidence> visualEvidence, String ocrModelId,
                                String imageModelId, ReviewResult review) {
            this(language, segments, visualEvidence, ocrModelId, imageModelId, review, null, null, null, null, null, null);
        }
    }
    public record AnalysisProgress(String stage, int completedStages, int totalStages, int completedUnits, int totalUnits, String phase, Integer readyGroups, Integer completedGroups, Integer totalGroups, String groupPhase) {
        public AnalysisProgress(String stage, int completedStages, int totalStages, int completedUnits, int totalUnits) { this(stage, completedStages, totalStages, completedUnits, totalUnits, null, null, null, null, null); }
    }
    public record TranscriptionJob(String id, String status, TranscriptResult result, String error, AnalysisProgress progress) {
        public TranscriptionJob(String id, String status, TranscriptResult result, String error) {
            this(id, status, result, error, null);
        }
    }
}
