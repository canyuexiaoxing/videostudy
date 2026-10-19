"""Offline-only contract tests for page collection prototype."""
import importlib.util, tempfile, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('versions_probe',Path(__file__).with_name('page-versions-probe.py'))
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
class Contracts(unittest.TestCase):
 def test_positions_and_multiple_anchors_required(self):
  a=[('shared long problem condition', (0,0,.8,.1)),('second fixed problem statement', (0,.2,.8,.3))]
  self.assertTrue(p.anchor_match(a,a))
  self.assertFalse(p.anchor_match(a[:1],a[:1]))
  self.assertFalse(p.anchor_match(a,[(t,(x,y+.5,z,w+.5)) for t,(x,y,z,w) in a]))
 def test_different_problem_is_not_same(self):
  self.assertFalse(p.anchor_match([('common course title',(0,0,1,.1)),('find limit of expression one',(0,.2,1,.3))],[('common course title',(0,0,1,.1)),('find integral of expression two',(0,.2,1,.3))]))
 def test_changed_sign_is_not_exact_duplicate(self):
  self.assertNotEqual(p.ocr_signature({'ocrBlocks':[{'text':'x-1'}]}),p.ocr_signature({'ocrBlocks':[{'text':'x+1'}]}))
 def test_low_confidence_not_used_for_extra_selection(self):
  self.assertEqual(p.tokens({'ocrBlocks':[{'text':'new answer','score':.2}]}),set())
 def test_addition_budget_does_not_limit_original_versions(self):
  originals=list(range(30)); extras=[(100-i,1000+i) for i in range(30)]
  selected=p.add_candidates(originals,extras,16)
  self.assertTrue(set(originals)<=set(selected));self.assertEqual(len(selected),46)
 def test_unknown_and_occluded_versions_are_preserved(self):
  self.assertEqual(p.add_candidates([1,2],[],16),[1,2])
 def test_identical_file_requires_same_ocr_and_region(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for t in (1,2,3):(root/f'{t}.jpg').write_bytes(b'identical frozen image')
   frames={1:{'ocrBlocks':[{'text':'x-1'}]},2:{'ocrBlocks':[{'text':'x-1'}]},3:{'ocrBlocks':[{'text':'x+1'}]}}
   kept,proofs=p.exact_duplicates([1,2,3],root,frames,{})
   self.assertEqual(kept,[2,3]);self.assertEqual(proofs,[{'removed':1,'retained':2}])
 def test_no_transitive_retirement(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for t in (1,2,3):(root/f'{t}.jpg').write_bytes(str(t).encode())
   kept,proofs=p.exact_duplicates([1,2,3],root,{t:{} for t in (1,2,3)},{})
   self.assertEqual(kept,[1,2,3]);self.assertFalse(proofs)
if __name__=='__main__':unittest.main()
