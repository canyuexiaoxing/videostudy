package cn.videostudy.api;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.List;
import java.util.Optional;

import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class MindMapControllerTest {
    private final String id = "51557229-d873-4a4a-b80e-5d4f21e2d1ae";

    private TranscriptionController.TranscriptResult legacyResult() {
        return new TranscriptionController.TranscriptResult("zh",
            List.of(new TranscriptionController.TranscriptSegment("t_1", 1000, 1900, "增长量等于现期减基期")),
            List.of(), null, null, null);
    }

    private TranscriptionController.MindMapResult map() {
        var source = new TranscriptionController.MindMapEvidence("transcript", "t_1", 1000, 1900,
            "增长量等于现期减基期");
        var concept = new TranscriptionController.MindMapNode("concept_0_0", "增长量公式", 1000, 1900,
            List.of(source), List.of());
        var node = new TranscriptionController.MindMapNode("course", "课程知识导图", 1000, 1900,
            List.of(source), List.of(concept));
        return new TranscriptionController.MindMapResult("completed", "deepseek-flash", "v1", node);
    }

    @Test
    void acceptsEvidenceGroundedTreeBeyondThreeLevels() {
        var result = legacyResult();
        var evidence = new TranscriptionController.MindMapEvidence("transcript", "t_1", 1000, 1900,
            "增长量等于现期减基期");
        var node = new TranscriptionController.MindMapNode("leaf", "公式", 1000, 1900,
            List.of(evidence), List.of());
        for (int depth = 0; depth < 6; depth++) {
            node = new TranscriptionController.MindMapNode("level_" + depth, "主题" + depth, 1000, 1900,
                List.of(evidence), List.of(node));
        }
        var deepMap = new TranscriptionController.MindMapResult("completed", "deepseek", "v2", node);
        org.junit.jupiter.api.Assertions.assertTrue(MindMapValidator.isGrounded(deepMap, result.segments()));
    }

    @Test
    void createsMapFromSavedTranscriptWithoutReuploadingVideo() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(
            id, "completed", legacyResult(), null)));
        var analyzer = mock(MediaAnalyzer.class);
        when(analyzer.generateMindMap(anyList(), anyList())).thenReturn(map());
        var mvc = MockMvcBuilders.standaloneSetup(new MindMapController(store, analyzer)).build();
        mvc.perform(post("/api/transcriptions/{id}/mind-map", id))
            .andExpect(status().isOk()).andExpect(jsonPath("$.root.startMs").value(1000));
        verify(analyzer).generateMindMap(eq(legacyResult().segments()), eq(List.of()));
        verify(store).saveMindMap(id, map());
    }

    @Test
    void completedMapIsReturnedWithoutSecondModelCall() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        var existing = legacyResult().withMindMap(map());
        when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(
            id, "completed", existing, null)));
        var analyzer = mock(MediaAnalyzer.class);
        MockMvcBuilders.standaloneSetup(new MindMapController(store, analyzer)).build()
            .perform(post("/api/transcriptions/{id}/mind-map", id))
            .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("completed"));
        verifyNoInteractions(analyzer);
    }

    @Test
    void explicitRefreshRebuildsCompletedMapFromSavedTranscript() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(
            id, "completed", legacyResult().withMindMap(map()), null)));
        var analyzer = mock(MediaAnalyzer.class);
        when(analyzer.generateMindMap(anyList(), anyList())).thenReturn(map());
        MockMvcBuilders.standaloneSetup(new MindMapController(store, analyzer)).build()
            .perform(post("/api/transcriptions/{id}/mind-map?refresh=true", id))
            .andExpect(status().isOk());
        verify(analyzer).generateMindMap(anyList(), anyList());
        verify(store).saveMindMap(id, map());
    }

    @Test
    void failedRefreshKeepsPreviouslyCompletedMap() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(
            id, "completed", legacyResult().withMindMap(map()), null)));
        var analyzer = mock(MediaAnalyzer.class);
        var failed = new TranscriptionController.MindMapResult("failed", "deepseek", "v2",
            new TranscriptionController.MindMapNode("course", "课程", 0, 0, List.of(), List.of()));
        when(analyzer.generateMindMap(anyList(), anyList())).thenReturn(failed);
        MockMvcBuilders.standaloneSetup(new MindMapController(store, analyzer)).build()
            .perform(post("/api/transcriptions/{id}/mind-map?refresh=true", id))
            .andExpect(status().isBadGateway());
        verify(store, never()).saveMindMap(anyString(), any());
    }

    @Test
    void incompleteOrMissingTaskCannotGenerateMap() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        var analyzer = mock(MediaAnalyzer.class);
        var mvc = MockMvcBuilders.standaloneSetup(new MindMapController(store, analyzer)).build();
        mvc.perform(post("/api/transcriptions/{id}/mind-map", id)).andExpect(status().isNotFound());
        when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(
            id, "processing", null, null)));
        mvc.perform(post("/api/transcriptions/{id}/mind-map", id)).andExpect(status().isConflict());
        verifyNoInteractions(analyzer);
    }

    @Test
    void inventedCitationIsRejectedBeforePersistence() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(
            id, "completed", legacyResult(), null)));
        var analyzer = mock(MediaAnalyzer.class);
        var fake = new TranscriptionController.MindMapEvidence("transcript", "invented", 1000, 1900,
            "增长量等于现期减基期");
        var root = new TranscriptionController.MindMapNode("course", "课程知识导图", 1000, 1900,
            List.of(fake), List.of());
        when(analyzer.generateMindMap(anyList(), anyList())).thenReturn(
            new TranscriptionController.MindMapResult("completed", "test", "v1", root));
        MockMvcBuilders.standaloneSetup(new MindMapController(store, analyzer)).build()
            .perform(post("/api/transcriptions/{id}/mind-map", id))
            .andExpect(status().isBadGateway())
            .andExpect(jsonPath("$.error").value("mind_map_generation_failed"));
        verify(store, never()).saveMindMap(anyString(), any());
    }
}
