"""Synthetic failure probes for the experimental selector; no product tests."""
import unittest,tempfile,importlib.util
from pathlib import Path
import cv2,numpy as np
spec=importlib.util.spec_from_file_location('probe',Path(__file__).with_name('grouping-coverage-probe.py'));probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
class CoverageProbeTests(unittest.TestCase):
 def feature(self,lines):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);folder=Path(self.tmp.name);frames=[]
  for t,items in enumerate(lines):
   image=np.zeros((400,640,3),np.uint8);blocks=[]
   for text,x,y in items:
    cv2.putText(image,text,(x,y),cv2.FONT_HERSHEY_SIMPLEX,.8,(255,255,255),1,cv2.LINE_AA)
    (w,h),_=cv2.getTextSize(text,cv2.FONT_HERSHEY_SIMPLEX,.8,1)
    blocks.append(dict(text=text,score=1.,polygon=[[x,y-h-2],[x+w,y-h-2],[x+w,y+3],[x,y+3]]))
   cv2.imwrite(str(folder/f'{t}.jpg'),image);frames.append(dict(frameTimeMs=t,ocrBlocks=blocks))
  return probe.Features(frames,folder)
 def base(self):return [('course topic',30,55),('condition x > 0',30,110),('y = x - 10',30,170)]
 def test_added_formula_keeps_completed_frame(self):
  f=self.feature([self.base(),self.base()+[('z = x + 20',330,250)]])
  self.assertTrue(f.covers(0,1,.93));self.assertFalse(f.covers(1,0,.93));self.assertEqual(f.select([0,1],.93),[1])
 def test_erasure_with_new_content_keeps_complementary_frames(self):
  f=self.feature([self.base(),self.base()[:2]+[('z = x + 20',330,250)]])
  self.assertEqual(f.select([0,1],.93),[0,1])
 def test_changed_operator_cannot_replace_original(self):
  a=self.base();b=a[:2]+[('y = x + 10',30,170)]
  f=self.feature([a,b]);self.assertFalse(f.covers(0,1,.93));self.assertEqual(f.select([0,1],.93),[0,1])
 def test_changed_number_cannot_replace_original(self):
  a=self.base();b=a[:2]+[('y = x - 11',30,170)]
  f=self.feature([a,b]);self.assertFalse(f.covers(0,1,.93))
 def test_identical_content_prefers_later(self):
  f=self.feature([self.base(),self.base()]);self.assertEqual(f.select([0,1],.93),[1])
 def test_blank_or_weak_ocr_keeps_uncertain_frames(self):
  f=self.feature([[],self.base()]);self.assertEqual(f.select([0,1],.93),[0,1])
 def test_no_transitive_coverage_assumption(self):
  f=object.__new__(probe.Features)
  f.covers=lambda a,b,*args:a==b or (a,b) in {(0,1),(1,2)}
  selected=f.select([0,1,2],.93)
  self.assertTrue(all(any(f.covers(t,q) for q in selected) for t in [0,1,2]));self.assertGreater(len(selected),1)
if __name__=='__main__':unittest.main()
