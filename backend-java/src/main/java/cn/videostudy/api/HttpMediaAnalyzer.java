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
        var endpoint = "full".equals(mode) ? "/analyze" : "/transcribe";
        var body = new LinkedHashMap<String,Object>();
        body.put("fileId", fileId); body.put("visualAnalysisMode", visualAnalysisMode);
        body.put("coarseChangePercent", coarseChangePercent);
        if (subtitleCallbackToken != null) body.put("subtitleCallbackToken", subtitleCallbackToken);
        return agent.post().uri(endpoint).body(body)
            .retrieve().body(TranscriptionController.TranscriptResult.class);
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
