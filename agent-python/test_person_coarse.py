import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
from visual_evidence import _candidate_times
class FakePerson:
 device='cpu'
 def alive(self):return True
 def __enter__(self):return self
 def close(self):pass
 def predict(self,image):return (image[:,:,2]>150)&(image[:,:,0]<100)&(image[:,:,1]<100)
class PersonCoarseIntegrationTests(unittest.TestCase):
 def tearDown(self):
  from person_selection import shutdown_person_worker
  shutdown_person_worker()
 def test_rgb_sampler_uses_masks_to_suppress_person_motion(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'moving.avi';w=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'MJPG'),2,(320,180))
   for i in range(24):
    f=np.full((180,320,3),255,np.uint8);x=[10,80,150,220][(i//4)%4];cv2.rectangle(f,(x,30),(x+50,165),(0,0,255),-1);w.write(f)
   w.release()
   with patch.dict(os.environ,{'PERSON_SEGMENTATION':'off'}):legacy=_candidate_times(p)
   with patch.dict(os.environ,{'PERSON_SEGMENTATION':'cpu'}),patch('person_selection.PersonMaskProcess',FakePerson):improved=_candidate_times(p)
   self.assertGreater(len(legacy),len(improved));self.assertEqual(improved[0],0);self.assertEqual(improved[-1],10000)
 def test_missing_person_runtime_falls_back_without_losing_last_frame(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'constant.avi';w=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'MJPG'),2,(320,180))
   for i in range(8):w.write(np.full((180,320,3),255,np.uint8))
   w.release()
   with patch.dict(os.environ,{'PERSON_SEGMENTATION':'cuda','PERSON_PYTHON':str(Path(d)/'missing')}):
    self.assertEqual(_candidate_times(p)[-1],2000)

 def test_timed_manual_region_is_respected_with_rgb_person_masks(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'outside.avi';w=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'MJPG'),2,(320,180))
   for i in range(24):
    f=np.full((180,320,3),255,np.uint8);x=210+(i//4)%2*20;cv2.rectangle(f,(x,30),(x+50,165),(0,0,255),-1);w.write(f)
   w.release();regions={'analysisRegion':{'nodes':[{'timeMs':0,'region':{'x':0,'y':0,'width':.5,'height':1}}]},'ignoredRegion':None}
   with patch.dict(os.environ,{'PERSON_SEGMENTATION':'cpu'}),patch('person_selection.PersonMaskProcess',FakePerson):
    self.assertEqual(_candidate_times(p,ignore_region=regions),[0,10000])
 def test_cancelled_task_does_not_start_a_model(self):
  from concurrent.futures import CancelledError
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'cancelled';marker=Path(d)/p.name/'.analysis/cancel.json';marker.parent.mkdir(parents=True);marker.write_text('{}')
   with patch.dict(os.environ,{'PERSON_SEGMENTATION':'cpu','KEYFRAME_DIR':d}),patch('person_selection.PersonMaskProcess',side_effect=AssertionError('should not start')):
    with self.assertRaises(CancelledError):_candidate_times(p)

 def test_cancelling_active_scan_retires_person_process(self):
  from concurrent.futures import CancelledError
  from unittest.mock import Mock
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'active.avi';w=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'MJPG'),2,(320,180))
   for i in range(8):w.write(np.full((180,320,3),255,np.uint8))
   w.release()
   # Put cancellation state outside the media path itself.
   cancel_root=Path(d)/'keyframes';marker=cancel_root/p.name/'.analysis/cancel.json';marker.parent.mkdir(parents=True)
   worker=FakePerson();worker.close=Mock();original=worker.predict
   def cancel_after_first(image):marker.write_text('{}');return original(image)
   worker.predict=cancel_after_first
   with patch.dict(os.environ,{'PERSON_SEGMENTATION':'cpu','KEYFRAME_DIR':str(cancel_root)}),patch('person_selection.PersonMaskProcess',return_value=worker):
    with self.assertRaises(CancelledError):_candidate_times(p)
    worker.close.assert_called_once()

 def test_small_writing_before_erase_keeps_original_timestamp(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'erase.avi';w=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'MJPG'),2,(320,180))
   for i in range(12):
    f=np.full((180,320,3),255,np.uint8)
    if 4<=i<8:cv2.rectangle(f,(10,10),(40,35),(0,0,0),-1)
    if i>=8:f[:140,:250]=0
    w.write(f)
   w.release()
   with patch.dict(os.environ,{'PERSON_SEGMENTATION':'cpu'}),patch('person_selection.PersonMaskProcess',FakePerson):self.assertIn(2000,_candidate_times(p))

 def test_last_clear_unsaved_board_is_kept_if_video_ends_hidden(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'hidden-end.avi';w=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'MJPG'),2,(320,180))
   for i in range(12):
    f=np.full((180,320,3),255,np.uint8)
    if 4<=i<8:cv2.rectangle(f,(10,10),(40,35),(0,0,0),-1)
    if i>=8:f[:]=(0,0,255)
    w.write(f)
   w.release()
   with patch.dict(os.environ,{'PERSON_SEGMENTATION':'cpu'}),patch('person_selection.PersonMaskProcess',FakePerson):self.assertIn(2000,_candidate_times(p))
