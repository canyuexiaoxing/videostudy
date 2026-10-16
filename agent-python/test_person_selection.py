import unittest,os,tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from person_selection import VisibilitySelector,selection_context,settings

class PersonSelectionTests(unittest.TestCase):
 def setUp(self):
  self.frame=np.full((60,100),255,np.uint8);self.allowed=np.ones_like(self.frame,dtype=bool)
 def mask(self,x):
  m=np.zeros_like(self.allowed);m[:,x:x+20]=True;return m
 def test_person_motion_does_not_create_new_board_content(self):
  s=VisibilitySelector(.02);self.assertTrue(s.observe(self.frame,self.allowed,self.mask(0),0))
  # First reveal of initially unknown pixels must be retained, then motion across known board is ignored.
  self.assertTrue(s.observe(self.frame,self.allowed,self.mask(60),2000))
  for t,x in [(4000,20),(6000,40),(8000,60)]:self.assertFalse(s.observe(self.frame,self.allowed,self.mask(x),t))
 def test_writing_behind_person_is_detected_when_revealed(self):
  s=VisibilitySelector(.02);s.observe(self.frame,self.allowed,self.mask(40),0)
  written=self.frame.copy();written[15:35,40:55]=0
  self.assertFalse(s.observe(written,self.allowed,self.mask(40),2000))
  self.assertTrue(s.observe(written,self.allowed,self.mask(70),4000))
 def test_erasing_and_replacement_keep_versions(self):
  s=VisibilitySelector(.02);old=self.frame.copy();old[10:30,10:30]=0
  self.assertTrue(s.observe(old,self.allowed,self.mask(70),0))
  self.assertTrue(s.observe(self.frame,self.allowed,self.mask(70),2000))
  changed=self.frame.copy();changed[30:50,20:40]=0
  self.assertTrue(s.observe(changed,self.allowed,self.mask(70),4000))
 def test_no_common_visible_pixels_is_unknown_not_same(self):
  s=VisibilitySelector(.02);left=np.zeros_like(self.allowed);left[:,:50]=True
  s.observe(self.frame,self.allowed,~left,0)
  self.assertTrue(s.observe(self.frame,self.allowed,left,2000))
 def test_slow_writing_accumulates_and_is_kept_at_bounded_interval(self):
  s=VisibilitySelector(.02);s.observe(self.frame,self.allowed,self.mask(70),0)
  f=self.frame.copy();f[10:12,10:20]=0
  self.assertFalse(s.observe(f,self.allowed,self.mask(70),2000))
  self.assertTrue(s.observe(f,self.allowed,self.mask(70),30000))
 def test_fully_hidden_board_gets_bounded_conservative_samples(self):
  s=VisibilitySelector(.02);hidden=np.ones_like(self.allowed)
  self.assertTrue(s.observe(self.frame,self.allowed,hidden,0))
  self.assertFalse(s.observe(self.frame,self.allowed,hidden,2000))
  self.assertTrue(s.observe(self.frame,self.allowed,hidden,30000))
 def test_manual_region_change_resets_comparison(self):
  s=VisibilitySelector(.02);s.observe(self.frame,self.allowed,self.mask(70),0)
  allowed=self.allowed.copy();allowed[:,:50]=False
  self.assertTrue(s.observe(self.frame,allowed,self.mask(70),2000))
 def test_inputs_are_not_painted_or_modified(self):
  s=VisibilitySelector(.02);original=self.frame.copy();s.observe(self.frame,self.allowed,self.mask(70),0)
  np.testing.assert_array_equal(self.frame,original)
 def test_disabled_mode_preserves_legacy_cache_identity_and_no_runtime_import(self):
  with patch.dict(os.environ,{'PERSON_SEGMENTATION':'off'}):self.assertEqual(selection_context(),{})
 def test_mode_and_model_revision_change_cache_identity(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'model.pt';p.write_bytes(b'one')
   with patch.dict(os.environ,{'PERSON_SEGMENTATION':'cpu','PERSON_MODEL_PATH':str(p)}):
    a=selection_context();p.write_bytes(b'two-more');self.assertNotEqual(a,selection_context())
   with patch.dict(os.environ,{'PERSON_SEGMENTATION':'invalid'}):
    with self.assertRaises(ValueError):settings()

 def test_worker_lease_reuses_model_but_retires_failed_worker(self):
  from person_selection import PersonMaskLease,shutdown_person_worker
  from unittest.mock import Mock
  worker=Mock();worker.__enter__=Mock(return_value=worker);worker.alive.return_value=True
  shutdown_person_worker();self.addCleanup(shutdown_person_worker)
  with patch.dict(os.environ,{'PERSON_SEGMENTATION':'cpu'}),patch('person_selection.PersonMaskProcess',return_value=worker) as factory:
   with PersonMaskLease() as first:pass
   with PersonMaskLease() as second:pass
   self.assertEqual(factory.call_count,1)
   second=PersonMaskLease().__enter__();second.invalidate()
   with PersonMaskLease():pass
   self.assertEqual(factory.call_count,2)

 def test_small_unsaved_writing_is_preserved_before_large_erase(self):
  s=VisibilitySelector(.02);none=np.zeros_like(self.allowed)
  s.observe(self.frame,self.allowed,none,0)
  partial=self.frame.copy();partial[10:15,10:28]=0
  self.assertFalse(s.observe(partial,self.allowed,none,2000))
  replacement=self.frame.copy();replacement[:40,:80]=0
  self.assertTrue(s.observe(replacement,self.allowed,none,4000))
  self.assertEqual(s.preserve_time,2000)
