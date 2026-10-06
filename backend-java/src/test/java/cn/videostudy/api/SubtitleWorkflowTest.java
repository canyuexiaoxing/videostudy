package cn.videostudy.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.core.io.ClassPathResource;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.client.ResourceAccessException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class SubtitleWorkflowTest {
    String id;
    JdbcTemplate jdbc;
    TranscriptionJobStore main;
    SubtitleJobStore store;
    SubtitleService service;
    final ObjectMapper json = new ObjectMapper();
    final List<TranscriptionController.TranscriptSegment> segments = List.of(
        new TranscriptionController.TranscriptSegment("t_1", 1000, 2200, "增加量等于现期减基期"));
    final List<TranscriptionController.PageGroup> pages = List.of(new TranscriptionController.PageGroup(
        0, 0, 2500, List.of(1000L), List.of(1000L), "same", "same page",
        List.of(new TranscriptionController.OcrLine("增长量等于现期减基期", 1000, 0)), null));

    @BeforeEach void setup() {
        var ds = new DriverManagerDataSource("jdbc:h2:mem:" + UUID.randomUUID() + ";MODE=MySQL;DB_CLOSE_DELAY=-1", "sa", "");
        new ResourceDatabasePopulator(new ClassPathResource("db/migration/V1__create_transcription_jobs.sql"),
            new ClassPathResource("db/migration/V3__visual_analysis_mode.sql"),
            new ClassPathResource("db/migration/V4__coarse_change_percent.sql"),
            new ClassPathResource("db/migration/V5__subtitle_jobs.sql")).execute(ds);
        jdbc = new JdbcTemplate(ds); main = new TranscriptionJobStore(jdbc, json); store = new SubtitleJobStore(jdbc, json);
        id = UUID.randomUUID().toString(); main.createQueued(id); main.markProcessing(id);
    }
    @AfterEach void cleanup() { if (service != null) service.close(); }

    @Test void savedFinalPagesRefreshAnOlderSubtitleSourceSnapshot() {
        store.createUploadRequest(id, "source");
        store.captureSource(id, store.callbackToken(id), source());
        var p = pages.getFirst();
        var understood = new TranscriptionController.PageGroup(p.pageIndex(), p.firstFrameTimeMs(), p.lastFrameTimeMs(),
            p.memberFrameTimesMs(), p.representativeFrameTimesMs(), p.decision(), p.decisionReason(), p.ocrLines(),
            new TranscriptionController.ImageAnalysis("completed", "公式", "基期乘以增长率", List.of(), List.of()));
        store.captureFallback(id, new SubtitleJobStore.Source("zh", segments, List.of(understood)));
        assertEquals("基期乘以增长率", store.claim(id, "source", 3).orElseThrow().source()
            .pageGroups().getFirst().imageAnalysis().content());
    }

    @Test void explicitRegenerationResetsCurrentCacheButDoesNotDuplicateRunningJob() {
        store.createUploadRequest(id, "source");
        store.captureSource(id, store.callbackToken(id), source());
        var current = result("completed");
        current.put("promptVersion", SubtitleResultValidator.PROMPT_VERSION);
        store.finish(store.claim(id, "source", 3).orElseThrow(), current, "completed", null);
        assertEquals("completed", store.request(id, "source", true).status());
        assertEquals("queued", store.request(id, "source", true, true).status());
        assertNull(store.find(id, "source").orElseThrow().result());
        var run = store.claim(id, "source", 3).orElseThrow();
        assertEquals("processing", store.request(id, "source", true, true).status());
        assertTrue(store.finish(run, current, "completed", null));
    }

    @Test void sampledSlideAfterSpeechCanProvideRealContextEvidence() {
        var later = new TranscriptionController.PageGroup(0, 28000, 108000, List.of(28000L), List.of(28000L),
            "same", "sampled later", List.of(new TranscriptionController.OcrLine("增长量等于现期减基期", 28000, 0)), null);
        var corrected = result("completed");
        corrected.put("changes", List.of(Map.of("segmentId", "t_1", "originalText", segments.getFirst().text(),
            "text", "增长量等于现期减基期", "reason", "附近公式支持短语校正", "evidence",
            List.of(Map.of("sourceFrameTimeMs", 28000, "text", "增长量等于现期减基期")))));
        assertDoesNotThrow(() -> SubtitleResultValidator.validate(new SubtitleJobStore.Source("zh", segments, List.of(later)), "source", corrected));
        // The preceding page is closer, but this speech may introduce the next.
        var prior = new TranscriptionController.PageGroup(0, 0, 500, List.of(0L), List.of(0L),
            "same", "previous", List.of(new TranscriptionController.OcrLine("旧题", 0, 0)), null);
        assertDoesNotThrow(() -> SubtitleResultValidator.validate(new SubtitleJobStore.Source("zh", segments, List.of(prior, later)), "source", corrected));
    }

    @Test void oldSubtitleCacheIsUpdatedOnlyOnExplicitRequest() {
        store.createUploadRequest(id, "source"); store.captureSource(id, store.callbackToken(id), source());
        var old = result("completed"); old.put("promptVersion", "subtitle-calibration-v3");
        store.finish(store.claim(id, "source", 3).orElseThrow(), old, "completed", null);
        assertEquals("completed", store.find(id, "source").orElseThrow().status());
        assertEquals("queued", store.request(id, "source", true).status());
        var current = result("completed"); current.put("promptVersion", SubtitleResultValidator.PROMPT_VERSION);
        store.finish(store.claim(id, "source", 3).orElseThrow(), current, "completed", null);
        assertEquals("completed", store.request(id, "source", true).status());
    }

    @Test void sameLanguageAndSourceShareOneCorrectionRequest() throws Exception {
        store.createUploadRequest(id, "source");
        store.captureSource(id, store.callbackToken(id), source());
        var calls = new AtomicInteger();
        service = new SubtitleService(store, main, analyzer(() -> { calls.incrementAndGet(); return result("completed"); }));
        service.request(id, "zh");
        awaitStatus("completed");
        assertEquals(service.get(id, "source"), service.get(id, "zh"));
        service.request(id, "zh");
        assertEquals(1, calls.get());
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM subtitle_jobs WHERE transcription_id = ?", Integer.class, id));
    }

    @Test void existingExplicitLanguageCorrectionIsReusedForSourceSelection() {
        store.createUploadRequest(id, "zh");
        store.captureSource(id, store.callbackToken(id), source());
        var run = store.claim(id, "zh", 3).orElseThrow();
        store.finish(run, result("completed"), "completed", null);
        service = new SubtitleService(store, main, analyzer(() -> { fail("must reuse existing correction"); return null; }));
        assertEquals(service.get(id, "zh"), service.get(id, "source"));
        service.request(id, "source");
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM subtitle_jobs WHERE transcription_id = ?", Integer.class, id));
    }

    @Test void legacyDuplicateResultsAlwaysChooseSameSourceCorrection() {
        store.createUploadRequest(id, "source"); store.createUploadRequest(id, "zh");
        store.captureSource(id, store.callbackToken(id), source());
        var original = result("completed");
        store.finish(store.claim(id, "source", 3).orElseThrow(), original, "completed", null);
        var other = result("completed"); other.put("concerns", List.of("different legacy result"));
        store.finish(store.claim(id, "zh", 3).orElseThrow(), other, "completed", null);
        service = new SubtitleService(store, main, analyzer(() -> { fail("must not regenerate"); return null; }));
        assertEquals(service.get(id, "source"), service.get(id, "zh"));
        assertEquals(List.of(), service.get(id, "zh").result().get("concerns"));
        assertEquals("not_requested", service.get(id, "en").status());
    }

    @Test void duplicateQueuedCorrectionsBeforeLanguageDetectionRunOnlyOnce() throws Exception {
        store.createUploadRequest(id, "source"); store.createUploadRequest(id, "zh");
        store.captureSource(id, store.callbackToken(id), source());
        var calls = new AtomicInteger();
        service = new SubtitleService(store, main, analyzer(() -> { calls.incrementAndGet(); return result("completed"); }));
        service.drainQueued(); awaitStatus("completed");
        assertEquals(1, calls.get());
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM subtitle_jobs WHERE transcription_id = ?", Integer.class, id));
        assertEquals(service.get(id, "source"), service.get(id, "zh"));
    }

    @Test void englishSourceSharesEnglishCorrectionButNotChineseTranslation() {
        store.createUploadRequest(id, "source");
        store.captureSource(id, store.callbackToken(id), new SubtitleJobStore.Source("en-US", segments, pages));
        service = new SubtitleService(store, main, analyzer(() -> result("completed")));
        assertEquals(service.get(id, "source"), service.get(id, "en"));
        assertEquals("queued", service.get(id, "en").status());
        assertEquals("not_requested", service.get(id, "zh").status());
    }
    SubtitleJobStore.Source source() { return new SubtitleJobStore.Source("zh", segments, pages); }
    Map<String,Object> result(String status) {
        return new LinkedHashMap<>(Map.of("status", status, "sourceLanguage", "zh", "targetLanguage", "zh",
            "mode", "correction", "segments", List.of(Map.of("id", "t_1", "startMs", 1000, "endMs", 2200, "text", "增长量等于现期减基期")),
            "changes", List.of(Map.of("segmentId", "t_1", "originalText", "增加量等于现期减基期", "text", "增长量等于现期减基期", "reason", "OCR terminology",
                "evidence", List.of(Map.of("sourceFrameTimeMs", 1000, "text", "增长量等于现期减基期")))),
            "rejectedCount", 0, "concerns", List.of(), "usage", Map.of("tokens", 4)));
    }
    MediaAnalyzer analyzer(java.util.function.Supplier<Map<String,Object>> response) {
        return new MediaAnalyzer() {
            public TranscriptionController.TranscriptResult analyze(String id, String mode) { throw new AssertionError(); }
            public Map<String,Object> generateSubtitles(String language, List<TranscriptionController.TranscriptSegment> segments,
                                                       List<TranscriptionController.PageGroup> pages, String target) { return response.get(); }
        };
    }
    void awaitStatus(String status) throws Exception {
        for (int i = 0; i < 200; i++) {
            if (store.find(id, "source").orElseThrow().status().equals(status)) return;
            Thread.sleep(10);
        }
        assertEquals(status, store.find(id, "source").orElseThrow().status());
    }

    @Test void authenticatedSourceStartsSubtitleBeforeMainAnalysisCompletes() throws Exception {
        store.createUploadRequest(id, "source");
        var entered = new CountDownLatch(1); var release = new CountDownLatch(1);
        service = new SubtitleService(store, main, analyzer(() -> {
            entered.countDown(); try { release.await(3, TimeUnit.SECONDS); } catch (InterruptedException e) { throw new RuntimeException(e); }
            return result("completed");
        }));
        var mvc = MockMvcBuilders.standaloneSetup(new SubtitleSourceController(service))
            .addFilters(new org.springframework.web.filter.CorsFilter(new org.springframework.web.cors.UrlBasedCorsConfigurationSource())).build();
        mvc.perform(post("/api/internal/transcriptions/{id}/subtitle-source", id).header("X-Subtitle-Token", store.callbackToken(id))
                .contentType("application/json").content(json.writeValueAsString(source())))
            .andExpect(status().isAccepted());
        assertTrue(entered.await(2, TimeUnit.SECONDS));
        assertEquals("processing", main.find(id).orElseThrow().status());
        assertEquals("processing", store.find(id, "source").orElseThrow().status());
        release.countDown(); awaitStatus("completed");
        assertEquals(Map.of("tokens", 4), store.find(id, "source").orElseThrow().result().get("usage"));
    }

    @Test void callbackRejectsWrongTokenUnknownDeletedAndCrossOriginRequests() throws Exception {
        store.createUploadRequest(id, "source"); var token = store.callbackToken(id);
        service = new SubtitleService(store, main, analyzer(() -> result("completed")));
        var mvc = MockMvcBuilders.standaloneSetup(new SubtitleSourceController(service))
            .addFilters(new org.springframework.web.filter.CorsFilter(new org.springframework.web.cors.UrlBasedCorsConfigurationSource())).build();
        mvc.perform(post("/api/internal/transcriptions/{id}/subtitle-source", id).header("X-Subtitle-Token", "bad")
            .contentType("application/json").content(json.writeValueAsString(source()))).andExpect(status().isForbidden());
        mvc.perform(options("/api/internal/transcriptions/{id}/subtitle-source", id).header("Origin", "http://localhost:5173")
            .header("Access-Control-Request-Method", "POST").header("Access-Control-Request-Headers", "X-Subtitle-Token"))
            .andExpect(status().isForbidden());
        main.delete(id);
        mvc.perform(post("/api/internal/transcriptions/{id}/subtitle-source", id).header("X-Subtitle-Token", token)
            .contentType("application/json").content(json.writeValueAsString(source()))).andExpect(status().isForbidden());
        assertTrue(store.find(id, "source").isEmpty());
    }

    @Test void existingCourseRequestsAreIdempotentAndExposeAllStatuses() throws Exception {
        main.complete(id, new TranscriptionController.TranscriptResult("zh", segments, List.of(), null, null, null, pages, List.of(), "both", "v1"));
        var calls = new AtomicInteger();
        service = new SubtitleService(store, main, analyzer(() -> { calls.incrementAndGet(); return result("partial"); }));
        var mvc = MockMvcBuilders.standaloneSetup(new SubtitleController(service, main)).build();
        mvc.perform(get("/api/transcriptions/{id}/subtitles", id)).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("not_requested"));
        mvc.perform(post("/api/transcriptions/{id}/subtitles", id).contentType("application/json").content("{\"targetLanguage\":\"source\"}"))
            .andExpect(status().is2xxSuccessful()); // A fast worker may finish before the HTTP response.
        awaitStatus("partial");
        mvc.perform(post("/api/transcriptions/{id}/subtitles", id).contentType("application/json").content("{\"targetLanguage\":\"source\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("partial"));
        mvc.perform(get("/api/transcriptions/{id}/subtitles?targetLanguage=en", id)).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("not_requested"));
        mvc.perform(get("/api/transcriptions/{id}/subtitles?targetLanguage=fr", id)).andExpect(status().isBadRequest());
        assertEquals(1, calls.get());
    }

    @Test void deletionDuringWorkerCannotResurrectResult() throws Exception {
        store.createUploadRequest(id, "source"); store.captureSource(id, store.callbackToken(id), source());
        var entered = new CountDownLatch(1); var release = new CountDownLatch(1);
        service = new SubtitleService(store, main, analyzer(() -> {
            entered.countDown(); try { release.await(3, TimeUnit.SECONDS); } catch (InterruptedException e) { throw new RuntimeException(e); }
            return result("completed");
        }));
        service.drainQueued(); assertTrue(entered.await(2, TimeUnit.SECONDS)); main.delete(id); release.countDown();
        Thread.sleep(100);
        assertTrue(store.find(id, "source").isEmpty()); assertTrue(store.source(id).isEmpty());
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM subtitle_jobs", Integer.class));
    }

    @Test void restartInvalidatesOldRunAndDuplicateSourceDoesNotReplaceEvidence() {
        store.createUploadRequest(id, "source"); var token = store.callbackToken(id);
        assertTrue(store.captureSource(id, token, source()));
        var run = store.claim(id, "source", 3).orElseThrow();
        store.recoverInterrupted(3);
        assertFalse(store.finish(run, result("completed"), "completed", null));
        assertTrue(store.captureSource(id, token, new SubtitleJobStore.Source("en", segments, List.of())));
        assertEquals("zh", store.source(id).orElseThrow().language());
        assertEquals("queued", store.find(id, "source").orElseThrow().status());
        assertTrue(store.claim(id, "source", 3).isPresent()); assertTrue(store.claim(id, "source", 3).isEmpty());
    }

    @Test void transientFailuresRetryBoundedlyWithoutFailingAnalysis() throws Exception {
        store.createUploadRequest(id, "source"); store.captureSource(id, store.callbackToken(id), source());
        var calls = new AtomicInteger();
        service = new SubtitleService(store, main, analyzer(() -> { calls.incrementAndGet(); throw new ResourceAccessException("offline"); }));
        service.drainQueued(); awaitStatus("queued");
        for (int i = 0; i < 3; i++) {
            jdbc.update("UPDATE subtitle_jobs SET next_attempt_at = CURRENT_TIMESTAMP WHERE transcription_id = ?", id);
            service.drainQueued(); Thread.sleep(70);
        }
        awaitStatus("failed"); assertEquals(3, calls.get()); assertEquals("processing", main.find(id).orElseThrow().status());
    }

    @Test void malformedSegmentsAndUnguardedCorrectionAreFailedWithoutPublishing() throws Exception {
        store.createUploadRequest(id, "source"); store.captureSource(id, store.callbackToken(id), source());
        var bad = result("completed"); bad.put("segments", List.of(Map.of("id", "t_1", "startMs", 0, "endMs", 2200, "text", "增长量等于现期减基期")));
        service = new SubtitleService(store, main, analyzer(() -> bad)); service.drainQueued(); awaitStatus("failed");
        assertNull(store.find(id, "source").orElseThrow().result()); assertEquals("processing", main.find(id).orElseThrow().status());
        var ungrounded = result("completed"); ungrounded.put("changes", List.of());
        assertThrows(IllegalArgumentException.class, () -> SubtitleResultValidator.validate(source(), "source", ungrounded));
    }
}
