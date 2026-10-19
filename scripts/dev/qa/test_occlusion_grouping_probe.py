"""Failure cases for position-matched occlusion grouping, generated fixtures only."""
import importlib.util,unittest,sys,copy
from pathlib import Path
import numpy as np,cv2
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
s=importlib.util.spec_from_file_location('occ',Path(__file__).with_name('occlusion-grouping-probe.py'));p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
class OcclusionTests(unittest.TestCase):
 def frame(self,t,side=None,addition=False,other=False):
  image=np.full((180,320),255,np.uint8);blocks=[]
  lines=[('Shared lesson title',15,20),('Question one: find the integral',15,55),('Condition: x greater than zero',15,85),('y = x - 10',15,125)]
  if other:lines=[lines[0],('Question two: solve equation',15,55),('Condition: t less than zero',15,85),('z = t + 20',15,125)]
  if addition:lines.append(('answer z = 123',170,155))
  for text,x,y in lines:
   cv2.putText(image,text,(x,y),cv2.FONT_HERSHEY_SIMPLEX,.35,0,1);(w,h),_=cv2.getTextSize(text,cv2.FONT_HERSHEY_SIMPLEX,.35,1)
   blocks.append({'text':text,'score':1,'polygon':[[x,y-h-1],[min(319,x+w),y-h-1],[min(319,x+w),y+2],[x,y+2]]})
  mask=np.zeros((180,320),bool)
  if side=='left':mask[95:175,0:110]=True
  elif side=='right':mask[95:175,210:320]=True
  elif side=='all':mask[:]=True
  image[mask]=100
  blocks=[b for b in blocks if np.mean(mask[max(0,int(b['polygon'][0][1])):int(b['polygon'][2][1]),int(b['polygon'][0][0]):int(b['polygon'][1][0])])<.1]
  return p.Frame(t,image,~np.zeros_like(mask),mask,blocks,(320,180),True)
 def test_teacher_left_to_right_same_board(self):self.assertEqual(p.compare(self.frame(0,'left'),self.frame(1,'right'))['relation'],'same')
 def test_teacher_motion_not_counted_as_new_formula(self):self.assertEqual(p.compare(self.frame(0,'right'),self.frame(1,'left'))['relation'],'same')
 def test_new_formula_keeps_both_original_sources(self):
  result=p.compare(self.frame(0,'left'),self.frame(1,'right',addition=True));self.assertEqual(result['relation'],'same')
 def test_different_question_same_title_not_merged(self):self.assertNotEqual(p.compare(self.frame(0),self.frame(1,other=True))['relation'],'same')
 def test_no_common_visible_area_is_unknown(self):self.assertEqual(p.compare(self.frame(0,'all'),self.frame(1,'all'))['relation'],'unknown')
 def test_unknown_mask_does_not_establish_occlusion(self):
  a,b=self.frame(0),self.frame(1);a.mask_known=False
  self.assertEqual(p.compare(a,b)['reason'],'mask_unknown')
 def test_history_can_use_an_earlier_clear_real_frame(self):
  clear,blocked,current=self.frame(0),self.frame(1,'all'),self.frame(2,'left')
  result=p.resolve([clear,blocked],current,use_history=True)
  self.assertEqual(result['relation'],'same');self.assertEqual(result['reference_time_ms'],0)
 def test_adjacent_only_cannot_use_earlier_frame(self):
  result=p.resolve([self.frame(0),self.frame(1,'all')],self.frame(2,'left'),use_history=False)
  self.assertEqual(result['relation'],'unknown')
 def test_history_has_no_pixel_mosaic(self):
  a,b,c=self.frame(0,'all'),self.frame(1,'all'),self.frame(2);result=p.resolve([a,b],c,use_history=True)
  self.assertEqual(result['relation'],'unknown')
 def test_unknown_reference_does_not_prove_old_content_unchanged(self):
  self.assertEqual(p.compare(self.frame(0,'all'),self.frame(1,addition=True))['relation'],'unknown')
 def test_sources_are_not_mutated(self):
  a,b=self.frame(0,'left'),self.frame(1,'right');old=a.gray.copy();p.resolve([a],b,use_history=True);np.testing.assert_array_equal(old,a.gray)
 def test_later_clear_frame_rejoins_only_fully_occluded_pending_fragment(self):
  frames={0:self.frame(0),1:self.frame(1,'all'),2:self.frame(2,'left')}
  pages=[{'pageIndex':i+1,'memberFrameTimesMs':[i],'representativeFrameTimesMs':[i]} for i in range(3)]
  result=p.collect(pages,frames,use_history=True)
  self.assertEqual(len(result['collections']),1);self.assertEqual(result['selected'],[0,1,2])
 def test_new_question_after_occlusion_does_not_rejoin_old_page(self):
  frames={0:self.frame(0),1:self.frame(1,'all'),2:self.frame(2,other=True)}
  pages=[{'pageIndex':i+1,'memberFrameTimesMs':[i],'representativeFrameTimesMs':[i]} for i in range(3)]
  result=p.collect(pages,frames,use_history=True)
  self.assertGreater(len(result['collections']),1);self.assertEqual(result['selected'],[0,1,2])
 def test_shared_footer_cannot_prove_same_question(self):
  a,b=self.frame(0),self.frame(1,other=True)
  footer=[{'text':'permanent subscription public channel','score':1,'polygon':[[10,151],[240,151],[240,161],[10,161]]},{'text':'follow account for more learning material','score':1,'polygon':[[10,164],[260,164],[260,174],[10,174]]}]
  a.blocks+=footer;b.blocks+=footer
  self.assertNotEqual(p.compare(a,b)['relation'],'same')
 def test_question_number_change_overrides_shared_body(self):
  a,b=self.frame(0),self.frame(1)
  a.blocks.insert(0,{'text':'1. lim integral problem','score':1,'polygon':[[15,25],[200,25],[200,37],[15,37]]})
  b.blocks.insert(0,{'text':'2. lim integral problem','score':1,'polygon':[[15,25],[200,25],[200,37],[15,37]]})
  self.assertEqual(p.compare(a,b)['relation'],'new')
if __name__=='__main__':unittest.main()
