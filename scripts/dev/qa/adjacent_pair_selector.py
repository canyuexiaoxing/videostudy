"""Experimental adjacent-pair person exclusion. QA only, not a production selector."""
import numpy as np
class AdjacentPairSelector:
    def __init__(self,threshold,max_wait_ms=30000):
        self.threshold=threshold;self.previous=None;self.previous_visible=None
        self.pending_time=None;self.preserve_time=None;self.uncertain_frames=0;self.reveal_frames=0
    def observe(self,frame,allowed,person,time_ms):
        frame=np.asarray(frame);visible=np.asarray(allowed,dtype=bool)&~np.asarray(person,dtype=bool)
        if self.previous is None:keep=True
        else:
            common=visible & self.previous_visible
            if common.any():
                changed=(np.abs(frame.astype(np.int16)-self.previous.astype(np.int16))>25)&common
                keep=float(changed.sum())/int(common.sum())>self.threshold
            else:
                self.uncertain_frames+=1;keep=False
        self.previous=frame.copy();self.previous_visible=visible.copy()
        return bool(keep)
