"""Same-frame sidecar persistence with deterministic detector; never loads YOLO."""
import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import CancelledError
import cv2,numpy as np
from visual_evidence import analyze_visuals
from person_visibility import load_visibility,save_visibility
class CaptureTests(unittest.TestCase):
 def run_capture(self,root,mode,fail=False):
  (root/'media').write_bytes(b'fixture');source=[]
  for i in range(4):
   image=np.full((180,320,3),255,np.uint8);image[20:150,5+i*25:45+i*25]=(0,0,255)
   if i>=2:image[20:100,180:260]=0
   source.append((i*2000,image))
  calls=[]
  class Lease:
   device='cuda'
   def __init__(self,*_):pass
   def __enter__(self):return self
   def close(self):pass
   def invalidate(self):pass
   def predict(self,image):
    calls.append(image.copy())
    if fail:raise RuntimeError('detector_failed')
    return (image[:,:,2]>150)&(image[:,:,0]<100)&(image[:,:,1]<100)
  with patch('visual_evidence._has_video',return_value=True),patch('frame_stream.sample_frames',return_value=iter(source)),patch('person_selection.PersonMaskLease',Lease):
   result=analyze_visuals(root/'media',keyframe_dir=root,recognize=lambda _:[],person_selection_mode=mode)
  return source,result,calls
 def test_selected_frame_uses_exact_existing_detection_before_ocr(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source,frames,calls=self.run_capture(root,'adjacent');self.assertEqual(len(calls),len(source))
   original=dict(source)
   for f in frames:
    t=f['frameTimeMs'];expected=(original[t][:,:,2]>150)&(original[t][:,:,0]<100)&(original[t][:,:,1]<100)
    np.testing.assert_array_equal(load_visibility(root,t,(320,180)),expected)
   self.assertEqual(len(list((root/'.person-masks').glob('*.json'))),len(frames))
 def test_off_writes_no_masks_and_runs_no_detector(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);_,_,calls=self.run_capture(root,'off');self.assertEqual(calls,[]);self.assertFalse((root/'.person-masks').exists())
 def test_detector_failure_invalidates_old_mask(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);cv2.imwrite(str(root/'0.jpg'),np.zeros((180,320,3),np.uint8));save_visibility(root,0,np.ones((180,320),bool),(320,180))
   _,frames,_=self.run_capture(root,'adjacent',True)
   self.assertTrue(frames);self.assertIsNone(load_visibility(root,0,(320,180)))
 def test_cancelled_write_never_publishes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);cv2.imwrite(str(root/'0.jpg'),np.zeros((180,320,3),np.uint8))
   with self.assertRaises(CancelledError):save_visibility(root,0,np.ones((180,320),bool),(320,180),_check=lambda:(_ for _ in ()).throw(CancelledError()))
   self.assertFalse((root/'.person-masks/0.json').exists())
if __name__=='__main__':unittest.main()
