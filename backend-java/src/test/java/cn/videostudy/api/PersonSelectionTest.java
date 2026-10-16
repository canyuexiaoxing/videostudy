package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.client.RestClient;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.http.MediaType;
import org.springframework.jdbc.datasource.embedded.*;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;import java.util.*;
import static org.mockito.Mockito.*;import static org.mockito.ArgumentMatchers.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;
class PersonSelectionTest {
 @TempDir Path directory;
 @Test void uploadAndRetryKeepSelectedMode() throws Exception {
  var store=mock(TranscriptionJobStore.class);var agent=mock(MediaAnalyzer.class);
  var fixture=new GroupedAnalysisTest();var result=fixture.result(fixture.map(fixture.image(1200)));
  when(agent.analyze(anyString(),eq("full"),eq("both"),eq(2.0),eq(2),isNull(),isNull(),eq(false),eq("legacy"),eq("adjacent"))).thenReturn(result);
  var controller=new TranscriptionController(directory.toString(),"full",store,agent);
  try {
   var mvc=MockMvcBuilders.standaloneSetup(controller).build();
   mvc.perform(multipart("/api/transcriptions").file(new MockMultipartFile("file","lesson.mp4","video/mp4",new byte[]{1})).param("personSelectionMode","adjacent")).andExpect(status().isAccepted());
   verify(store).savePersonSelectionMode(anyString(),eq("adjacent"));
   verify(agent,timeout(3000)).analyze(anyString(),eq("full"),eq("both"),eq(2.0),eq(2),isNull(),isNull(),eq(false),eq("legacy"),eq("adjacent"));
   var id=UUID.randomUUID().toString();Files.write(directory.resolve(id),new byte[]{1});
   when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id,"failed",null,"failed")));when(store.markQueuedIfFailed(id)).thenReturn(true);
   when(store.findVisualAnalysisMode(id)).thenReturn("both");when(store.findCoarseChangePercent(id)).thenReturn(2.0);when(store.findCoarseSampleSeconds(id)).thenReturn(2);when(store.findPersonSelectionMode(id)).thenReturn("adjacent");
   mvc.perform(post("/api/transcriptions/"+id+"/retry")).andExpect(status().isAccepted());
   verify(agent,timeout(3000)).analyze(eq(id),eq("full"),eq("both"),eq(2.0),eq(2),isNull(),isNull(),eq(false),eq("legacy"),eq("adjacent"));
   mvc.perform(multipart("/api/transcriptions").file(new MockMultipartFile("file","lesson.mp4","video/mp4",new byte[]{1})).param("personSelectionMode","cpu")).andExpect(status().isBadRequest()).andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.error").value("invalid_person_selection_mode"));
  } finally {controller.close();}
 }
 @Test void settingIsPersistedAndOldRowsRemainUnspecified(){
  var ds=new EmbeddedDatabaseBuilder().setType(EmbeddedDatabaseType.H2).generateUniqueName(true).build();
  try {
   new ResourceDatabasePopulator(new ClassPathResource("db/migration/V1__create_transcription_jobs.sql"),new ClassPathResource("db/migration/V3__visual_analysis_mode.sql"),new ClassPathResource("db/migration/V4__coarse_change_percent.sql"),new ClassPathResource("db/migration/V15__person_selection_mode.sql")).execute(ds);
   var store=new TranscriptionJobStore(new JdbcTemplate(ds),new ObjectMapper());store.createQueued("old");store.createQueued("new");
   assertNull(store.findPersonSelectionMode("old"));store.savePersonSelectionMode("new","adjacent");assertEquals("adjacent",store.findPersonSelectionMode("new"));store.savePersonSelectionMode("new","off");assertEquals("off",store.findPersonSelectionMode("new"));assertThrows(IllegalArgumentException.class,()->store.savePersonSelectionMode("new","cpu"));
  } finally {ds.shutdown();}
 }
 @Test void httpCarriesModeAlongsideMapMode(){
  var builder=RestClient.builder().baseUrl("http://agent");var server=MockRestServiceServer.bindTo(builder).build();
  server.expect(requestTo("http://agent/analyze")).andExpect(org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath("$.personSelectionMode").value("adjacent")).andExpect(org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath("$.mindMapMode").value("direct")).andRespond(withSuccess("{\"language\":\"zh\",\"segments\":[]}",MediaType.APPLICATION_JSON));
  new HttpMediaAnalyzer(builder.build()).analyze("id","full","both",2.0,2,null,null,false,"direct","adjacent");server.verify();
 }
}
