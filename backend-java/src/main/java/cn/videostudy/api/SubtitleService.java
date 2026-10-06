package cn.videostudy.api;

import jakarta.annotation.PreDestroy;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;

@Service
public class SubtitleService {
    private static final Logger log = LoggerFactory.getLogger(SubtitleService.class);
    private final SubtitleJobStore store;
    private final TranscriptionJobStore transcriptions;
    private final MediaAnalyzer analyzer;
    @Value("${subtitles.attempts:3}") private int maxAttempts = 3;
    private final ThreadPoolExecutor worker = new ThreadPoolExecutor(2, 2, 0L, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(4));
    private final Set<SubtitleJobStore.Key> dispatched = ConcurrentHashMap.newKeySet();

    public SubtitleService(SubtitleJobStore store, TranscriptionJobStore transcriptions, MediaAnalyzer analyzer) {
        this.store = store; this.transcriptions = transcriptions; this.analyzer = analyzer;
    }
    public void createUploadRequest(String id, String target) { store.createUploadRequest(id, correctionTarget(id, target)); }
    public String callbackToken(String id) { return store.callbackToken(id); }
    public void sourceUnavailable(String id) {
        try { store.sourceUnavailable(id); }
        catch (RuntimeException error) { log.warn("Subtitle source status deferred for {} ({})", id, error.getClass().getSimpleName()); }
    }
    public SubtitleJobStore.Job get(String id, String target) {
        return store.find(id, correctionTarget(id, target)).orElse(new SubtitleJobStore.Job(id, "not_requested", null, null));
    }
    public SubtitleJobStore.Job request(String id, String target) {
        return request(id, target, false);
    }
    public SubtitleJobStore.Job request(String id, String target, boolean force) {
        store.request(id, correctionTarget(id, target), true, force);
        var main = transcriptions.find(id);
        if (main.isPresent() && main.get().result() != null) captureFallback(id, main.get().result());
        drainQueued(); return get(id, target);
    }
    /** Same-language selection is an alias of correction, never another model job. */
    private String correctionTarget(String id, String target) {
        String language = store.source(id).map(SubtitleJobStore.Source::language).orElseGet(() ->
            transcriptions.find(id).filter(job -> job.result() != null)
                .map(job -> job.result().language()).orElse(""));
        language = language == null ? "" : language.toLowerCase(Locale.ROOT).split("[-_]", 2)[0];
        if (!List.of("zh", "en").contains(language) || !(target.equals("source") || target.equals(language))) return target;
        // Legacy courses may have only an explicit-language result. Reuse it;
        // if both exist, always expose the source result for both selections.
        if (store.find(id, "source").isPresent()) return "source";
        return store.find(id, language).isPresent() ? language : "source";
    }
    public boolean acceptSource(String id, String token, SubtitleJobStore.Source source) {
        boolean captured = store.captureSource(id, token, source);
        if (captured) dispatchSafely();
        return captured;
    }
    public void captureFallback(String id, TranscriptionController.TranscriptResult result) {
        store.captureFallback(id, new SubtitleJobStore.Source(result.language(), result.segments(), result.pageGroups()));
        dispatchSafely();
    }
    private void dispatchSafely() {
        try { drainQueued(); }
        catch (RuntimeException error) { log.warn("Subtitle dispatch deferred ({})", error.getClass().getSimpleName()); }
    }
    @Scheduled(fixedDelayString = "${subtitles.dispatch-interval-ms:1000}")
    public void drainQueued() {
        store.failUnavailableSources();
        for (var key : store.due(32, attempts())) {
            if (!key.targetLanguage().equals(correctionTarget(key.id(), key.targetLanguage()))) {
                store.discardDuplicatePending(key.id(), key.targetLanguage());
                continue;
            }
            if (!dispatched.add(key)) continue;
            try { worker.execute(() -> { try { process(key); } finally { dispatched.remove(key); } }); }
            catch (RejectedExecutionException full) { dispatched.remove(key); }
        }
    }
    @EventListener(ApplicationReadyEvent.class)
    public void recoverInterruptedJobs() {
        int recovered = store.recoverInterrupted(attempts());
        store.failUnavailableSources();
        if (recovered > 0) log.info("Recovered {} subtitle jobs", recovered);
        // Sources captured before a crash stay durable and are independently dispatched.
        dispatchSafely();
    }
    private int attempts() { return Math.max(1, Math.min(maxAttempts, 5)); }
    private void process(SubtitleJobStore.Key key) {
        SubtitleJobStore.Run run;
        try { var claim = store.claim(key.id(), key.targetLanguage(), attempts()); if (claim.isEmpty()) return; run = claim.get(); }
        catch (RuntimeException error) { log.warn("Subtitle claim deferred for {} ({})", key.id(), error.getClass().getSimpleName()); return; }
        try {
            var source = run.source();
            var result = analyzer.generateSubtitles(source.language(), source.segments(), source.pageGroups() == null ? List.of() : source.pageGroups(), run.targetLanguage());
            SubtitleResultValidator.validate(source, run.targetLanguage(), result);
            var status = (String)result.get("status");
            store.finish(run, "failed".equals(status) ? null : result, status, "failed".equals(status) ? "subtitle_failed" : null);
        } catch (Exception error) {
            try {
                if (transientFailure(error) && run.attempt() < attempts() && !Thread.currentThread().isInterrupted())
                    store.retry(run, Instant.now().plusSeconds(Math.min(30, run.attempt() * 2L)));
                else store.finish(run, null, "failed", error instanceof IllegalArgumentException ? "invalid_subtitle_result" : "subtitle_failed");
            } catch (RuntimeException persistenceError) {
                // The processing row remains recoverable if the database is temporarily unavailable.
                log.warn("Subtitle status update deferred for {} ({})", key.id(), persistenceError.getClass().getSimpleName());
            }
            log.warn("Subtitle job {} failed ({})", key.id(), error.getClass().getSimpleName());
        }
    }
    private static boolean transientFailure(Exception error) {
        if (error instanceof ResourceAccessException) return true;
        if (error instanceof RestClientResponseException response) {
            int status = response.getStatusCode().value(); return status == 408 || status == 429 || status >= 500;
        }
        return false;
    }
    @PreDestroy public void close() { worker.shutdownNow(); }
}
