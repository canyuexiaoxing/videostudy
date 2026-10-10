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

class AnalysisProgressTest {
 @TempDir Path directory;
 @Test void readsOnlyTaskProgressAndPreservesOldFourFieldConstructor() throws Exception {
  var store=mock(TranscriptionJobStore.class);
  var controller=new TranscriptionController(directory.toString(),"full",store,mock(MediaAnalyzer.class));
  org.springframework.test.util.ReflectionTestUtils.setField(controller,"keyframeDirectory",directory.toString());
  var id=UUID.randomUUID().toString();var other=UUID.randomUUID().toString();
  var path=directory.resolve(id).resolve(".analysis");Files.createDirectories(path);
  Files.writeString(path.resolve("progress.json"),"{\"stage\":\"pages\",\"completedStages\":3,\"totalStages\":5,\"completedUnits\":8,\"totalUnits\":20}");
  when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id,"processing",null,null)));
  when(store.find(other)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(other,"processing",null,null)));
  try {
   var mvc=MockMvcBuilders.standaloneSetup(controller).build();
   mvc.perform(get("/api/transcriptions/"+id)).andExpect(status().isOk()).andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.progress.completedUnits").value(8));
   mvc.perform(get("/api/transcriptions/"+other)).andExpect(status().isOk()).andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.progress").doesNotExist());
   Files.writeString(path.resolve("progress.json"),"broken");
   mvc.perform(get("/api/transcriptions/"+id)).andExpect(status().isOk()).andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.progress").doesNotExist());
   when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id,"completed",null,null)));
   mvc.perform(get("/api/transcriptions/"+id)).andExpect(status().isOk()).andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.progress").doesNotExist());
  } finally {controller.close();}
 }
}
