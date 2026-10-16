import os,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from person_selection import AdjacentPairSelector,settings,selection_context
class AdjacentSelectionTests(unittest.TestCase):
 def setUp(self):self.f=np.zeros((10,10),np.uint8);self.all=np.ones((10,10),bool);self.none=~self.all
 def test_both_people_excluded_and_reveal_does_not_trigger(self):
  a=self.none.copy();a[:,:3]=True;b=self.none.copy();b[:,7:]=True
  before=self.f.copy();before[a]=255;after=self.f.copy();after[b]=255
  s=AdjacentPairSelector(.02);self.assertTrue(s.observe(before,self.all,a,0));self.assertFalse(s.observe(after,self.all,b,2000))
  revealed=after.copy();revealed[:,:3]=255;self.assertTrue(s.observe(revealed,self.all,self.none,4000))
  s=AdjacentPairSelector(.02);s.observe(self.f,self.all,a,0);revealed=self.f.copy();revealed[a]=255;self.assertFalse(s.observe(revealed,self.all,self.none,2000))
 def test_no_accumulation_and_no_common_pixels(self):
  s=AdjacentPairSelector(.02);s.observe(self.f,self.all,self.none,0)
  for i in range(1,5):
   f=self.f.copy();f.flat[:i]=255;self.assertFalse(s.observe(f,self.all,self.none,i*2000))
  self.assertFalse(s.observe(self.f,self.all,self.all,10000));self.assertEqual(s.uncertain_frames,1)
 def test_per_request_modes_do_not_change_environment_or_cache_other_jobs(self):
  with patch.dict(os.environ,{'PERSON_SEGMENTATION':'cpu'}):
   legacy=selection_context();self.assertEqual(settings('adjacent')['mode'],'cuda');self.assertEqual(settings('adjacent')['strategy'],'adjacent')
   self.assertEqual(selection_context('off'),{});self.assertNotEqual(legacy,selection_context('adjacent'));self.assertEqual(selection_context(),legacy)
   self.assertEqual(os.environ['PERSON_SEGMENTATION'],'cpu')
   with self.assertRaises(ValueError):settings('other')
 def test_request_reaches_analysis_api(self):
  from app import TranscribeRequest,analyze
  from pydantic import ValidationError
  with self.assertRaises(ValidationError):TranscribeRequest(fileId='x',personSelectionMode='cpu')
  with patch('app.analyze_file',return_value={}) as run:
   analyze(TranscribeRequest(fileId='x',personSelectionMode='adjacent',mindMapMode='direct'))
  self.assertEqual(run.call_args.kwargs['person_selection_mode'],'adjacent')
 def test_explicit_off_skips_model_even_if_server_enables_it(self):
  import cv2
  from visual_evidence import _candidate_times
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'constant.avi';writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),2,(320,180))
   for _ in range(8):writer.write(np.full((180,320,3),255,np.uint8))
   writer.release()
   with patch.dict(os.environ,{'PERSON_SEGMENTATION':'cuda'}),patch('person_selection.PersonMaskProcess',side_effect=AssertionError('must not run')):
    self.assertEqual(_candidate_times(path,person_selection_mode='off'),[2000])
 def test_explicit_adjacent_reaches_gpu_sampler_even_when_server_is_off(self):
  import cv2
  from visual_evidence import _candidate_times
  modes=[]
  class FakeLease:
   device='cuda'
   def __init__(self,mode):modes.append(mode)
   def __enter__(self):return self
   def close(self):pass
   def predict(self,image):return (image[:,:,2]>150)&(image[:,:,0]<100)&(image[:,:,1]<100)
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'moving.avi';writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),2,(320,180))
   for i in range(24):
    frame=np.full((180,320,3),255,np.uint8);x=[10,80,150,220][(i//4)%4];cv2.rectangle(frame,(x,30),(x+50,165),(0,0,255),-1);writer.write(frame)
   writer.release()
   with patch.dict(os.environ,{'PERSON_SEGMENTATION':'off'}),patch('person_selection.PersonMaskLease',FakeLease):
    self.assertEqual(_candidate_times(path,person_selection_mode='adjacent'),[0,10000])
   self.assertEqual(modes,['adjacent'])
 def test_shared_worker_resets_mode_on_every_binding(self):
  from unittest.mock import Mock
  from visual_evidence import _serve_visual_requests
  requests=[]
  for mode in ['adjacent','off',None]:
   requests.extend([{'op':'bind','mediaPath':'media','keyframePath':None,'pageChangeFraction':.02,'sampleSeconds':2,'personSelectionMode':mode},{'op':'analyze'}])
  connection=Mock();connection.recv.side_effect=[*requests,None]
  with patch('visual_evidence.analyze_visuals',return_value=[]) as analyze:
   _serve_visual_requests(connection)
  self.assertEqual([call.kwargs['person_selection_mode'] for call in analyze.call_args_list],['adjacent','off',None])
if __name__=='__main__':unittest.main()
