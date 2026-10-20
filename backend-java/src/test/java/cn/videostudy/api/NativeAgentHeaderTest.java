package cn.videostudy.api;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import java.net.InetSocketAddress;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
class NativeAgentHeaderTest {
 @Test void everyAgentClientPassesNativeCapabilityAndLegacyModeOmitsIt()throws Exception{
  for(String token:List.of("test-private-native-capability","")){
   var headers=new ArrayList<String>();var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
   server.createContext("/",exchange->{headers.add(exchange.getRequestHeaders().getFirst(NativeRuntimeFilter.HEADER));exchange.getRequestBody().readAllBytes();byte[] reply="{}".getBytes(java.nio.charset.StandardCharsets.UTF_8);exchange.getResponseHeaders().set("Content-Type","application/json");exchange.sendResponseHeaders(200,reply.length);exchange.getResponseBody().write(reply);exchange.close();});server.start();
   try{String origin="http://127.0.0.1:"+server.getAddress().getPort();
    new HttpMediaAnalyzer(origin,token).generatePractice(Map.of());
    new CompatibilityController(System.getProperty("java.io.tmpdir"),origin,token).capabilities();
    new VideoRegionController(origin,token).detect(new VideoRegionController.Batch(List.of(new VideoRegionController.Frame(0,"data:image/jpeg;base64,AA=="))));
    var study=new StudyController(origin,token);var course=study.createCourse(new StudyController.CreateCourse("test",1)).getBody();study.createJob(course.id());
    assertEquals(4,headers.size());for(String header:headers)assertEquals(token.isEmpty()?null:token,header);
   }finally{server.stop(0);}
  }
 }
}
