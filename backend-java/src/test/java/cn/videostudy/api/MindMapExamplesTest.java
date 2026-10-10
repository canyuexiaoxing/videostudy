package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
class MindMapExamplesTest {
 @Test void validatesTimelineEvidenceEvenWhenCoreIsEmpty() {
  var speech=List.of(new TranscriptionController.TranscriptSegment("s1",1000,2000,"例题一"));
  var ref=new TranscriptionController.MindMapEvidence("transcript","s1",1000,2000,"例题一");
  var root=new TranscriptionController.MindMapNode("course","课程知识导图",0,0,List.of(),List.of());
  var example=new TranscriptionController.MindMapNode("example1","例题一",1000,2000,List.of(ref),List.of());
  assertTrue(MindMapValidator.isGrounded(new TranscriptionController.MindMapResult("empty",null,null,"v3",null,root,List.of(example)),speech));
  var bad=new TranscriptionController.MindMapNode("example1","例题一",9999,20000,List.of(ref),List.of());
  assertFalse(MindMapValidator.isGrounded(new TranscriptionController.MindMapResult("empty",null,null,"v3",null,root,List.of(bad)),speech));
  var unsupported=new TranscriptionController.MindMapNode("example1","例题一",0,0,List.of(),List.of());
  assertFalse(MindMapValidator.isGrounded(new TranscriptionController.MindMapResult("empty",null,null,"v3",null,root,List.of(unsupported)),speech));
 }

 @Test void refreshCanMigrateOldExampleMapToIndependentTimeline() {
  var speech=List.of(new TranscriptionController.TranscriptSegment("s1",1000,2000,"例题一"));
  var ref=new TranscriptionController.MindMapEvidence("transcript","s1",1000,2000,"例题一");
  var example=new TranscriptionController.MindMapNode("example1","例题一",1000,2000,List.of(ref),List.of());
  var oldRoot=new TranscriptionController.MindMapNode("course","课程知识导图",1000,2000,List.of(ref),List.of(example));
  var oldMap=new TranscriptionController.MindMapResult("completed",null,null,"v2",null,oldRoot);
  var result=new TranscriptionController.TranscriptResult("zh",speech,List.of(),null,null,null).withMindMap(oldMap);
  var emptyRoot=new TranscriptionController.MindMapNode("course","课程知识导图",0,0,List.of(),List.of());
  var generated=new TranscriptionController.MindMapResult("empty",null,null,"v3",null,emptyRoot,List.of(example));
  var store=org.mockito.Mockito.mock(TranscriptionJobStore.class);
  var analyzer=org.mockito.Mockito.mock(MediaAnalyzer.class);
  org.mockito.Mockito.when(store.find("job")).thenReturn(java.util.Optional.of(new TranscriptionController.TranscriptionJob("job","completed",result,null)));
  org.mockito.Mockito.when(analyzer.generateMindMap(org.mockito.ArgumentMatchers.anyList(),org.mockito.ArgumentMatchers.anyList())).thenReturn(generated);
  assertEquals(200,new MindMapController(store,analyzer).generate("job",true).getStatusCode().value());
  org.mockito.Mockito.verify(store).saveMindMap("job",generated);
 }
}
