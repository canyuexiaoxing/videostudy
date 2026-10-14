package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
class PracticeModesTest {
 @Test void modeAndOriginalMaterialsRemainSeparateAndLegacyCompatible(){
  var fixture=new GroupedAnalysisTest();var result=fixture.result(fixture.map(fixture.image(1200)));
  var related=PracticeController.source(result,new PracticeController.Request(null,3,"basic",true,"related_materials"));
  var context=PracticeController.source(result,new PracticeController.Request(null,3,"basic",true,"map_context"));
  assertEquals("related_materials",related.get("mode"));assertSame(result.mindMap(),related.get("mindMap"));assertTrue(related.containsKey("sourceSegments"));assertTrue(related.containsKey("visualEvidence"));
  assertEquals("map_context",context.get("mode"));assertFalse(context.containsKey("sourceSegments"));
  assertFalse(PracticeController.source(result,new PracticeController.Request(null,3,"basic",true)).containsKey("mode"));
  assertThrows(IllegalArgumentException.class,()->PracticeController.source(result,new PracticeController.Request(null,3,"basic",true,"unknown")));
 }
 @Test void sameScopeDifferentModesUseDifferentCacheKeys(){
  var main=mock(TranscriptionJobStore.class);var store=mock(PracticeStore.class);var agent=mock(MediaAnalyzer.class);
  var id=UUID.randomUUID().toString();var fixture=new GroupedAnalysisTest();var result=fixture.result(fixture.map(fixture.image(1200)));
  when(main.find(id)).thenReturn(Optional.of(new cn.videostudy.api.TranscriptionController.TranscriptionJob(id,"completed",result,null)));
  var keys=new ArrayList<String>();
  when(store.request(eq(id),anyString(),anyString(),anyString(),anyMap(),eq(true))).thenAnswer(call->{keys.add(call.getArgument(2));return new PracticeStore.SetJob(UUID.randomUUID().toString(),id,"hash","scope","queued",call.getArgument(4),null,null);});
  when(store.publicSet(eq(id),anyString())).thenReturn(Map.of("status","queued"));
  var controller=new PracticeController(store,main,agent,new ObjectMapper());
  try {
   assertEquals(202,controller.generate(id,new PracticeController.Request(null,3,"basic",true,"map_context")).getStatusCode().value());
   assertEquals(202,controller.generate(id,new PracticeController.Request(null,3,"basic",true,"related_materials")).getStatusCode().value());
   assertEquals(2,keys.size());assertNotEquals(keys.get(0),keys.get(1));verifyNoInteractions(agent);
  }finally{controller.close();}
 }
}
