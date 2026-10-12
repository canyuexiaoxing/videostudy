package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.Path;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import static org.mockito.Mockito.mock;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
class HistoryControllerTest {
 @TempDir Path temp;
 @Test void emptyServerHistoryIsAvailableInFreshBrowser() throws Exception {
  var controller=new TranscriptionController(temp.toString(), "full",mock(TranscriptionJobStore.class),(id,mode)->{throw new IllegalStateException();});
  try { MockMvcBuilders.standaloneSetup(controller).build().perform(get("/api/transcriptions"))
   .andExpect(status().isOk()).andExpect(content().json("[]")); } finally {controller.close();}
 }
}
