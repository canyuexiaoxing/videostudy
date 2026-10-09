package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static cn.videostudy.api.TranscriptionController.*;
class PracticeControllerTest {
    TranscriptResult course(){
        var leaf=new MindMapNode("n1","增长量",0,1000,List.of(new MindMapEvidence("transcript","s1",99,99,"不可用的旧引用")),List.of());
        var root=new MindMapNode("root","课程",0,1000,List.of(),List.of(leaf));
        return new TranscriptResult("zh",List.of(new TranscriptSegment("s1",0,1000,"增长量等于现期减基期")),List.of(),null,null,null).withMindMap(new MindMapResult("completed","deepseek","v1",root));
    }
    @Test void snapshotsOriginalEvidenceAndSelectedNode(){
        var source=PracticeController.source(course(),new PracticeController.Request("n1",3,"basic",false));
        var node=(Map<?,?>)((List<?>)source.get("nodes")).getFirst();
        var ref=(Map<?,?>)((List<?>)node.get("evidenceRefs")).getFirst();
        assertEquals("增长量等于现期减基期",ref.get("quote"));assertEquals(0L,ref.get("startMs"));
        assertEquals(3,source.get("count"));
    }
    @Test void rejectsUnknownNodeAndUnsupportedSettings(){
        assertThrows(IllegalArgumentException.class,()->PracticeController.source(course(),new PracticeController.Request("unknown",3,"basic",false)));
        assertThrows(IllegalArgumentException.class,()->PracticeController.source(course(),new PracticeController.Request(null,100,"basic",false)));
    }
    @Test void pageSelectionUsesEvidenceTimesRatherThanParentDisplayTime(){
        var original=course();
        var lateLeaf=new MindMapNode("late","后续知识点",5000,6000,List.of(new MindMapEvidence("transcript","s2",5000,6000,"后续语音")),List.of());
        var root=new MindMapNode("root","课程",0,1000,List.of(),List.of(lateLeaf));
        var page=new PageGroup(2,4000,7000,List.of(5000L),List.of(5000L),"same","",List.of(),new ImageAnalysis("completed","后续页","正确的后续内容",List.of(),List.of()));
        var result=new TranscriptResult("zh",List.of(new TranscriptSegment("s2",5000,6000,"后续语音")),List.of(),null,null,null,List.of(page),List.of(),"image","v1",2.0,new MindMapResult("completed","model","v1",root));
        var source=PracticeController.source(result,new PracticeController.Request(null,3,"basic",false));
        assertEquals(1,((List<?>)source.get("pages")).size());
    }
    @Test void validatesCanonicalCitationsAndRejectsAnswerLeakDiagrams(){
        var source=PracticeController.source(course(),new PracticeController.Request(null,3,"basic",false));
        var node=(Map<?,?>)((List<?>)source.get("nodes")).getFirst();
        var q=new HashMap<String,Object>();
        q.putAll(Map.of("id",UUID.randomUUID().toString(),"nodeId","n1","kind","true_false","options",List.of("正确","错误"),"answerIndex",0,"title","概念","prompt","增长量是数量差。","explanation","现期减基期","takeaway","区分增长率","distractorReasons",List.of("","不符合公式")));
        q.put("citations",node.get("evidenceRefs"));
        var result=Map.<String,Object>of("status","completed","questions",List.of(q));
        assertDoesNotThrow(()->PracticeController.validate(result,source));
        q.put("diagram",Map.of("kind","svg","content","<svg/>"));
        assertThrows(IllegalArgumentException.class,()->PracticeController.validate(result,source));
        q.remove("diagram");q.put("citations",List.of(Map.of("sourceId","s1","startMs",0,"endMs",1000,"quote","改写了依据")));
        assertThrows(IllegalArgumentException.class,()->PracticeController.validate(result,source));
    }
}
