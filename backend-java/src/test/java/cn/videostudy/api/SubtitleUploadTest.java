package cn.videostudy.api;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import java.nio.file.Path;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class SubtitleUploadTest {
    @TempDir Path directory;
    @Test void enabledUploadForwardsPrivateTokenAndCapturesSavedFallback() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        var subtitles = mock(SubtitleService.class);
        var agent = mock(MediaAnalyzer.class);
        var result = new TranscriptionController.TranscriptResult("zh", java.util.List.of(), java.util.List.of(), null, null, null);
        when(subtitles.callbackToken(anyString())).thenReturn("private-callback-token");
        when(agent.analyze(anyString(), eq("transcription"), eq("both"), eq(2.0), eq("private-callback-token"))).thenReturn(result);
        var controller = new TranscriptionController(directory.toString(), "transcription", store, agent);
        org.springframework.test.util.ReflectionTestUtils.setField(controller, "subtitles", subtitles);
        var chapters = mock(ChapterController.class);
        org.springframework.test.util.ReflectionTestUtils.setField(controller, "chapters", chapters);
        try {
            var job = (TranscriptionController.TranscriptionJob)controller.upload(new MockMultipartFile("file", "lesson.wav", "audio/wav", new byte[]{1}), "both", 2.0, true, "en").getBody();
            verify(subtitles).createUploadRequest(job.id(), "en");
            verify(subtitles, timeout(2000)).captureFallback(eq(job.id()), eq(result));
            verify(store).complete(job.id(), result);
            verify(chapters).request(job.id());
            verify(agent).analyze(job.id(), "transcription", "both", 2.0, "private-callback-token");
        } finally { controller.close(); }
    }

    @Test void disabledUploadDoesNotRequestOrForwardSubtitleToken() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        var subtitles = mock(SubtitleService.class);
        var agent = mock(MediaAnalyzer.class);
        var result = new TranscriptionController.TranscriptResult("en", java.util.List.of(), java.util.List.of(), null, null, null);
        when(agent.analyze(anyString(), eq("transcription"), eq("both"), eq(2.0))).thenReturn(result);
        var controller = new TranscriptionController(directory.toString(), "transcription", store, agent);
        org.springframework.test.util.ReflectionTestUtils.setField(controller, "subtitles", subtitles);
        try {
            var job = (TranscriptionController.TranscriptionJob)controller.upload(new MockMultipartFile("file", "lesson.wav", "audio/wav", new byte[]{1}), "both", 2.0, false, "source").getBody();
            verify(store, timeout(2000)).complete(job.id(), result);
            verify(subtitles, never()).createUploadRequest(anyString(), anyString());
            verify(agent, never()).analyze(anyString(), anyString(), anyString(), anyDouble(), anyString());
        } finally { controller.close(); }
    }
    @Test void invalidSubtitleTargetIsRejectedBeforeUploadIsSaved() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        var controller = new TranscriptionController(directory.toString(), "transcription", store,
            (id, mode) -> new TranscriptionController.TranscriptResult("zh", java.util.List.of(), java.util.List.of(), null, null, null));
        try {
            MockMvcBuilders.standaloneSetup(controller).build()
                .perform(multipart("/api/transcriptions").file(new MockMultipartFile("file", "lesson.wav", "audio/wav", new byte[]{1}))
                    .param("subtitleTargetLanguage", "fr"))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.error").value("invalid_subtitle_target_language"));
            verify(store, never()).createQueued(anyString(), anyString(), anyDouble());
        } finally { controller.close(); }
    }
}
