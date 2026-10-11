from pathlib import Path
r=Path('E:/workp/videostudy')
(r/'agent-python/test_core_mind_map.py').write_text('''import unittest
from mind_map import build_mind_map
from test_mind_map import segment

class CoreMapTest(unittest.TestCase):
 def test_examples_separate_from_formulas_and_times_are_evidence_derived(self):
  result=build_mind_map([segment(1,'增长量等于现期减基期'),segment(8,'例题一，现期120，基期100'),segment(10,'增长量为20')],[],lambda _: {'topic':'增长量','children':[{'title':'增长量公式','sourceIds':['t_1']},{'title':'例题一','kind':'example','sourceIds':['t_8'],'children':[{'title':'代入120减100','sourceIds':['t_10']}]}],'examples':[{'title':'增长量计算例题','sourceIds':['t_10','invented','t_8'],'startMs':999999}]})
  self.assertEqual([n['title'] for n in result['root']['children'][0]['children']],['增长量公式'])
  self.assertEqual(result['examples'][0]['startMs'],8000)
  self.assertTrue(all(e['endMs']==10900 for e in result['examples']))
  self.assertTrue(all(e['children']==[] for e in result['examples']))
  self.assertTrue(all(ref['sourceId']!='invented' for e in result['examples'] for ref in e['evidenceRefs']))

 def test_example_only_course_is_empty_core_with_usable_timeline(self):
  result=build_mind_map([segment(1,'例题一')],[],lambda _: {'topic':'例题讲解','children':[],'examples':[{'title':'例题一','sourceIds':['t_1']}]})
  self.assertEqual(result['status'],'empty');self.assertEqual(result['root']['children'],[])
  self.assertEqual(result['examples'][0]['startMs'],1000)

 def test_unsupported_examples_are_omitted_and_policy_sent_to_same_request(self):
  calls=[]
  def ask(payload):
   calls.append(payload)
   return {'topic':'概念','children':[{'title':'公式','sourceIds':['t_1']}],'examples':[{'title':'编造例题','sourceIds':['unknown']}]}
  result=build_mind_map([segment(1)],[],ask)
  self.assertEqual(result['examples'],[]);self.assertEqual(len(calls),1)
  self.assertIn('contentPolicy',calls[0])
''',encoding='utf-8')
base=r/'backend-java/src/test/java/cn/videostudy/api'
(base/'MindMapExamplesTest.java').write_text('''package cn.videostudy.api;
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
}
''',encoding='utf-8')
