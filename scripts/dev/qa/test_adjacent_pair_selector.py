"""Check the explicitly requested experimental rule with deterministic masks."""
import unittest,numpy as np
from adjacent_pair_selector import AdjacentPairSelector
class PairRuleTests(unittest.TestCase):
    def setUp(self):self.image=np.zeros((10,10),np.uint8);self.allowed=np.ones((10,10),bool);self.none=np.zeros((10,10),bool)
    def selector(self):return AdjacentPairSelector(.02)
    def test_visible_change_kept(self):
        s=self.selector();self.assertTrue(s.observe(self.image,self.allowed,self.none,0));self.assertTrue(s.observe(np.full((10,10),255,np.uint8),self.allowed,self.none,2000))
    def test_both_person_masks_excluded(self):
        a=self.none.copy();a[:,:3]=True;b=self.none.copy();b[:,7:]=True;first=self.image.copy();first[a]=255;second=self.image.copy();second[b]=255
        s=self.selector();s.observe(first,self.allowed,a,0);self.assertFalse(s.observe(second,self.allowed,b,2000))
    def test_reveal_has_no_extra_keep(self):
        mask=self.none.copy();mask[:,:5]=True;s=self.selector();s.observe(self.image,self.allowed,mask,0);later=self.image.copy();later[:,:5]=255
        self.assertFalse(s.observe(later,self.allowed,self.none,2000));self.assertFalse(s.observe(later,self.allowed,self.none,4000))
    def test_no_historical_accumulation(self):
        s=self.selector();s.observe(self.image,self.allowed,self.none,0)
        for i in range(1,5):
            frame=self.image.copy();frame.flat[:i]=255
            self.assertFalse(s.observe(frame,self.allowed,self.none,i*2000))
    def test_no_common_pixels_no_decision(self):
        s=self.selector();s.observe(self.image,self.allowed,self.none,0);self.assertFalse(s.observe(self.image,self.allowed,~self.none,2000));self.assertEqual(s.uncertain_frames,1)
    def test_outside_roi_ignored(self):
        allowed=self.allowed.copy();allowed[:,:5]=False;s=self.selector();s.observe(self.image,allowed,self.none,0);frame=self.image.copy();frame[:,:5]=255;self.assertFalse(s.observe(frame,allowed,self.none,2000))
if __name__=='__main__':unittest.main()
