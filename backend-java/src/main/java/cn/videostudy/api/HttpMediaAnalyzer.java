package cn.videostudy.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;
import java.util.List;

@Component
public class HttpMediaAnalyzer implements MediaAnalyzer {
    private final RestClient agent;

    public HttpMediaAnalyzer(@Value("${agent.base-url}") String agentBaseUrl) {
        var requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(3000);
        requestFactory.setReadTimeout(30 * 60 * 1000);
        agent = RestClient.builder().baseUrl(agentBaseUrl).requestFactory(requestFactory).build();
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
        var endpoint = "full".equals(mode) ? "/analyze" : "/transcribe";
        return agent.post().uri(endpoint).body(Map.of("fileId", fileId, "visualAnalysisMode", visualAnalysisMode,
                                                  "coarseChangePercent", coarseChangePercent))
            .retrieve().body(TranscriptionController.TranscriptResult.class);
    }

    @Override
    public TranscriptionController.MindMapResult generateMindMap(
        List<TranscriptionController.TranscriptSegment> segments,
        List<TranscriptionController.PageGroup> pageGroups) {
        return agent.post().uri("/mind-map").body(Map.of("segments", segments, "pageGroups", pageGroups))
            .retrieve().body(TranscriptionController.MindMapResult.class);
    }
}
