package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.http.MediaType;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;
class VideoRegionControllerTest {
 @Test void forwardsBatchWithoutChangingTimes(){
  var builder=RestClient.builder().baseUrl("http://agent");var server=MockRestServiceServer.bindTo(builder).build();
  server.expect(requestTo("http://agent/video-region-detections")).andExpect(jsonPath("$.frames[0].timeMs").value(1234)).andRespond(withSuccess("{\"detections\":[{\"timeMs\":1234,\"status\":\"absent\",\"region\":null}]}",MediaType.APPLICATION_JSON));
  var controller=new VideoRegionController(builder.build());assertEquals(200,controller.detect(new VideoRegionController.Batch(List.of(new VideoRegionController.Frame(1234,"data:image/jpeg;base64,AA==")))).getStatusCode().value());server.verify();
 }
 @Test void rejectsInvalidOrDuplicateFramesBeforeCallingAgent(){
  var controller=new VideoRegionController(org.mockito.Mockito.mock(RestClient.class));
  assertEquals(400,controller.detect(new VideoRegionController.Batch(List.of())).getStatusCode().value());
  var frame=new VideoRegionController.Frame(0,"data:image/jpeg;base64,AA==");
  assertEquals(400,controller.detect(new VideoRegionController.Batch(List.of(frame,frame))).getStatusCode().value());
  assertEquals(400,controller.detect(new VideoRegionController.Batch(List.of(new VideoRegionController.Frame(-1,frame.image())))).getStatusCode().value());
 }
}
