package cn.videostudy.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import java.nio.file.Path;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import static cn.videostudy.api.TranscriptionController.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class GroupedAnalysisTest {
    @TempDir Path uploads;
    MindMapEvidence image(long ms) { return new MindMapEvidence("image", "frame_"+ms, ms, ms, "课件截图"); }
    MindMapResult map(MindMapEvidence evidence) {
        var detail = new MindMapNode("detail", "图中公式条件", evidence.startMs(), evidence.endMs(), List.of(evidence), List.of());
        var concept = new MindMapNode("concept", "公式", evidence.startMs(), evidence.endMs(), List.of(evidence), List.of(), List.of(detail));
        return new MindMapResult("completed", "test", "v1", new MindMapNode("course", "课程", evidence.startMs(), evidence.endMs(), List.of(), List.of(concept)));
    }
    TranscriptResult result(MindMapResult map) {
        return new TranscriptResult("zh", List.of(), List.of(new VisualEvidence(1200, List.of(), null)), null, null,
            new ReviewResult("completed", "test", "test", "v1", List.of(), List.of())).withMindMap(map);
    }
    @Test void imageEvidenceAndDetailsMustReferToRealFramesExactly() {
        assertTrue(MindMapValidator.isGrounded(map(image(1200)), List.of(), result(null).visualEvidence()));
        assertFalse(MindMapValidator.isGrounded(map(image(1200)), List.of()));
        assertFalse(MindMapValidator.isGrounded(map(image(1300)), List.of(), result(null).visualEvidence()));
        for (var forged : List.of(new MindMapEvidence("image", "frame_1200", 1200, 1201, "课件截图"),
            new MindMapEvidence("image", "frame_9999", 1200, 1200, "课件截图"),
            new MindMapEvidence("image", "frame_1200", 1200, 1200, "模型描述"))) {
            assertFalse(MindMapValidator.isGrounded(map(forged), List.of(), result(null).visualEvidence()));
            assertThrows(IllegalArgumentException.class, () -> PracticeController.source(result(map(forged)), new PracticeController.Request("concept",3,"basic",false)));
        }
    }
    @Test void imageOnlyConceptAndItsDetailsCanSupplyPracticeWithoutRawImages() {
        var source = PracticeController.source(result(map(image(1200))), new PracticeController.Request("detail", 3, "basic", false));
        assertEquals("concept", source.get("scopeNodeId"));
        var nodes = (List<?>) source.get("nodes"); assertEquals(2, nodes.size());
        var ref = (Map<?,?>)((List<?>)((Map<?,?>)nodes.getFirst()).get("evidenceRefs")).getFirst();
        assertEquals("image", ref.get("sourceType")); assertEquals("frame_1200", ref.get("sourceId"));
        assertFalse(source.toString().contains("base64"));
    }
    @Test void groupedFlagDefaultsFalseAndPersistsForRetry() {
        var ds = new DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1", "sa", "");
        var populator = new ResourceDatabasePopulator();
        for(var migration : List.of("V1__create_transcription_jobs.sql","V3__visual_analysis_mode.sql","V4__coarse_change_percent.sql","V13__grouped_analysis.sql"))
            populator.addScript(new ClassPathResource("db/migration/"+migration));
        populator.execute(ds);
        var store = new TranscriptionJobStore(new JdbcTemplate(ds), new ObjectMapper());
        store.createQueued("legacy"); assertFalse(store.findGroupedAnalysis("legacy"));
        store.saveGroupedAnalysis("legacy", true); assertTrue(store.findGroupedAnalysis("legacy"));
        assertTrue(store.cancel("legacy"));
        assertThrows(IllegalStateException.class, () -> store.complete("legacy", result(null)));
        assertEquals("analysis_cancelled", store.find("legacy").orElseThrow().error());
        assertTrue(store.markQueuedIfFailed("legacy")); assertTrue(store.findGroupedAnalysis("legacy"));
    }
    @Test void httpForwardsExplicitGroupedFlagAndCourseContext() {
        var builder = RestClient.builder().baseUrl("http://agent");
        var server = MockRestServiceServer.bindTo(builder).build();
        var analyzer = new HttpMediaAnalyzer(builder.build());
        server.expect(requestTo("http://agent/analyze")).andExpect(jsonPath("$.groupedAnalysis").value(true))
            .andRespond(withSuccess("{\"language\":\"zh\",\"segments\":[],\"visualEvidence\":[]}", org.springframework.http.MediaType.APPLICATION_JSON));
        analyzer.analyze("course", "full", "both", 2, 2, null, null, true);
        server.verify();
        server.reset();
        server.expect(requestTo("http://agent/mind-map")).andExpect(jsonPath("$.groupedAnalysis").value(true))
            .andExpect(jsonPath("$.courseId").value("course"))
            .andExpect(jsonPath("$.visualEvidence[0].frameTimeMs").value(1200))
            .andRespond(withSuccess("{\"status\":\"empty\"}", org.springframework.http.MediaType.APPLICATION_JSON));
        analyzer.generateMindMap("course",true,List.of(),List.of(),result(null).visualEvidence());
        server.verify();
    }
    @Test void uploadOptInPersistsAndRetryUsesSavedModeAfterReset() throws Exception {
        var store = mock(TranscriptionJobStore.class); var agent = mock(MediaAnalyzer.class);
        when(agent.analyze(anyString(), eq("full"), eq("both"), eq(2.0), eq(2), isNull(), isNull(), eq(true))).thenReturn(result(null));
        var controller = new TranscriptionController(uploads.toString(), "full", store, agent);
        try {
            var response = controller.upload(new MockMultipartFile("file", "lesson.mp4", "video/mp4", new byte[]{1}),"both",2,2,null,true,false,"source");
            var id = ((TranscriptionJob)response.getBody()).id();
            verify(store).saveGroupedAnalysis(id,true);
            verify(store, timeout(3000)).complete(eq(id), any());
            var retryId = UUID.randomUUID().toString(); Files.write(uploads.resolve(retryId),new byte[]{1});
            when(store.find(retryId)).thenReturn(Optional.of(new TranscriptionJob(retryId,"failed",null,"analysis_cancelled")));
            when(store.markQueuedIfFailed(retryId)).thenReturn(true);
            when(store.findGroupedAnalysis(retryId)).thenReturn(true);
            when(store.findCoarseChangePercent(retryId)).thenReturn(2.0);when(store.findCoarseSampleSeconds(retryId)).thenReturn(2);
            assertEquals(202, controller.retry(retryId).getStatusCode().value());
            verify(agent).resetAnalysis(retryId);
            verify(agent, timeout(3000)).analyze(eq(retryId),eq("full"),eq("both"),eq(2.0),eq(2),isNull(),isNull(),eq(true));
        } finally { controller.close(); }
    }

    @Test void groupedPartialMapIsStoredWithoutAutomaticExtraModelCalls() throws Exception {
        var store=mock(TranscriptionJobStore.class);var agent=mock(MediaAnalyzer.class);
        var partial=new MindMapResult("failed","test","whole-course-group-evidence-v2",
            new MindMapNode("course","待核对课程",0,0,List.of(),List.of()));
        when(agent.analyze(anyString(),eq("full"),eq("both"),eq(2.0),eq(2),isNull(),isNull(),eq(true))).thenReturn(result(partial));
        var controller=new TranscriptionController(uploads.toString(),"full",store,agent);
        try {
            var response=controller.upload(new MockMultipartFile("file","lesson.mp4","video/mp4",new byte[]{1}),"both",2,2,null,true,false,"source");
            var id=((TranscriptionJob)response.getBody()).id();
            verify(store,timeout(3000)).complete(eq(id),any());
            verify(agent,times(1)).analyze(eq(id),eq("full"),eq("both"),eq(2.0),eq(2),isNull(),isNull(),eq(true));
            verify(store,never()).markFailed(eq(id),anyString());
        } finally {controller.close();}
    }

    @Test void cancellationRejectsLateCompletionAndKeepsUploadForRetry() throws Exception {
        var store = mock(TranscriptionJobStore.class);
        var started = new CountDownLatch(1); var release = new CountDownLatch(1); var returned = new CountDownLatch(1);
        var analyzer = new MediaAnalyzer() {
            public TranscriptResult analyze(String id, String mode) {
                started.countDown();
                try { assertTrue(release.await(3, TimeUnit.SECONDS)); } catch(InterruptedException e) { throw new IllegalStateException(e); }
                returned.countDown(); return result(null);
            }
        };
        var controller = new TranscriptionController(uploads.toString(), "full", store, analyzer);
        try {
            var response = controller.upload(new MockMultipartFile("file", "lesson.mp4", "video/mp4", new byte[]{1}),"both",2,2,null,false,false,"source");
            var id = ((TranscriptionJob)response.getBody()).id(); assertTrue(started.await(3,TimeUnit.SECONDS));
            when(store.find(id)).thenReturn(Optional.of(new TranscriptionJob(id,"processing",null,null)));
            when(store.cancel(id)).thenReturn(true);
            assertEquals(200, controller.cancel(id).getStatusCode().value());
            release.countDown(); assertTrue(returned.await(3,TimeUnit.SECONDS));
            verify(store, after(100).never()).complete(eq(id), any());
            verify(store, never()).markFailed(eq(id), anyString());
            assertTrue(Files.exists(uploads.resolve(id)));
        } finally { release.countDown(); controller.close(); }
    }
}
