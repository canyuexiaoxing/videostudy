"""Offline same-frame pipeline and long-GOP timestamp regressions."""
import tempfile,threading,subprocess,unittest,time
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import CancelledError
import numpy as np
import cv2
from frame_stream import sample_frames,accurate_frames
from visual_evidence import analyze_visuals

class FrameStreamTests(unittest.TestCase):
 def samples(self):
  return iter([(21,np.full((90,160,3),v,np.uint8)) for v in []])
 def test_sampling_has_actual_pts_not_nominal_interval(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'offset.ts'
   subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=25:duration=5','-c:v','libx264','-g','250','-sc_threshold','0','-f','mpegts',str(p)],check=True)
   frames=list(sample_frames(p,2))
   self.assertEqual(len(frames),3)
   self.assertGreaterEqual(frames[0][0],0);self.assertLess(frames[0][0],45)
   self.assertTrue(all(abs(t-i*2000)<=45 for i,(t,_) in enumerate(frames)))
   self.assertEqual(frames[0][1].shape,(90,160,3))
 def test_saving_and_ocr_start_before_sampling_finishes_with_same_original(self):
  first_ocr=threading.Event()
  def source(*args,**kwargs):
   yield 21,np.full((90,160,3),20,np.uint8)
   yield 2021,np.full((90,160,3),100,np.uint8)
   self.assertTrue(first_ocr.wait(3),'OCR waited for whole video')
   yield 4021,np.full((90,160,3),200,np.uint8)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);media=root/'media';media.write_bytes(b'fixture');seen=[]
   def ocr(image):first_ocr.set();return [{'text':str(round(float(image.mean())))}]
   def ready(item):
    frame=cv2.imread(str(root/f"{item['frameTimeMs']}.jpg"));self.assertIsNotNone(frame)
    self.assertEqual(round(float(frame.mean())),int(item['ocrBlocks'][0]['text']));seen.append(item)
   with patch('visual_evidence._has_video',return_value=True),patch('frame_stream.sample_frames',side_effect=source),patch('visual_evidence._frames_at',side_effect=AssertionError('second decode used')):
    result=analyze_visuals(media,keyframe_dir=root,recognize=ocr,on_frame=ready)
   self.assertEqual(result,seen);self.assertEqual([f['frameTimeMs'] for f in result],[21,2021,4021])
   self.assertEqual(len(list(root.glob('*.jpg'))),3)
 def test_save_error_reaches_consumer_and_threads_exit(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'media';p.write_bytes(b'x')
   frames=[(i*2000,np.full((30,40,3),(i%2)*200,np.uint8)) for i in range(20)]
   with patch('visual_evidence._has_video',return_value=True),patch('frame_stream.sample_frames',return_value=iter(frames)),patch('visual_evidence._save_keyframe',side_effect=OSError('disk full')):
    with self.assertRaises(OSError):analyze_visuals(p,keyframe_dir=root,recognize=lambda _:[])
   self.assertFalse(any(t.name.startswith('same-frame-') for t in threading.enumerate()))
 def test_ocr_error_stops_producer_and_saver(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'media';p.write_bytes(b'x')
   frames=((i*2000,np.full((30,40,3),(i%2)*200,np.uint8)) for i in range(100))
   with patch('visual_evidence._has_video',return_value=True),patch('frame_stream.sample_frames',return_value=frames):
    with self.assertRaisesRegex(RuntimeError,'OCR failed'):analyze_visuals(p,keyframe_dir=root,recognize=lambda _:(_ for _ in ()).throw(RuntimeError('OCR failed')))
   self.assertFalse(any(t.name.startswith('same-frame-') for t in threading.enumerate()))
 def test_cancel_stops_callbacks_and_threads(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'media';p.write_bytes(b'x');seen=[]
   def ready(item):
    seen.append(item);(root/'.analysis').mkdir(exist_ok=True);(root/'.analysis/cancel.json').write_text('{}')
   frames=((i*2000,np.full((30,40,3),(i%2)*200,np.uint8)) for i in range(100))
   with patch('visual_evidence._has_video',return_value=True),patch('frame_stream.sample_frames',return_value=frames):
    with self.assertRaises(CancelledError):analyze_visuals(p,keyframe_dir=root,recognize=lambda _:[],on_frame=ready)
   self.assertEqual(len(seen),1);self.assertFalse(any(t.name.startswith('same-frame-') for t in threading.enumerate()))
 def test_long_gop_capture_matches_sequential_decoding_and_does_not_repeat_keyframe(self):
  import av
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'long-gop.ts'
   subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=25:duration=14','-c:v','libx264','-g','250','-sc_threshold','0','-f','mpegts',str(p)],check=True)
   frames=list(accurate_frames(p,[2021,4021,6021]));self.assertEqual([t for t,_ in frames],[2000,4000,6000])
   expected=[]
   with av.open(str(p)) as c:
    origin=c.start_time/av.time_base
    for frame in c.decode(video=0):
     ms=round((float(frame.pts*frame.time_base)-origin)*1000)
     if ms in (2000,4000,6000):expected.append(frame.to_ndarray(format='bgr24'))
   self.assertEqual(len(expected),3)
   for (_,image),other in zip(frames,expected):self.assertTrue(np.array_equal(image,other))
   self.assertFalse(np.array_equal(frames[0][1],frames[1][1]))

 def test_bounded_queues_apply_backpressure_without_dropping_frames(self):
  from frame_stream import SavedFramePipeline
  from visual_evidence import _save_keyframe
  produced=[]
  def source(*args,**kwargs):
   for i in range(30):
    produced.append(i);yield i*2000,np.full((30,40,3),(i%2)*200,np.uint8)
  with tempfile.TemporaryDirectory() as d,patch('frame_stream.sample_frames',side_effect=source):
   with SavedFramePipeline(Path(d)/'video',Path(d),threshold=.02,sample_seconds=2,regions=None,person_mode='off',save=_save_keyframe,capacity=1) as pipe:
    deadline=time.monotonic()+3
    while not pipe.ready.full() and time.monotonic()<deadline:time.sleep(.01)
    time.sleep(.15);self.assertLessEqual(len(produced),6);self.assertLessEqual(pipe.raw.qsize(),1)
    self.assertEqual(len(list(pipe)),30)
 def test_vfr_sampling_reports_actual_timestamp_and_skips_no_pts_guessing(self):
  import types
  from fractions import Fraction
  stream=types.SimpleNamespace(start_time=1000,time_base=Fraction(1,1000))
  def frame(pts):return types.SimpleNamespace(pts=pts,time_base=Fraction(1,1000),to_ndarray=lambda **_:np.zeros((8,10,3),np.uint8))
  class Fake:
   start_time=1000000;streams=types.SimpleNamespace(video=[stream])
   def __enter__(self):return self
   def __exit__(self,*_):pass
   def decode(self,s):return iter([frame(t) for t in (1021,2999,3041,5007)])
  with patch('frame_stream.av.open',return_value=Fake()):self.assertEqual([t for t,_ in __import__('frame_stream').sample_frames_pyav('unused',2)],[21,2041,4007])
 def test_cancelled_atomic_save_does_not_publish_or_leave_temp_file(self):
  from visual_evidence import _save_keyframe
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(CancelledError):_save_keyframe(np.zeros((30,40,3),np.uint8),Path(d),1000,_check=__import__('unittest.mock',fromlist=['Mock']).Mock(side_effect=[None,CancelledError()]))
   self.assertEqual(list(Path(d).iterdir()),[])
 def test_adjacent_person_and_include_ignore_masks_stack_without_modifying_original(self):
  frames=[]
  for i in range(4):
   f=np.full((180,320,3),255,np.uint8)
   f[20:150,5+i*25:45+i*25]=(0,0,255)
   if i>=2:f[20:100,180:260]=0
   f[120:170,230:300]=i*40
   frames.append((i*2000,f))
  class FakeLease:
   device='cuda'
   def __init__(self,mode):assert mode=='adjacent'
   def __enter__(self):return self
   def close(self):pass
   def invalidate(self):pass
   def predict(self,image):return (image[:,:,2]>150)&(image[:,:,0]<100)&(image[:,:,1]<100)
  settings={'analysisRegion':{'x':0.,'y':0.,'width':1.,'height':1.},'ignoredRegion':{'x':.7,'y':.65,'width':.3,'height':.35}}
  originals=[f.copy() for _,f in frames]
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'media';p.write_bytes(b'x')
   with patch('visual_evidence._has_video',return_value=True),patch('frame_stream.sample_frames',return_value=iter(frames)),patch('person_selection.PersonMaskLease',FakeLease):
    result=analyze_visuals(p,recognize=lambda _:[],ignore_region=settings,person_selection_mode='adjacent')
   self.assertEqual([f['frameTimeMs'] for f in result],[0,4000,6000])
   for (_,f),saved in zip(frames,originals):self.assertTrue(np.array_equal(f,saved))

 def test_cancel_during_ocr_never_publishes_stale_frame(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'media';p.write_bytes(b'x');seen=[]
   def ocr(frame):
    (root/'.analysis').mkdir(exist_ok=True);(root/'.analysis/cancel.json').write_text('{}');return []
   with patch('visual_evidence._has_video',return_value=True),patch('frame_stream.sample_frames',return_value=iter([(0,np.zeros((30,40,3),np.uint8))])):
    with self.assertRaises(CancelledError):analyze_visuals(p,keyframe_dir=root,recognize=ocr,on_frame=seen.append)
   self.assertEqual(seen,[])
 def test_new_run_identity_invalidates_guard_that_started_without_identity(self):
  from frame_stream import FrameRunGuard
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);guard=FrameRunGuard(root);guard.check();(root/'active-run.json').write_text('{"runId":"new"}')
   with self.assertRaises(CancelledError):guard.check()
 def test_vfr_supplement_uses_visible_frame_and_its_actual_timestamp(self):
  import types
  from fractions import Fraction
  stream=types.SimpleNamespace(start_time=0,time_base=Fraction(1,1000))
  def frame(t):return types.SimpleNamespace(pts=t,time_base=Fraction(1,1000),rotation=0,to_ndarray=lambda **_:np.full((8,10,3),t//1000,np.uint8))
  class Fake:
   start_time=0;duration=5000000;streams=types.SimpleNamespace(video=[stream])
   def __enter__(self):return self
   def __exit__(self,*_):pass
   def decode(self,s):return iter([frame(t) for t in (0,1000,3500)])
  with patch('frame_stream.av.open',return_value=Fake()):
   result=list(accurate_frames('unused',[2000]));self.assertEqual(result[0][0],1000);self.assertEqual(result[0][1][0,0,0],1)
 def test_rotated_original_matches_ffmpeg_display_orientation(self):
  with tempfile.TemporaryDirectory() as d:
   base=Path(d)/'base.mp4';rotated=Path(d)/'rotated.mp4'
   subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=25:duration=1','-c:v','libx264',str(base)],check=True)
   import av
   with av.open(str(base)) as src,av.open(str(rotated),'w') as dst:
    stream=dst.add_stream_from_template(src.streams.video[0]);stream.set_display_rotation(90)
    for packet in src.demux(video=0):
     if packet.dts is None:continue
     packet.stream=stream;dst.mux(packet)
   expected=cv2.imdecode(np.frombuffer(subprocess.run(['ffmpeg','-v','error','-i',str(rotated),'-frames:v','1','-f','image2pipe','-vcodec','png','pipe:1'],capture_output=True,check=True).stdout,np.uint8),cv2.IMREAD_COLOR)
   self.assertEqual(expected.shape,(160,90,3))
   got=next(sample_frames(rotated,2))[1];self.assertEqual(got.shape,expected.shape)
   self.assertLess(float(np.mean(np.abs(got.astype(float)-expected.astype(float)))),2)
   self.assertTrue(np.array_equal(next(accurate_frames(rotated,[0]))[1],got))

 def test_only_visual_stages_are_invalidated_by_pipeline_version(self):
  import os
  from uuid import uuid4
  from analysis import analyze_file
  with tempfile.TemporaryDirectory() as d:
   fid=str(uuid4());Path(d,fid).write_bytes(b'fixture')
   with patch.dict(os.environ,{'MEDIA_TEMP_DIR':d,'KEYFRAME_DIR':str(Path(d)/'frames')}),patch('analysis.transcribe_file',return_value={'language':'zh','segments':[]}) as speech,patch('analysis.VisualOcrWorker') as worker,patch('analysis.media_duration_ms',return_value=1000),patch('analysis.review_visual_coverage',return_value=([],{'status':'not_applicable'})),patch('analysis.group_pages',return_value=([],[])),patch('frame_stream.FRAME_PIPELINE_VERSION','test-v1'):
    worker.return_value.__enter__.return_value.analyze.return_value=[]
    analyze_file(fid)
    with patch('frame_stream.FRAME_PIPELINE_VERSION','test-v2'):analyze_file(fid)
    self.assertEqual(speech.call_count,1);self.assertEqual(worker.return_value.__enter__.return_value.analyze.call_count,2)
