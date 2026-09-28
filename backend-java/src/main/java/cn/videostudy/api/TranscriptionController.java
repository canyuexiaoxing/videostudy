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
                                    @RequestParam(value = "coarseChangePercent", defaultValue = "2") double coarseChangePercent)
                                    throws IOException {
        if (!List.of("ocr_only", "both").contains(visualAnalysisMode))
            return ResponseEntity.badRequest().body(Map.of("error", "invalid_visual_analysis_mode"));
        if (coarseChangePercent != 0.5 && coarseChangePercent != 1.0 &&
            coarseChangePercent != 2.0 && coarseChangePercent != 3.0)
            return ResponseEntity.badRequest().body(Map.of("error", "invalid_coarse_change_percent"));
        if (file.isEmpty()) return ResponseEntity.badRequest().body(Map.of("error", "empty_file"));
        Files.createDirectories(uploadRoot);
        var id = UUID.randomUUID().toString();
        var path = uploadRoot.resolve(id);
        file.transferTo(path);
        var job = new TranscriptionJob(id, "queued", null, null);
        try {
            store.createQueued(id, visualAnalysisMode, coarseChangePercent);
        } catch (RuntimeException error) {
            Files.deleteIfExists(path);
            throw error;
        }
        try {
            worker.execute(() -> process(id, path, visualAnalysisMode, coarseChangePercent));
        } catch (RejectedExecutionException error) {
            store.delete(id);
            Files.deleteIfExists(path);
            return ResponseEntity.status(429).body(Map.of("error", "analysis_queue_full"));
        }
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(job);
    }

    public ResponseEntity<?> upload(MultipartFile file) throws IOException { return upload(file, "both", 2.0); }

    @GetMapping("/{id}")
    public ResponseEntity<?> get(@PathVariable String id) {
        return store.find(id).<ResponseEntity<?>>map(ResponseEntity::ok)
            .orElseGet(() -> ResponseEntity.status(404).body(Map.of("error", "job_not_found")));
    }

    @PostMapping("/{id}/retry")
    public ResponseEntity<?> retry(@PathVariable String id) {
        var existing = store.find(id);
        if (existing.isEmpty()) return ResponseEntity.status(404).body(Map.of("error", "job_not_found"));
        if (!"failed".equals(existing.get().status())) return ResponseEntity.status(409).body(Map.of("error", "job_not_failed"));
        var path = uploadRoot.resolve(id);
        if (!Files.isRegularFile(path)) return ResponseEntity.status(410).body(Map.of("error", "upload_no_longer_available"));
        if (!store.markQueuedIfFailed(id)) return ResponseEntity.status(409).body(Map.of("error", "job_not_failed"));
        try {
            var visualAnalysisMode = store.findVisualAnalysisMode(id);
            var coarseChangePercent = store.findCoarseChangePercent(id);
            worker.execute(() -> process(id, path, visualAnalysisMode == null ? "both" : visualAnalysisMode,
                                          coarseChangePercent));
        } catch (RejectedExecutionException error) {
            store.markFailed(id, "analysis_queue_full");
            return ResponseEntity.status(429).body(Map.of("error", "analysis_queue_full"));
        }
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(new TranscriptionJob(id, "queued", null, null));
    }

    @Scheduled(fixedDelayString = "${media.cleanup-interval-ms:3600000}")
    public void cleanupStaleUploads() {
        var cutoff = Instant.now().minus(Duration.ofHours(24));
        for (var id : store.findOldFailedIds(cutoff)) {
            try {
                store.markExpired(id);
                Files.deleteIfExists(uploadRoot.resolve(id));
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

    private void process(String id, Path path, String visualAnalysisMode, double coarseChangePercent) {
        boolean saved = false;
        try {
            store.markProcessing(id);
            var result = agent.analyze(id, analysisMode, visualAnalysisMode, coarseChangePercent);
            if (result == null) throw new IllegalStateException("Agent returned no transcription result");
            if (analysisMode.equals("full") &&
                (result.review() == null || !List.of("completed", "not_applicable").contains(result.review().status()))) {
                throw new IllegalStateException("Full analysis has not completed Agent review");
            }
            store.complete(id, result);
            saved = true;
            Files.deleteIfExists(path);
        } catch (Exception error) {
            log.warn("Transcription job {} failed", id, error);
            if (!saved) {
                try { store.markFailed(id, analysisMode.equals("full") ? "analysis_failed" : "transcription_failed"); }
                catch (RuntimeException persistenceError) { log.error("Unable to persist failure for job {}", id, persistenceError); }
            }
        }
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
                            ImageAnalysis imageAnalysis, ImageAnalysis textAnalysis) {
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
    public record TranscriptResult(String language, List<TranscriptSegment> segments,
                                   List<VisualEvidence> visualEvidence, String ocrModelId,
                                   String imageModelId, ReviewResult review,
                                   List<PageGroup> pageGroups, List<Long> transitionFrameTimesMs,
                                   String visualAnalysisMode, String groupingVersion, Double coarseChangePercent) {
        public TranscriptResult(String language, List<TranscriptSegment> segments,
                                List<VisualEvidence> visualEvidence, String ocrModelId,
                                String imageModelId, ReviewResult review,
                                List<PageGroup> pageGroups, List<Long> transitionFrameTimesMs,
                                String visualAnalysisMode, String groupingVersion) {
            this(language, segments, visualEvidence, ocrModelId, imageModelId, review,
                 pageGroups, transitionFrameTimesMs, visualAnalysisMode, groupingVersion, null);
        }
        public TranscriptResult(String language, List<TranscriptSegment> segments,
                                List<VisualEvidence> visualEvidence, String ocrModelId,
                                String imageModelId, ReviewResult review) {
            this(language, segments, visualEvidence, ocrModelId, imageModelId, review, null, null, null, null, null);
        }
    }
    public record TranscriptionJob(String id, String status, TranscriptResult result, String error) {}
}
