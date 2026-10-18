"""YOLO-only grouping and pending-tail regressions with deterministic masks."""
import tempfile,unittest,copy,os
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
from person_visibility import save_visibility
from slide_grouping import group_pages,IncrementalPageGrouper
class YoloGroupingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
 def image(self,t,occlusion=None,question=1):
  im=np.full((180,320,3),230,np.uint8);items=[('unit title',18),('example '+str(question)+' fixed long problem statement',50),('given fixed x and y condition',78),('calculation alpha equals 100',118),('final relation beta equals 200',150)];blocks=[]
  mask=np.zeros((180,320),bool)
  if occlusion=='partial':mask[96:174,4:315]=True
  if occlusion=='full':mask[:]=True
  if occlusion=='top':mask[:65]=True
  for text,y in items:
   cv2.putText(im,text,(8,y),cv2.FONT_HERSHEY_SIMPLEX,.38,(0,0,0),1);(w,h),_=cv2.getTextSize(text,cv2.FONT_HERSHEY_SIMPLEX,.38,1)
   x2=min(319,8+w);y1=y-h-1;y2=y+2
   if not mask[y1:y2,8:x2].any():blocks.append({'text':text,'score':.99,'polygon':[[8,y1],[x2,y1],[x2,y2],[8,y2]]})
  im[mask]=(90,110,140);cv2.imwrite(str(self.root/f'{t}.jpg'),im);save_visibility(self.root,t,mask,(320,180));return {'frameTimeMs':t,'ocrBlocks':blocks}
 def group(self,frames,mode='adjacent'):
  return group_pages(frames,self.root,[],ask_json=lambda _:{'samePage':False},person_selection_mode=mode)
 def test_occluded_text_does_not_count_as_content_loss(self):
  a,b=self.image(0),self.image(2000,'partial');pages,_=self.group([a,b]);self.assertEqual(len(pages),1);self.assertEqual(pages[0]['memberFrameTimesMs'],[0,2000]);self.assertTrue({0,2000}<=set(pages[0]['representativeFrameTimesMs']))
 def test_explicit_off_is_exact_old_behavior_even_with_masks(self):
  frames=[self.image(0),self.image(2000,'partial')];old=group_pages(frames,self.root,[],ask_json=lambda _:{'samePage':False})
  with patch.dict(os.environ,{'PERSON_SEGMENTATION':'cuda'}):self.assertEqual(self.group(frames,'off'),old)
  self.assertEqual(len(old[0]),2)
 def test_full_occlusion_waits_for_clear_same_page(self):
  frames=[self.image(0),self.image(2000,'full'),self.image(4000)];pages,_=self.group(frames);self.assertEqual(len(pages),1);self.assertEqual(pages[0]['memberFrameTimesMs'],[0,2000,4000])
 def test_unresolved_end_splits_without_claiming_same_page(self):
  pages,_=self.group([self.image(0),self.image(2000,'full')]);self.assertEqual(len(pages),2)
 def test_changed_question_after_occlusion_is_not_joined(self):
  pages,_=self.group([self.image(0),self.image(2000,'full'),self.image(4000,question=2)]);self.assertGreater(len(pages),1)
 def test_invalid_masks_restore_original_grouping(self):
  frames=[self.image(0),self.image(2000,'partial')];(self.root/'.person-masks/2000.json').write_text('{}');self.assertEqual(self.group(frames),self.group(frames,'off'))
 def test_tiny_visible_region_cannot_prove_same_page(self):
  pages,_=self.group([self.image(0),self.image(2000,'full')]);self.assertNotEqual(len(pages),1)
 def test_incremental_does_not_publish_occluded_tail_early(self):
  frames=[self.image(0),self.image(2000,'full'),self.image(4000)];g=IncrementalPageGrouper(self.root,person_selection_mode='adjacent')
  self.assertEqual(g.add(frames[0]),[]);self.assertEqual(g.add(frames[1]),[]);self.assertEqual(g.add(frames[2]),[]);pages=g.finish();self.assertEqual(len(pages),1)
 def test_original_ocr_sources_not_filtered_out_of_result(self):
  frames=[self.image(0),self.image(2000,'partial')];saved=copy.deepcopy(frames);pages,_=self.group(frames);self.assertEqual(frames,saved);self.assertTrue(any(x['text']=='final relation beta equals 200' for x in pages[0]['ocrLines']))
 def test_original_conservative_representatives_survive_group_correction(self):
  frames=[self.image(0),self.image(2000,'partial'),self.image(4000),self.image(6000,'partial'),self.image(8000)]
  old,_=self.group(frames,'off');new,_=self.group(frames)
  before={t for p in old for t in p['representativeFrameTimesMs']};after={t for p in new for t in p['representativeFrameTimesMs']}
  self.assertTrue(before<=after)
 def test_long_unresolved_occlusion_is_bounded_and_keeps_every_frame(self):
  frames=[self.image(0)]+[self.image(i*2000,'full') for i in range(1,12)]
  pages,_=self.group(frames);self.assertGreater(len(pages),1);self.assertEqual(sorted(t for p in pages for t in p['memberFrameTimesMs']),[f['frameTimeMs'] for f in frames])
 def test_unresolved_occlusion_keeps_original_groups_instead_of_one_per_image(self):
  frames=[self.image(0)]+[self.image(i*2000,'full') for i in range(1,5)]
  old,_=self.group(frames,'off');new,_=self.group(frames)
  self.assertEqual(len(new),len(old));self.assertEqual([p['memberFrameTimesMs'] for p in new],[p['memberFrameTimesMs'] for p in old])
 def test_pending_limit_does_not_split_a_baseline_group_into_chunks(self):
  frames=[self.image(0)]+[self.image(i*2000,'full') for i in range(1,14)]
  old,_=self.group(frames,'off');new,_=self.group(frames)
  self.assertEqual([p['memberFrameTimesMs'] for p in new],[p['memberFrameTimesMs'] for p in old])
 def test_old_ocr_on_moving_person_does_not_look_like_erased_page_text(self):
  old=self.image(0,'partial');current=self.image(2000)
  for i in range(8):
   old['ocrBlocks'].append({'text':'person shirt false OCR line '+str(i)+' unrelated long noisy recognition','score':.99,'polygon':[[10,105],[300,105],[300,160],[10,160]]})
  baseline,_=self.group([old,current],'off');self.assertEqual(len(baseline),2)
  pages,_=self.group([old,current]);self.assertEqual(len(pages),1);self.assertEqual(pages[0]['memberFrameTimesMs'],[0,2000])
 def test_question_number_read_on_person_cannot_force_new_page(self):
  old=self.image(0,'top');current=self.image(2000)
  old['ocrBlocks'].append({'text':'example 99 false person text','score':.99,'polygon':[[8,20],[300,20],[300,55],[8,55]]})
  pages,_=self.group([old,current]);self.assertEqual(len(pages),1)
if __name__=='__main__':unittest.main()
