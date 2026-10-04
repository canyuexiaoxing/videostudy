package cn.videostudy.api;

import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.http.MediaType;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class SubtitleTransportTest {
    @Test void privateCallbackAndSubtitleTextAreSerializedAtHttpBoundary() {
        var builder = RestClient.builder().baseUrl("http://agent");
        var server = MockRestServiceServer.bindTo(builder).build();
        var analyzer = new HttpMediaAnalyzer(builder.build());
        server.expect(requestTo("http://agent/analyze"))
            .andExpect(jsonPath("$.subtitleCallbackToken").value("private-token"))
            .andExpect(jsonPath("$.coarseChangePercent").value(2.0))
            .andRespond(withSuccess("{\"language\":\"zh\",\"segments\":[]}", MediaType.APPLICATION_JSON));
        server.expect(requestTo("http://agent/transcribe"))
            .andExpect(jsonPath("$.subtitleCallbackToken").doesNotExist())
            .andRespond(withSuccess("{\"language\":\"zh\",\"segments\":[]}", MediaType.APPLICATION_JSON));
        server.expect(requestTo("http://agent/subtitles"))
            .andExpect(jsonPath("$.targetLanguage").value("en"))
            .andExpect(jsonPath("$.language").value("zh"))
            .andExpect(jsonPath("$.segments").isArray())
            .andExpect(jsonPath("$.subtitleCallbackToken").doesNotExist())
            .andRespond(withSuccess("{\"status\":\"completed\"}", MediaType.APPLICATION_JSON));
        server.expect(requestTo("http://agent/chapters"))
            .andExpect(jsonPath("$.segments").isArray())
            .andExpect(jsonPath("$.pageGroups").isArray())
            .andRespond(withSuccess("{\"status\":\"completed\",\"chapters\":[]}", MediaType.APPLICATION_JSON));
        analyzer.analyze("test-id", "full", "both", 2.0, "private-token");
        analyzer.analyze("test-id", "transcription", "both", 2.0);
        assertEquals("completed", analyzer.generateSubtitles("zh", List.of(), List.of(), "en").get("status"));
        assertEquals("completed", analyzer.generateChapters(List.of(), List.of()).get("status"));
        server.verify();
    }
}
