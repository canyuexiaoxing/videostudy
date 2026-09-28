package cn.videostudy.api;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class KeyframeControllerTest {
    @TempDir Path temporaryDirectory;

    @Test
    void servesOnlyImagesListedInCompletedResults() throws Exception {
        var id = UUID.randomUUID().toString();
        Files.createDirectories(temporaryDirectory.resolve(id));
        Files.write(temporaryDirectory.resolve(id).resolve("28000.jpg"), new byte[] {1, 2, 3});
        var store = mock(TranscriptionJobStore.class);
        var analysis = new TranscriptionController.ImageAnalysis("completed", "Title", "Content", List.of(), List.of());
        var frame = new TranscriptionController.VisualEvidence(28000, List.of(), analysis);
        var result = new TranscriptionController.TranscriptResult("zh", List.of(), List.of(frame),
            "PP-OCRv6_medium", "deepseek-flash", null);
        when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id, "completed", result, null)));
        var mvc = MockMvcBuilders.standaloneSetup(new KeyframeController(temporaryDirectory.toString(), store)).build();

        mvc.perform(get("/api/transcriptions/{id}/frames/28000", id))
            .andExpect(status().isOk()).andExpect(content().bytes(new byte[] {1, 2, 3}));
        mvc.perform(get("/api/transcriptions/{id}/frames/56000", id)).andExpect(status().isNotFound());
        mvc.perform(get("/api/transcriptions/{id}/frames/28000", "../etc")).andExpect(status().isNotFound());

        var oldFrame = new TranscriptionController.VisualEvidence(28000, List.of(), null);
        var oldResult = new TranscriptionController.TranscriptResult("zh", List.of(), List.of(oldFrame),
            "PP-OCRv6_medium", null, null);
        when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id, "completed", oldResult, null)));
        mvc.perform(get("/api/transcriptions/{id}/frames/28000", id)).andExpect(status().isNotFound());

        var page = new TranscriptionController.PageGroup(1, 28000, 56000, List.of(28000L, 56000L),
            List.of(56000L), "auto_same_page", "continued", List.of(), null);
        var grouped = new TranscriptionController.TranscriptResult("zh", List.of(), List.of(oldFrame),
            "PP-OCRv6_medium", null, null, List.of(page), List.of(), "ocr_only", "page-group-v1");
        when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id, "completed", grouped, null)));
        mvc.perform(get("/api/transcriptions/{id}/frames/28000", id)).andExpect(status().isOk());
        mvc.perform(get("/api/transcriptions/{id}/frames/56000", id)).andExpect(status().isNotFound());
    }
}
