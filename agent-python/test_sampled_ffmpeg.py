"""Offline cancellation-I/O and sampled FFmpeg transport contract."""
import tempfile,subprocess,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import CancelledError
import numpy as np,av
import frame_stream as fs
class SampledFFmpegTests(unittest.TestCase):
 def fixture(self,root,name='input.ts',seconds=5):
  p=root/name
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'testsrc2=size=160x90:rate=25:duration={seconds}','-c:v','libx264','-g','250','-sc_threshold','0',str(p)],check=True)
  return p
 def test_poll_is_throttled_but_forced_boundary_check_observes_cancel(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'active-run.json').write_text('first');guard=fs.FrameRunGuard(root)
   with patch('frame_stream.time.monotonic',return_value=10),patch.object(Path,'read_bytes',autospec=True,return_value=b'first') as read:
    for _ in range(1000):guard.poll()
    self.assertEqual(read.call_count,1)
   (root/'cancel.json').write_text('{}')
   with self.assertRaises(CancelledError):guard.check()
 def test_interval_output_matches_reference_pts_and_pixels_for_all_intervals(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.fixture(Path(d))
   for seconds in (2,3,4):
    expected=list(fs.sample_frames_pyav(p,seconds));got=list(fs.sample_frames_ffmpeg(p,seconds))
    self.assertEqual([t for t,_ in got],[t for t,_ in expected])
    for (_,a),(_,b) in zip(got,expected):self.assertLess(np.abs(a.astype(float)-b).mean(),1)
 def test_early_close_reaps_process_and_watcher(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.fixture(Path(d),seconds=20);children=[];spawn=subprocess.Popen
   def tracked(*a,**kw):child=spawn(*a,**kw);children.append(child);return child
   with patch('frame_stream.subprocess.Popen',side_effect=tracked):
    frames=fs.sample_frames_ffmpeg(p,2);next(frames);frames.close()
   self.assertTrue(children);self.assertTrue(all(p.poll() is not None for p in children))
   self.assertFalse(any(t.name.startswith('sampled-ffmpeg-') for t in threading.enumerate()))
 def test_cancel_at_sample_boundary_stops_child(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.fixture(Path(d));cancel=threading.Event()
   def check():
    if cancel.is_set():raise CancelledError()
   frames=fs.sample_frames_ffmpeg(p,2,check=check);next(frames);cancel.set()
   with self.assertRaises(CancelledError):next(frames)
   frames.close()
 def test_decoder_failure_is_not_treated_as_empty_success(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.fixture(Path(d))
   with patch('frame_stream.subprocess.Popen',side_effect=OSError('missing ffmpeg')):
    with self.assertRaises(OSError):list(fs.sample_frames_ffmpeg(p))
 def test_vfr_real_pts_keep_grid_alignment_without_duplicate_frames(self):
  from fractions import Fraction
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'vfr.mp4'
   with av.open(str(p),'w') as out:
    stream=out.add_stream('libx264',rate=1000);stream.width=160;stream.height=90;stream.pix_fmt='yuv420p';stream.options={'bf':'0'}
    stream.time_base=Fraction(1,1000)
    for i,t in enumerate((21,1999,2041,3500,4007,6001)):
     f=av.VideoFrame.from_ndarray(np.full((90,160,3),i*35,np.uint8),format='bgr24');f.pts=t;f.time_base=Fraction(1,1000)
     for packet in stream.encode(f):out.mux(packet)
    for packet in stream.encode():out.mux(packet)
   a=list(fs.sample_frames_pyav(p));b=list(fs.sample_frames_ffmpeg(p))
   self.assertEqual([t for t,_ in a],[t for t,_ in b]);self.assertGreater(len(b),2)
 def test_nonzero_av_origin_matches_source_timestamps(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'av.ts'
   subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=25:duration=5','-f','lavfi','-i','sine=frequency=400:duration=5','-c:v','libx264','-c:a','aac','-f','mpegts',str(p)],check=True)
   a=list(fs.sample_frames_pyav(p));b=list(fs.sample_frames_ffmpeg(p));self.assertEqual([t for t,_ in a],[t for t,_ in b]);self.assertNotEqual(a[0][0],0)
 def test_watchdog_cancels_blocked_output_read(self):
  import sys
  with tempfile.TemporaryDirectory() as d:
   p=self.fixture(Path(d));cancel=threading.Event();spawn=subprocess.Popen;children=[]
   def blocked(*a,**kw):
    child=spawn([sys.executable,'-c','import time; time.sleep(30)'],stdout=subprocess.PIPE,stderr=subprocess.PIPE);children.append(child);return child
   def check():
    if cancel.is_set():raise CancelledError()
   timer=threading.Timer(.2,cancel.set);timer.start()
   try:
    with patch('frame_stream.subprocess.Popen',side_effect=blocked):
     started=time.monotonic()
     with self.assertRaises(CancelledError):list(fs.sample_frames_ffmpeg(p,check=check))
     self.assertLess(time.monotonic()-started,3)
   finally:timer.cancel()
   self.assertTrue(all(p.poll() is not None for p in children))
 def test_decoder_exit_code_and_classified_error_log_do_not_leak_stderr(self):
  import os,sys
  from model_diagnostics import close_logs
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=self.fixture(root);spawn=subprocess.Popen
   def bad(*a,**kw):return spawn([sys.executable,'-c',"import sys;sys.stderr.write('Invalid data found PRIVATE_PATH_AND_CONTENT');sys.exit(7)"],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   try:
    with patch.dict(os.environ,{'MODEL_LOG_DIR':str(root/'logs')}),patch('frame_stream.subprocess.Popen',side_effect=bad):
     with self.assertRaises(Exception):list(fs.sample_frames_ffmpeg(p))
    text=(root/'logs/model-events.jsonl').read_text();self.assertIn('video_input_invalid',text);self.assertIn('"exit_code":7',text);self.assertNotIn('PRIVATE_PATH_AND_CONTENT',text)
   finally:close_logs()
if __name__=='__main__':unittest.main()
