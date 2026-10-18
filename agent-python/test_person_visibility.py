"""Authenticated person-mask sidecars; only YOLO-enabled grouping consumes them."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
from person_visibility import save_visibility,load_visibility,grouping_context
class VisibilityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.mask=np.zeros((180,320),bool);self.mask[40:100,20:80]=True
  cv2.imwrite(str(self.root/'2000.jpg'),np.full((180,320,3),180,np.uint8))
 def test_exact_timestamp_and_image_bound_roundtrip(self):
  save_visibility(self.root,2000,self.mask,(320,180));np.testing.assert_array_equal(load_visibility(self.root,2000,(320,180)),self.mask);self.assertIsNone(load_visibility(self.root,2001,(320,180)))
 def test_changed_jpg_rejects_old_mask(self):
  save_visibility(self.root,2000,self.mask,(320,180));cv2.imwrite(str(self.root/'2000.jpg'),np.zeros((180,320,3),np.uint8));self.assertIsNone(load_visibility(self.root,2000,(320,180)))
 def test_wrong_dimensions_rejected(self):
  save_visibility(self.root,2000,self.mask,(320,180));self.assertIsNone(load_visibility(self.root,2000,(640,360)))
 def test_letterbox_padding_removed_before_grouping_projection(self):
  cv2.imwrite(str(self.root/'2000.jpg'),np.full((480,640,3),180,np.uint8));mask=np.zeros((180,320),bool);mask[:,:40]=True
  save_visibility(self.root,2000,mask,(640,480));self.assertFalse(load_visibility(self.root,2000,(640,480)).any())
 def test_missing_or_invalid_sidecar_falls_back(self):
  self.assertIsNone(load_visibility(self.root,2000,(320,180)));save_visibility(self.root,2000,self.mask,(320,180));(self.root/'.person-masks/2000.json').write_text('{}');self.assertIsNone(load_visibility(self.root,2000,(320,180)))
 def test_off_does_not_read_any_files_or_change_cache_identity(self):
  with patch('pathlib.Path.read_bytes',side_effect=AssertionError('off touched mask')):self.assertEqual(grouping_context(self.root,[{'frameTimeMs':2000}],'off'),{})
 def test_enabled_cache_identity_changes_with_mask(self):
  frames=[{'frameTimeMs':2000}];save_visibility(self.root,2000,self.mask,(320,180));a=grouping_context(self.root,frames,'adjacent');save_visibility(self.root,2000,np.zeros_like(self.mask),(320,180));self.assertNotEqual(a,grouping_context(self.root,frames,'adjacent'))
 def test_unavailable_marker_invalidates_prior_mask(self):
  save_visibility(self.root,2000,self.mask,(320,180));save_visibility(self.root,2000,None,(320,180));self.assertIsNone(load_visibility(self.root,2000,(320,180)))
 def test_cached_exact_image_mask_survives_new_analysis_run(self):
  (self.root/'.analysis').mkdir();p=self.root/'.analysis/active-run.json';p.write_text('{"runId":"old"}')
  save_visibility(self.root,2000,self.mask,(320,180));context=grouping_context(self.root,[{'frameTimeMs':2000}],'adjacent')
  p.write_text('{"runId":"new"}');self.assertIsNotNone(load_visibility(self.root,2000,(320,180)));self.assertEqual(context,grouping_context(self.root,[{'frameTimeMs':2000}],'adjacent'))
if __name__=='__main__':unittest.main()
