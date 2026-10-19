"""Contract tests for forward representative replacement and bounded recovery."""
import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('forward',Path(__file__).with_name('forward-page-selection-probe.py'));p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
class Fake:
 def __init__(self,relations,occluded=()):self.relations=set(relations);self.occluded=set(occluded);self.loaded=set()
 def covers(self,a,b):self.loaded.update([a,b]);return a==b or (a,b) in self.relations
 def blocked(self,t):return t in self.occluded
class SelectionTests(unittest.TestCase):
 def test_new_complete_frame_replaces_old(self):
  r=p.forward([1,2],Fake({(1,2)}));self.assertEqual(r['selected'],[2])
 def test_occluded_final_prefers_clear_earlier(self):
  r=p.forward([1,2],Fake({(2,1)},[2]));self.assertEqual(r['selected'],[1])
 def test_occluded_with_new_content_keeps_both(self):self.assertEqual(p.forward([1,2],Fake(set(),[2]))['selected'],[1,2])
 def test_clear_candidate_can_replace_complementary_pair(self):
  r=p.forward([1,2],Fake({(1,3),(2,3)},[2]),{2:[3]},2);self.assertEqual(r['selected'],[3]);self.assertEqual(r['extra_reads'],1)
 def test_candidate_with_old_content_but_without_new_answer_cannot_replace(self):
  r=p.forward([1,2],Fake({(1,3)},[2]),{2:[3]},2);self.assertIn(2,r['selected'])
 def test_no_transitive_retirement(self):
  r=p.forward([1,2,3],Fake({(1,2),(2,3)}));self.assertIn(2,r['selected']);self.assertTrue(all(any(a==b or (a,b) in {(1,2),(2,3)} for b in r['selected']) for a in [1,2,3]))
 def test_every_proof_points_to_final_retained_frame(self):
  r=p.forward([1,2,3],Fake({(1,2),(2,3),(1,3)}));self.assertEqual(r['selected'],[3]);self.assertTrue(all(x['retained'] in r['selected'] for x in r['proofs']))
 def test_distinct_versions_retained(self):self.assertEqual(p.forward([1,2,3],Fake(set()))['selected'],[1,2,3])
 def test_additional_reads_have_course_budget(self):
  r=p.forward([1,2],Fake(set(),[1,2]),{1:[3,4],2:[5,6]},1);self.assertEqual(r['extra_reads'],1)
 def test_at_most_two_extra_reads_per_relation(self):
  r=p.forward([1],Fake(set(),[1]),{1:[2,3,4,5]},16);self.assertEqual(r['extra_reads'],2)
 def test_no_occlusion_no_member_search(self):
  r=p.forward([1,2],Fake(set()),{2:[3,4]},16);self.assertEqual(r['extra_reads'],0)
 def test_inputs_unchanged(self):
  sources=[1,2];candidates={2:[3]};p.forward(sources,Fake({(1,3),(2,3)},[2]),candidates,16);self.assertEqual(sources,[1,2]);self.assertEqual(candidates,{2:[3]})
if __name__=='__main__':unittest.main()
