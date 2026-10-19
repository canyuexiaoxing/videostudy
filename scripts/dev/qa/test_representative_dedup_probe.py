"""Specific last-frame occlusion probes, generated fixtures only."""
import unittest,importlib.util,tempfile
from pathlib import Path
import cv2,numpy as np
spec=importlib.util.spec_from_file_location('rep_probe',Path(__file__).with_name('representative-dedup-probe.py'));rep=importlib.util.module_from_spec(spec);spec.loader.exec_module(rep)
class RepresentativeTests(unittest.TestCase):
 def run_fixture(self,kind):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);frames=[]
   for t in (0,1):
    image=np.zeros((400,640,3),np.uint8);texts=[('course topic',30,55),('condition x > 0',30,110),('y = x - 10',30,170)]
    if t==1 and kind in ('added','occluded_added'):texts.append(('z = x + 20',330,250))
    blocks=[]
    for text,x,y in texts:
     cv2.putText(image,text,(x,y),cv2.FONT_HERSHEY_SIMPLEX,.8,(255,255,255),1,cv2.LINE_AA)
     (w,h),_=cv2.getTextSize(text,cv2.FONT_HERSHEY_SIMPLEX,.8,1)
     if t!=1 or kind not in ('occluded','occluded_added') or y!=170:blocks.append(dict(text=text,score=1.,polygon=[[x,y-h-2],[x+w,y-h-2],[x+w,y+3],[x,y+3]]))
    if t==1 and kind in ('occluded','occluded_added'):cv2.rectangle(image,(25,145),(240,182),(0,0,0),-1)
    if t==1 and kind=='blurred':image=cv2.GaussianBlur(image,(15,15),5)
    cv2.imwrite(str(folder/f'{t}.jpg'),image);frames.append(dict(frameTimeMs=t,ocrBlocks=blocks))
   f=rep.m.Features(frames,folder);pages=[dict(pageIndex=i+1,representativeFrameTimesMs=[i]) for i in (0,1)]
   return rep.deduplicate(pages,f)['selected']
 def test_final_occluded_without_new_content_keeps_earlier_clear(self):self.assertIn(0,self.run_fixture('occluded'))
 def test_final_occluded_with_new_formula_keeps_complementary_pair(self):self.assertEqual(self.run_fixture('occluded_added'),[0,1])
 def test_final_complete_added_content_replaces_previous(self):self.assertEqual(self.run_fixture('added'),[1])
 def test_identical_final_is_safe_to_keep(self):self.assertEqual(self.run_fixture('same'),[1])
 def test_final_blur_cannot_remove_earlier_clear(self):self.assertIn(0,self.run_fixture('blurred'))
 def test_single_group_complementary_representatives_unchanged(self):
  f=object.__new__(rep.m.Features);f.covers=lambda *a:True
  result=rep.deduplicate([dict(pageIndex=1,representativeFrameTimesMs=[0,1])],f)
  self.assertEqual(result['selected'],[0,1])
 def test_chain_requires_direct_coverage_of_every_original(self):
  f=object.__new__(rep.m.Features);f.covers=lambda a,b,*args:a==b or (a,b) in {(0,1),(1,2)}
  pages=[dict(pageIndex=i+1,representativeFrameTimesMs=[i]) for i in range(3)]
  result=rep.deduplicate(pages,f)['selected'];self.assertGreater(len(result),1)
  self.assertTrue(all(any(f.covers(t,q) for q in result) for t in range(3)))
if __name__=='__main__':unittest.main()
