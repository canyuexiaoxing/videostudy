package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import com.fasterxml.jackson.databind.ObjectMapper;
import static org.junit.jupiter.api.Assertions.*;
class AnalysisRegionTest {
 @Test void combinedRegionsRoundTripAndAllowFullAnalysis()throws Exception{
  var json=new ObjectMapper();var input="{\"analysisRegion\":{\"x\":0,\"y\":0,\"width\":1,\"height\":1},\"ignoredRegion\":{\"nodes\":[{\"timeMs\":0,\"region\":null},{\"timeMs\":5000,\"region\":{\"x\":0.8,\"y\":0.8,\"width\":0.1,\"height\":0.1}}]}}";
  assertEquals(IgnoreRegion.parse(input),IgnoreRegion.parse(json.writeValueAsString(IgnoreRegion.parse(input))));
 }
 @Test void rejectsCompleteExclusion(){
  assertThrows(IllegalArgumentException.class,()->IgnoreRegion.parse("{\"analysisRegion\":{\"x\":0.2,\"y\":0.2,\"width\":0.2,\"height\":0.2},\"ignoredRegion\":{\"x\":0.1,\"y\":0.1,\"width\":0.5,\"height\":0.5}}"));
 }
}
