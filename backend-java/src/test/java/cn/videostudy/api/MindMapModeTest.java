package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import org.springframework.http.MediaType;
import java.nio.file.Path;
import java.nio.file.Files;
import java.util.*;
import static cn.videostudy.api.TranscriptionController.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;
class MindMapModeTest {
 @TempDir Path uploads;
 TranscriptResult partial() { return new TranscriptResult("zh",List.of(),List.of(),null,null,new ReviewResult("completed","test","test","v1",List.of(),List.of())).withMindMap(new MindMapResult("failed","test","direct-v1",new MindMapNode("course","课程",0,0,List.of(),List.of()))); }
 @Test void invalidModeAndIncompatibleUploadsDoNotWrite() throws Exception {
  var store=mock(TranscriptionJobStore.class); var agent=mock(MediaAnalyzer.class);
  var file=new MockMultipartFile("file","lesson.mp4","video/mp4",new byte[]{1});
  var controller=new TranscriptionController(uploads.toString(),"full",store,agent);
  try {
   assertEquals(400,controller.upload(file,"both",2,2,null,false,false,"source","invalid").getStatusCode().value());
   assertEquals(400,controller.upload(file,"ocr_only",2,2,null,false,false,"source","direct").getStatusCode().value());
   verifyNoInteractions(store,agent); assertEquals(0,Files.list(uploads).count());
  } finally {controller.close();}
  var transcription=new TranscriptionController(uploads.toString(),"transcription",store,agent);
  try { assertEquals(400,transcription.upload(file,"both",2,2,null,false,false,"source","direct").getStatusCode().value()); } finally {transcription.close();}
 }
 @Test void explicitDirectOverridesGroupedFlagAndDoesNotRerunPartialMap() throws Exception {
  var store=mock(TranscriptionJobStore.class);var agent=mock(MediaAnalyzer.class);
  when(agent.analyze(anyString(),eq("full"),eq("both"),eq(2.0),eq(2),isNull(),isNull(),eq(false),eq("direct"))).thenReturn(partial());
  var controller=new TranscriptionController(uploads.toString(),"full",store,agent);
  try {
   var response=controller.upload(new MockMultipartFile("file","lesson.mp4","video/mp4",new byte[]{1}),"both",2,2,null,true,false,"source","direct");
   var id=((TranscriptionJob)response.getBody()).id(); verify(store).saveMindMapMode(id,"direct"); verify(store).saveGroupedAnalysis(id,false);
   verify(store,timeout(3000)).complete(eq(id),any()); verify(agent,times(1)).analyze(eq(id),eq("full"),eq("both"),eq(2.0),eq(2),isNull(),isNull(),eq(false),eq("direct"));
  } finally {controller.close();}
 }
 @Test void httpExplicitModeOverridesFlagForBothRequests() {
  var builder=RestClient.builder().baseUrl("http://agent");var server=MockRestServiceServer.bindTo(builder).build();var analyzer=new HttpMediaAnalyzer(builder.build());
  server.expect(requestTo("http://agent/analyze")).andExpect(jsonPath("$.mindMapMode").value("direct")).andExpect(jsonPath("$.groupedAnalysis").value(false)).andRespond(withSuccess("{\"language\":\"zh\",\"segments\":[]}",MediaType.APPLICATION_JSON));
  analyzer.analyze("course","full","both",2,2,null,null,true,"direct");server.verify();server.reset();
  server.expect(requestTo("http://agent/mind-map")).andExpect(jsonPath("$.mindMapMode").value("legacy")).andExpect(jsonPath("$.groupedAnalysis").value(false)).andRespond(withSuccess("{\"status\":\"empty\"}",MediaType.APPLICATION_JSON));
  analyzer.generateMindMap("course",true,List.of(),List.of(),List.of(),null,"legacy");server.verify();
 }

 @Test void migrationPreservesOldModeAndStoresDirectAcrossCancellation() {
  var ds=new org.springframework.jdbc.datasource.DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa","");
  var migration=new org.springframework.jdbc.datasource.init.ResourceDatabasePopulator();
  for(var name:List.of("V1__create_transcription_jobs.sql","V3__visual_analysis_mode.sql","V4__coarse_change_percent.sql","V13__grouped_analysis.sql","V14__mind_map_mode.sql")) migration.addScript(new org.springframework.core.io.ClassPathResource("db/migration/"+name));
  migration.execute(ds);
  var store=new TranscriptionJobStore(new org.springframework.jdbc.core.JdbcTemplate(ds),new com.fasterxml.jackson.databind.ObjectMapper());
  store.createQueued("course");assertEquals("legacy",store.findMindMapMode("course"));
  store.saveGroupedAnalysis("course",true);assertEquals("grouped",store.findMindMapMode("course"));
  store.saveMindMapMode("course","direct");assertEquals("direct",store.findMindMapMode("course"));
  assertTrue(store.cancel("course"));assertTrue(store.markQueuedIfFailed("course"));assertEquals("direct",store.findMindMapMode("course"));
 }
 @Test void manualRefreshUsesDirectAndPreservesCompletedMapWhenProviderFails() {
  var store=mock(TranscriptionJobStore.class);var agent=mock(MediaAnalyzer.class);
  var fixture=new GroupedAnalysisTest();var previous=fixture.map(fixture.image(1200));var result=fixture.result(previous);
  when(store.find("course")).thenReturn(Optional.of(new TranscriptionJob("course","completed",result,null)));
  when(agent.generateMindMap(eq("course"),eq(false),anyList(),anyList(),anyList(),isNull(),eq("direct"))).thenReturn(partial().mindMap());
  var controller=new MindMapController(store,agent);
  assertEquals(502,controller.generate("course",true,true,"direct").getStatusCode().value());
  verify(agent).generateMindMap(eq("course"),eq(false),anyList(),anyList(),anyList(),isNull(),eq("direct"));
  verify(store,never()).saveMindMap(anyString(),any());
 }

 @Test void overviewDispatchFollowsSavedUsableMapAndCannotDelayCompletion() throws Exception {
  var store=mock(TranscriptionJobStore.class);var agent=mock(MediaAnalyzer.class);var overview=mock(OverviewController.class);
  var fixture=new GroupedAnalysisTest();var result=fixture.result(fixture.map(fixture.image(1200)));
  when(agent.analyze(anyString(),eq("full"),eq("both"),eq(2.0),eq(2),isNull())).thenReturn(result);
  var controller=new TranscriptionController(uploads.toString(),"full",store,agent);
  org.springframework.test.util.ReflectionTestUtils.setField(controller,"overviews",overview);
  doThrow(new RuntimeException("note dispatch failed")).when(overview).request(anyString());
  try {
   var response=controller.upload(new MockMultipartFile("file","lesson.mp4","video/mp4",new byte[]{1}),"both",2,2,null,false,false,"source","legacy");
   var id=((TranscriptionJob)response.getBody()).id();verify(overview,timeout(3000)).request(id);
   var order=inOrder(store,overview);order.verify(store).complete(eq(id),any());order.verify(overview).request(id);
   verify(store,never()).markFailed(eq(id),anyString());
  } finally {controller.close();}
 }
}
