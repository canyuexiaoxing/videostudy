"""Cancellation checks shared by video extraction and page grouping."""
from concurrent.futures import CancelledError
from pathlib import Path
import threading,time

class FrameRunGuard:
 def __init__(self,root):
  self.root=Path(root) if root is not None else None
  p=self.root/'active-run.json' if self.root else None
  self.initial=p.read_bytes() if p and p.is_file() else None
  self.lock=threading.Lock();self.last_poll=None
 def poll(self):
  self.check(force=False)
 def check(self,*,force=True):
  if self.root is None:return
  with self.lock:
   now=time.monotonic()
   if not force and self.last_poll is not None and now-self.last_poll<.2:return
   if (self.root/'cancel.json').exists():raise CancelledError('analysis_cancelled')
   try:current=(self.root/'active-run.json').read_bytes()
   except FileNotFoundError:current=None
   except OSError:raise CancelledError('analysis_cancelled')
   if current!=self.initial:raise CancelledError('analysis_cancelled')
   self.last_poll=now
