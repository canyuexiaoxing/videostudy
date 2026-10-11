package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import com.fasterxml.jackson.databind.ObjectMapper;
import static org.junit.jupiter.api.Assertions.*;
class IgnoreRegionTimelineTest {
 String a="{\"x\":0.7,\"y\":0.6,\"width\":0.2,\"height\":0.3}";
 @Test void parsesAndRoundTripsStaticAndTimeline() throws Exception {
  String json="{\"nodes\":[{\"timeMs\":0,\"region\":"+a+"},{\"timeMs\":5000,\"region\":null}]}";
  var parsed=IgnoreRegion.parse(json);
  var encoded=new ObjectMapper().writeValueAsString(parsed);
  assertEquals(parsed,IgnoreRegion.parse(encoded));
  assertTrue(encoded.contains("5000"));
  assertEquals(4,new ObjectMapper().readTree(new ObjectMapper().writeValueAsString(IgnoreRegion.parse(a))).size());
 }
 @Test void rejectsInvalidTimelineBoundaries() {
  for(String json:new String[]{"{\"nodes\":[]}","{\"nodes\":[{\"timeMs\":1,\"region\":"+a+"}]}","{\"nodes\":[{\"timeMs\":0,\"region\":"+a+"},{\"timeMs\":0,\"region\":null}]}","{\"nodes\":[{\"timeMs\":0,\"region\":"+a+"},{\"timeMs\":0.5,\"region\":null}]}"})assertThrows(IllegalArgumentException.class,()->IgnoreRegion.parse(json));
 }
}
