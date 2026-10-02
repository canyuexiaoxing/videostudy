package cn.videostudy.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class PageGroupResultTest {
    private final ObjectMapper json = new ObjectMapper();

    @Test
    void readsTextRoutePageAnalysisAndLegacyPageWithoutIt() throws Exception {
        var current = """
            {"language":"zh","segments":[],"visualEvidence":[],"ocrModelId":"PP-OCRv6_medium",
             "imageModelId":null,"review":null,"pageGroups":[{"pageIndex":1,
             "firstFrameTimeMs":1000,"lastFrameTimeMs":1000,"memberFrameTimesMs":[1000],
             "representativeFrameTimesMs":[1000],"decision":"first_page",
             "decisionReason":"first","ocrLines":[],"imageAnalysis":null,
             "textAnalysis":{"status":"completed","title":"增长量","content":"讲解和OCR文字",
             "visualElements":[],"uncertainties":[]}}],"transitionFrameTimesMs":[],
             "visualAnalysisMode":"ocr_only","groupingVersion":"page-group-v1"}
            """;
        var result = json.readValue(current, TranscriptionController.TranscriptResult.class);
        assertEquals("增长量", result.pageGroups().get(0).textAnalysis().title());
        var legacy = json.readTree(current);
        ((com.fasterxml.jackson.databind.node.ObjectNode) legacy.get("pageGroups").get(0)).remove("textAnalysis");
        var oldResult = json.treeToValue(legacy, TranscriptionController.TranscriptResult.class);
        assertNull(oldResult.pageGroups().get(0).textAnalysis());
    }

    @Test
    void readsGroundedMindMapAndKeepsLegacyResultsReadable() throws Exception {
        var current = """
            {"language":"zh","segments":[],"visualEvidence":[],"mindMap":{
             "status":"completed","modelId":"deepseek-flash","promptVersion":"grounded-mind-map-v1",
             "root":{"id":"course","title":"课程知识导图","startMs":1000,"endMs":1900,
             "evidenceRefs":[],"children":[{"id":"chapter_0","title":"增长量","startMs":1000,
             "endMs":1900,"evidenceRefs":[],"children":[{"id":"concept_0_0",
             "title":"增长量公式","startMs":1000,"endMs":1900,"children":[],
             "evidenceRefs":[{"sourceType":"transcript","sourceId":"t_1","startMs":1000,
             "endMs":1900,"quote":"增长量等于现期减基期"}]}]}]}}}
            """;
        var parsed = json.readValue(current, TranscriptionController.TranscriptResult.class);
        assertEquals(1000, parsed.mindMap().root().children().get(0).children().get(0).startMs());
        assertEquals("t_1", parsed.mindMap().root().children().get(0).children().get(0)
            .evidenceRefs().get(0).sourceId());
        var legacy = (com.fasterxml.jackson.databind.node.ObjectNode) json.readTree(current);
        legacy.remove("mindMap");
        assertNull(json.treeToValue(legacy, TranscriptionController.TranscriptResult.class).mindMap());
    }
}
