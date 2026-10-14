package cn.videostudy.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;
import java.util.List;
import java.util.LinkedHashMap;
import org.springframework.core.ParameterizedTypeReference;

@Component
public class HttpMediaAnalyzer implements MediaAnalyzer {
    private final RestClient agent;

    @org.springframework.beans.factory.annotation.Autowired
    public HttpMediaAnalyzer(@Value("${agent.base-url}") String agentBaseUrl) {
        var requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(3000);
        requestFactory.setReadTimeout(30 * 60 * 1000);
        agent = RestClient.builder().baseUrl(agentBaseUrl).requestFactory(requestFactory).build();
    }

    HttpMediaAnalyzer(RestClient agent) { this.agent = agent; }

    @Override public Map<String,Object> chatQuestion(Map<String,Object> source) {
        return agent.post().uri("/question-chat").body(source).retrieve()
            .body(new ParameterizedTypeReference<Map<String,Object>>() {});
    }
    @Override public Map<String,Object> generatePractice(Map<String,Object> source) {
        return agent.post().uri("/practice").body(source).retrieve()
            .body(new ParameterizedTypeReference<Map<String,Object>>() {});
    }

    @Override public Map<String,Object> generateChapters(List<TranscriptionController.TranscriptSegment> segments,
        List<TranscriptionController.PageGroup> pages) {
        return agent.post().uri("/chapters").body(Map.of("segments", segments, "pageGroups", pages))
            .retrieve().body(new ParameterizedTypeReference<Map<String,Object>>() {});
    }

    @Override public Map<String,Object> generateOverview(List<TranscriptionController.TranscriptSegment> segments,
        List<TranscriptionController.PageGroup> pages) {
        return agent.post().uri("/overview").body(Map.of("segments",segments,"pageGroups",pages))
            .retrieve().body(new ParameterizedTypeReference<Map<String,Object>>() {});
    }

    @Override public Map<String,Object> generateOverview(TranscriptionController.TranscriptResult source) { return generateOverview(null,source); }
    @Override public Map<String,Object> generateOverview(String courseId,TranscriptionController.TranscriptResult source) {
        var body=new LinkedHashMap<String,Object>();body.put("segments",source.segments());body.put("courseId",courseId);
        body.put("pageGroups",source.pageGroups()==null?List.of():source.pageGroups());body.put("mindMap",source.mindMap());
        body.put("visualEvidence",source.visualEvidence()==null?List.of():source.visualEvidence());
        return agent.post().uri("/overview").body(body).retrieve().body(new ParameterizedTypeReference<Map<String,Object>>() {});
    }

    @Override
    public TranscriptionController.TranscriptResult analyze(String fileId, String mode) {
        return analyze(fileId, mode, "both");
    }

    @Override
    public TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode) {
        return analyze(fileId, mode, visualAnalysisMode, 2.0);
    }

    @Override
    public TranscriptionController.TranscriptResult analyze(String fileId, String mode,
                                                             String visualAnalysisMode, double coarseChangePercent) {
        return analyze(fileId, mode, visualAnalysisMode, coarseChangePercent, null);
    }

    @Override public TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode,
                                                                     double coarseChangePercent, String subtitleCallbackToken) {
        return analyze(fileId, mode, visualAnalysisMode, coarseChangePercent, 2, subtitleCallbackToken);
    }

    @Override public TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode,
            double coarseChangePercent, int coarseSampleSeconds, String subtitleCallbackToken) {
        return analyze(fileId, mode, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds, subtitleCallbackToken, null);
    }

    @Override public TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode,
            double coarseChangePercent, int coarseSampleSeconds, String subtitleCallbackToken, IgnoreRegion region) {
        return analyze(fileId, mode, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds, subtitleCallbackToken, region, false);
    }
    @Override public TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode,
            double coarseChangePercent, int coarseSampleSeconds, String subtitleCallbackToken, IgnoreRegion region, boolean groupedAnalysis) {
        return analyze(fileId, mode, visualAnalysisMode, coarseChangePercent, coarseSampleSeconds, subtitleCallbackToken, region, groupedAnalysis, null);
    }
    @Override public TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode,
            double coarseChangePercent, int coarseSampleSeconds, String subtitleCallbackToken, IgnoreRegion region, boolean groupedAnalysis, String mindMapMode) {
        if (mindMapMode != null) groupedAnalysis="grouped".equals(mindMapMode);
        var endpoint = "full".equals(mode) ? "/analyze" : "/transcribe";
        var body = new LinkedHashMap<String,Object>();
        body.put("fileId", fileId); body.put("visualAnalysisMode", visualAnalysisMode);
        body.put("coarseChangePercent", coarseChangePercent);
        body.put("coarseSampleSeconds", coarseSampleSeconds);
        body.put("groupedAnalysis", groupedAnalysis);
        if (mindMapMode != null) body.put("mindMapMode", mindMapMode);
        if (region != null) body.put("ignoredRegion", region);
        if (subtitleCallbackToken != null) body.put("subtitleCallbackToken", subtitleCallbackToken);
        return agent.post().uri(endpoint).body(body)
            .retrieve().body(TranscriptionController.TranscriptResult.class);
    }

    @Override public void resetAnalysis(String fileId) {
        agent.post().uri("/analysis-reset").body(Map.of("fileId", fileId)).retrieve().toBodilessEntity();
    }
    @Override public void cancelAnalysis(String fileId) {
        agent.post().uri("/analysis-cancel").body(Map.of("fileId", fileId)).retrieve().toBodilessEntity();
    }
    @Override public TranscriptionController.MindMapResult generateMindMap(String courseId, boolean groupedAnalysis,
            List<TranscriptionController.TranscriptSegment> segments, List<TranscriptionController.PageGroup> pages) {
        return generateMindMap(courseId, groupedAnalysis, segments, pages, List.of());
    }
    @Override public TranscriptionController.MindMapResult generateMindMap(String courseId, boolean groupedAnalysis,
            List<TranscriptionController.TranscriptSegment> segments, List<TranscriptionController.PageGroup> pages,
            List<TranscriptionController.VisualEvidence> visuals) {
        return generateMindMap(courseId, groupedAnalysis, segments, pages, visuals, null);
    }
    @Override public TranscriptionController.MindMapResult generateMindMap(String courseId, boolean groupedAnalysis,
            List<TranscriptionController.TranscriptSegment> segments, List<TranscriptionController.PageGroup> pages,
            List<TranscriptionController.VisualEvidence> visuals, IgnoreRegion region) {
        return generateMindMap(courseId,groupedAnalysis,segments,pages,visuals,region,null);
    }
    @Override public TranscriptionController.MindMapResult generateMindMap(String courseId, boolean groupedAnalysis,
            List<TranscriptionController.TranscriptSegment> segments, List<TranscriptionController.PageGroup> pages,
            List<TranscriptionController.VisualEvidence> visuals, IgnoreRegion region, String mindMapMode) {
        if (mindMapMode != null) groupedAnalysis="grouped".equals(mindMapMode);
        var body = new LinkedHashMap<String,Object>();
        body.put("courseId", courseId); body.put("groupedAnalysis", groupedAnalysis);
        if (mindMapMode != null) body.put("mindMapMode",mindMapMode);
        body.put("segments", segments); body.put("pageGroups", pages); body.put("visualEvidence", visuals);
        if (region != null) body.put("ignoredRegion", region);
        return agent.post().uri("/mind-map").body(body).retrieve().body(TranscriptionController.MindMapResult.class);
    }

    @Override public Map<String,Object> generateSubtitles(String language,
        List<TranscriptionController.TranscriptSegment> segments,
        List<TranscriptionController.PageGroup> pageGroups, String targetLanguage) {
        return agent.post().uri("/subtitles").body(Map.of("language", language, "segments", segments,
            "pageGroups", pageGroups, "targetLanguage", targetLanguage))
            .retrieve().body(new ParameterizedTypeReference<Map<String,Object>>() {});
    }

    @Override
    public TranscriptionController.MindMapResult generateMindMap(
        List<TranscriptionController.TranscriptSegment> segments,
        List<TranscriptionController.PageGroup> pageGroups) {
        return agent.post().uri("/mind-map").body(Map.of("segments", segments, "pageGroups", pageGroups))
            .retrieve().body(TranscriptionController.MindMapResult.class);
    }
}
