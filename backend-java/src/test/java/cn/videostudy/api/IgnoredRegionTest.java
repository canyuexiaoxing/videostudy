package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.datasource.embedded.*;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.jdbc.core.JdbcTemplate;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.client.RestClient;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.http.MediaType;
import java.nio.file.*;
import java.util.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class IgnoredRegionTest {
 @TempDir Path directory;
 static final String REGION="{\"x\":0.75,\"y\":0.5,\"width\":0.25,\"height\":0.5}";
 @Test void validatesCoordinatesBeforeSavingUpload() throws Exception {
  var store=mock(TranscriptionJobStore.class);var analyzer=mock(MediaAnalyzer.class);
  var controller=new TranscriptionController(directory.toString(),"full",store,analyzer);
  try {
   var mvc=MockMvcBuilders.standaloneSetup(controller).build();
   for(var invalid:List.of("{}","null","[]","broken","{\"x\":0,\"y\":0,\"width\":1,\"height\":1}",REGION.replace("0.75","1.1"),REGION.replace("0.75","\"0.75\"")))
    mvc.perform(multipart("/api/transcriptions").file(new MockMultipartFile("file","lesson.mp4","video/mp4",new byte[]{1})).param("ignoredRegion",invalid))
     .andExpect(status().isBadRequest()).andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.error").value("invalid_ignored_region"));
   verifyNoInteractions(store,analyzer);
   try(var files=Files.list(directory)){assertEquals(0,files.count());}
  } finally {controller.close();}
 }
 @Test void uploadAndRetryCarrySavedRegion() throws Exception {
  var store=mock(TranscriptionJobStore.class);var analyzer=mock(MediaAnalyzer.class);
  var region=IgnoreRegion.parse(REGION);
  var controller=new TranscriptionController(directory.toString(),"full",store,analyzer);
  try {
   var mvc=MockMvcBuilders.standaloneSetup(controller).build();
   mvc.perform(multipart("/api/transcriptions").file(new MockMultipartFile("file","lesson.mp4","video/mp4",new byte[]{1})).param("ignoredRegion",REGION)).andExpect(status().isAccepted());
   verify(store).createQueued(anyString(),eq("both"),eq(3.0),eq(2),eq(region));
   verify(analyzer,timeout(3000)).analyze(anyString(),eq("full"),eq("both"),eq(3.0),eq(2),isNull(),eq(region));
   var id=UUID.randomUUID().toString();Files.write(directory.resolve(id),new byte[]{1});
   when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id,"failed",null,"failed")));
   when(store.markQueuedIfFailed(id)).thenReturn(true);when(store.findVisualAnalysisMode(id)).thenReturn("both");
   when(store.findCoarseChangePercent(id)).thenReturn(2.0);when(store.findCoarseSampleSeconds(id)).thenReturn(4);
   when(store.findIgnoredRegion(id)).thenReturn(region);
   mvc.perform(post("/api/transcriptions/"+id+"/retry")).andExpect(status().isAccepted());
   verify(analyzer,timeout(3000)).analyze(eq(id),eq("full"),eq("both"),eq(2.0),eq(4),isNull(),eq(region));
  } finally {controller.close();}
 }
 @Test void persistsRegionAndOldJobsRemainUnmasked() {
  var ds=new EmbeddedDatabaseBuilder().setType(EmbeddedDatabaseType.H2).generateUniqueName(true).build();
  try {
   new ResourceDatabasePopulator(new ClassPathResource("db/migration/V1__create_transcription_jobs.sql"),new ClassPathResource("db/migration/V3__visual_analysis_mode.sql"),new ClassPathResource("db/migration/V4__coarse_change_percent.sql"),new ClassPathResource("db/migration/V10__coarse_sample_seconds.sql"),new ClassPathResource("db/migration/V11__ignored_region.sql")).execute(ds);
   var store=new TranscriptionJobStore(new JdbcTemplate(ds),new ObjectMapper());
   store.createQueued("old");store.createQueued("new","both",2.0,4,IgnoreRegion.parse(REGION));
   assertNull(store.findIgnoredRegion("old"));assertEquals(IgnoreRegion.parse(REGION),store.findIgnoredRegion("new"));
  } finally {ds.shutdown();}
 }
 @Test void httpTransportCarriesRegionAndCallback() {
  var builder=RestClient.builder().baseUrl("http://agent");var server=MockRestServiceServer.bindTo(builder).build();
  server.expect(requestTo("http://agent/analyze")).andExpect(org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath("$.ignoredRegion.x").value(.75))
   .andExpect(org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath("$.subtitleCallbackToken").value("token"))
   .andRespond(withSuccess("{\"language\":\"zh\",\"segments\":[]}",MediaType.APPLICATION_JSON));
  new HttpMediaAnalyzer(builder.build()).analyze("id","full","both",2.0,4,"token",IgnoreRegion.parse(REGION));server.verify();
 }
}
