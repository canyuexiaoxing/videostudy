package cn.videostudy.api;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import static org.mockito.Mockito.mock;

import java.nio.file.Path;
import java.nio.file.Files;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertFalse;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class TranscriptionControllerTest {
    @TempDir Path temporaryDirectory;

    @Test
    void transientFailureAutomaticallyResumesWithoutAnotherUpload() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        var calls = new java.util.concurrent.atomic.AtomicInteger();
        var controller = new TranscriptionController(temporaryDirectory.toString(), "full", store, (id, mode) -> {
            assertTrue(Files.exists(temporaryDirectory.resolve(id)));
            if (calls.incrementAndGet() == 1) throw new IllegalStateException("temporary failure");
            return new TranscriptionController.TranscriptResult("zh", List.of(), List.of(), null, null,
                new TranscriptionController.ReviewResult("completed", "test", "test", "v1", List.of(), List.of()));
        });
        try {
            var response = controller.upload(new MockMultipartFile("file", "lesson.wav", "audio/wav", new byte[]{1}));
            var id = ((TranscriptionController.TranscriptionJob)response.getBody()).id();
            org.mockito.Mockito.verify(store, org.mockito.Mockito.timeout(3000)).complete(org.mockito.ArgumentMatchers.eq(id), org.mockito.ArgumentMatchers.any());
            org.junit.jupiter.api.Assertions.assertEquals(2, calls.get());
            org.mockito.Mockito.verify(store, org.mockito.Mockito.never()).markFailed(org.mockito.ArgumentMatchers.anyString(), org.mockito.ArgumentMatchers.anyString());
        } finally { controller.close(); }
    }

    @Test
    void rejectsUnknownVisualModeBeforeSavingUpload() throws Exception {
        var controller = new TranscriptionController(temporaryDirectory.toString(), "full", mock(TranscriptionJobStore.class),
            (id, mode) -> { throw new IllegalStateException("unused"); });
        try {
            var mvc = MockMvcBuilders.standaloneSetup(controller).build();
            mvc.perform(multipart("/api/transcriptions")
                    .file(new MockMultipartFile("file", "lesson.mp4", "video/mp4", new byte[] {1}))
                    .param("visualAnalysisMode", "invalid"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_visual_analysis_mode"));
        } finally {
            controller.close();
        }
    }

    @Test
    void persistsSelectedVisualModeForRetry() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        var controller = new TranscriptionController(temporaryDirectory.toString(), "full", store,
            (id, mode) -> { throw new IllegalStateException("agent unavailable"); });
        try {
            var mvc = MockMvcBuilders.standaloneSetup(controller).build();
            mvc.perform(multipart("/api/transcriptions")
                    .file(new MockMultipartFile("file", "lesson.mp4", "video/mp4", new byte[] {1}))
                    .param("visualAnalysisMode", "ocr_only"))
                .andExpect(status().isAccepted());
            org.mockito.Mockito.verify(store, org.mockito.Mockito.timeout(3000))
                .createQueued(org.mockito.ArgumentMatchers.anyString(), org.mockito.ArgumentMatchers.eq("ocr_only"),
                    org.mockito.ArgumentMatchers.eq(2.0), org.mockito.ArgumentMatchers.eq(2));
        } finally {
            controller.close();
        }
    }

    @Test
    void rejectsUnsupportedCoarseThresholdBeforeSavingUpload() throws Exception {
        var controller = new TranscriptionController(temporaryDirectory.toString(), "full", mock(TranscriptionJobStore.class),
            (id, mode) -> { throw new IllegalStateException("unused"); });
        try {
            MockMvcBuilders.standaloneSetup(controller).build().perform(multipart("/api/transcriptions")
                    .file(new MockMultipartFile("file", "lesson.mp4", "video/mp4", new byte[] {1}))
                    .param("coarseChangePercent", "9"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_coarse_change_percent"));
        } finally {
            controller.close();
        }
    }

    @Test
    void selectedCoarseThresholdIsPersistedAndSentToAnalyzer() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        var actual = new java.util.concurrent.atomic.AtomicReference<Double>();
        MediaAnalyzer analyzer = new MediaAnalyzer() {
            public TranscriptionController.TranscriptResult analyze(String id, String mode) { throw new AssertionError(); }
            public TranscriptionController.TranscriptResult analyze(String id, String mode, String visualMode,
                                                                     double percent) {
                actual.set(percent);
                return new TranscriptionController.TranscriptResult("zh", List.of(), List.of(), null, null,
                    new TranscriptionController.ReviewResult("completed", "test", "test", "v1", List.of(), List.of()));
            }
        };
        var controller = new TranscriptionController(temporaryDirectory.toString(), "full", store, analyzer);
        try {
            MockMvcBuilders.standaloneSetup(controller).build().perform(multipart("/api/transcriptions")
                    .file(new MockMultipartFile("file", "lesson.mp4", "video/mp4", new byte[] {1}))
                    .param("coarseChangePercent", "3"))
                .andExpect(status().isAccepted());
            org.mockito.Mockito.verify(store, org.mockito.Mockito.timeout(3000))
                .createQueued(org.mockito.ArgumentMatchers.anyString(), org.mockito.ArgumentMatchers.eq("both"),
                    org.mockito.ArgumentMatchers.eq(3.0), org.mockito.ArgumentMatchers.eq(2));
            org.mockito.Mockito.verify(store, org.mockito.Mockito.timeout(3000))
                .complete(org.mockito.ArgumentMatchers.anyString(), org.mockito.ArgumentMatchers.any());
            org.junit.jupiter.api.Assertions.assertEquals(3.0, actual.get());
        } finally {
            controller.close();
        }
    }

    @Test
    void interruptedJobsBecomeRetryableAtStartup() {
        var store = mock(TranscriptionJobStore.class);
        var controller = new TranscriptionController(temporaryDirectory.toString(), "full", store,
            (id, mode) -> { throw new IllegalStateException("unused"); });
        try {
            controller.recoverInterruptedJobs();
            org.mockito.Mockito.verify(store).recoverInterruptedJobs();
        } finally {
            controller.close();
        }
    }

    @Test
    void rejectsEmptyUploadAndUnknownJob() throws Exception {
        var controller = new TranscriptionController(temporaryDirectory.toString(), "transcription", mock(TranscriptionJobStore.class),
            (id, mode) -> new TranscriptionController.TranscriptResult("zh", List.of(), List.of(), null, null, null));
        try {
            var mvc = MockMvcBuilders.standaloneSetup(controller).build();
            mvc.perform(multipart("/api/transcriptions")
                    .file(new MockMultipartFile("file", "empty.wav", "audio/wav", new byte[0])))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("empty_file"));
            mvc.perform(get("/api/transcriptions/unknown"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("job_not_found"));
        } finally {
            controller.close();
        }
    }

    @Test
    void failedAnalysisKeepsUploadForRetry() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        var controller = new TranscriptionController(temporaryDirectory.toString(), "full", store,
            (id, mode) -> { throw new IllegalStateException("agent unavailable"); });
        try {
            var response = controller.upload(new MockMultipartFile("file", "lesson.wav", "audio/wav", new byte[] {1, 2, 3}));
            var job = (TranscriptionController.TranscriptionJob) response.getBody();
            assertTrue(job != null);
            org.mockito.Mockito.verify(store, org.mockito.Mockito.timeout(3000)).markFailed(job.id(), "analysis_failed");
            assertTrue(Files.exists(temporaryDirectory.resolve(job.id())));
        } finally {
            controller.close();
        }
    }

    @Test
    void fullAnalysisWithoutCompletedReviewKeepsUpload() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        var controller = new TranscriptionController(temporaryDirectory.toString(), "full", store,
            (id, mode) -> new TranscriptionController.TranscriptResult("zh", List.of(), List.of(), null, null, null));
        try {
            var response = controller.upload(new MockMultipartFile("file", "lesson.wav", "audio/wav", new byte[] {1, 2, 3}));
            var job = (TranscriptionController.TranscriptionJob) response.getBody();
            assertTrue(job != null);
            org.mockito.Mockito.verify(store, org.mockito.Mockito.timeout(3000)).markFailed(job.id(), "analysis_failed");
            assertTrue(Files.exists(temporaryDirectory.resolve(job.id())));
        } finally {
            controller.close();
        }
    }

    @Test
    void completedFullReviewIsSavedBeforeUploadedMediaIsRemoved() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        var review = new TranscriptionController.ReviewResult("completed", "deepseek", "test", "v1", List.of(), List.of());
        var controller = new TranscriptionController(temporaryDirectory.toString(), "full", store,
            (id, mode) -> new TranscriptionController.TranscriptResult("zh", List.of(), List.of(), "PP-OCRv6_medium", null, review));
        try {
            var response = controller.upload(new MockMultipartFile("file", "lesson.wav", "audio/wav", new byte[] {1, 2, 3}));
            var job = (TranscriptionController.TranscriptionJob) response.getBody();
            assertTrue(job != null);
            org.mockito.Mockito.verify(store, org.mockito.Mockito.timeout(3000)).complete(org.mockito.ArgumentMatchers.eq(job.id()),
                org.mockito.ArgumentMatchers.any());
            for (int attempt = 0; attempt < 100 && Files.exists(temporaryDirectory.resolve(job.id())); attempt++) {
                Thread.sleep(10);
            }
            assertFalse(Files.exists(temporaryDirectory.resolve(job.id())));
        } finally {
            controller.close();
        }
    }

    @Test
    void failedJobCanRetryUsingRetainedUpload() throws Exception {
        var id = UUID.randomUUID().toString();
        Files.write(temporaryDirectory.resolve(id), new byte[] {1, 2, 3});
        var store = mock(TranscriptionJobStore.class);
        org.mockito.Mockito.when(store.find(id)).thenReturn(Optional.of(
            new TranscriptionController.TranscriptionJob(id, "failed", null, "analysis_failed")));
        org.mockito.Mockito.when(store.markQueuedIfFailed(id)).thenReturn(true);
        var review = new TranscriptionController.ReviewResult("completed", "deepseek", "test", "v1", List.of(), List.of());
        var controller = new TranscriptionController(temporaryDirectory.toString(), "full", store,
            (fileId, mode) -> new TranscriptionController.TranscriptResult("zh", List.of(), List.of(), "PP-OCRv6_medium", null, review));
        try {
            var mvc = MockMvcBuilders.standaloneSetup(controller).build();
            mvc.perform(post("/api/transcriptions/{id}/retry", id))
                .andExpect(status().isAccepted());
            org.mockito.Mockito.verify(store, org.mockito.Mockito.timeout(3000)).complete(org.mockito.ArgumentMatchers.eq(id),
                org.mockito.ArgumentMatchers.any());
        } finally {
            controller.close();
        }
    }

    @Test
    void retryUsesPersistedVisualMode() throws Exception {
        var id = UUID.randomUUID().toString();
        Files.write(temporaryDirectory.resolve(id), new byte[] {1});
        var store = mock(TranscriptionJobStore.class);
        org.mockito.Mockito.when(store.find(id)).thenReturn(Optional.of(
            new TranscriptionController.TranscriptionJob(id, "failed", null, "analysis_failed")));
        org.mockito.Mockito.when(store.markQueuedIfFailed(id)).thenReturn(true);
        org.mockito.Mockito.when(store.findVisualAnalysisMode(id)).thenReturn("ocr_only");
        org.mockito.Mockito.when(store.findCoarseChangePercent(id)).thenReturn(3.0);
        var actualMode = new java.util.concurrent.atomic.AtomicReference<String>();
        var actualPercent = new java.util.concurrent.atomic.AtomicReference<Double>();
        MediaAnalyzer analyzer = new MediaAnalyzer() {
            public TranscriptionController.TranscriptResult analyze(String fileId, String mode) {
                throw new AssertionError("three-argument analysis required");
            }
            public TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualMode,
                                                                     double coarsePercent) {
                actualMode.set(visualMode);
                actualPercent.set(coarsePercent);
                return new TranscriptionController.TranscriptResult("zh", List.of(), List.of(), null, null,
                    new TranscriptionController.ReviewResult("completed", "test", "test", "v1", List.of(), List.of()));
            }
        };
        var controller = new TranscriptionController(temporaryDirectory.toString(), "full", store, analyzer);
        try {
            MockMvcBuilders.standaloneSetup(controller).build().perform(post("/api/transcriptions/{id}/retry", id))
                .andExpect(status().isAccepted());
            org.mockito.Mockito.verify(store, org.mockito.Mockito.timeout(3000)).complete(org.mockito.ArgumentMatchers.eq(id),
                org.mockito.ArgumentMatchers.any());
            org.junit.jupiter.api.Assertions.assertEquals("ocr_only", actualMode.get());
            org.junit.jupiter.api.Assertions.assertEquals(3.0, actualPercent.get());
        } finally {
            controller.close();
        }
    }

    @Test
    void expiredFailedUploadIsRemoved() throws Exception {
        var id = UUID.randomUUID().toString();
        var path = temporaryDirectory.resolve(id);
        Files.write(path, new byte[] {1, 2, 3});
        var store = mock(TranscriptionJobStore.class);
        org.mockito.Mockito.when(store.findOldFailedIds(org.mockito.ArgumentMatchers.any(Instant.class))).thenReturn(List.of(id));
        var controller = new TranscriptionController(temporaryDirectory.toString(), "full", store,
            (fileId, mode) -> { throw new IllegalStateException("unused"); });
        var frames = Files.createDirectories(temporaryDirectory.resolve("frames"));
        var checkpoint = Files.createDirectories(frames.resolve(id).resolve(".analysis")).resolve("speech.json");
        Files.writeString(checkpoint, "{}");
        var neighbor = Files.writeString(Files.createDirectories(frames.resolve(UUID.randomUUID().toString())).resolve("keep.jpg"), "keep");
        org.springframework.test.util.ReflectionTestUtils.setField(controller, "keyframeDirectory", frames.toString());
        try {
            controller.cleanupStaleUploads();
            org.mockito.Mockito.verify(store).markExpired(id);
            assertFalse(Files.exists(path));
            assertFalse(Files.exists(checkpoint));
            assertTrue(Files.exists(neighbor));
        } finally {
            controller.close();
        }
    }
}
