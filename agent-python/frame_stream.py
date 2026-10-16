"""Actual-PTS video frames and bounded select/save/OCR handoff. No provider calls."""
from concurrent.futures import CancelledError
from pathlib import Path
import queue,threading,time,subprocess
import av
import cv2
import numpy as np
from ignored_region import effective_mask
from model_diagnostics import record_event

FRAME_PIPELINE_VERSION='sampled-ffmpeg-pts-v2'
QUEUE_CAPACITY=2

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


def _origin(container,stream):
 if container.start_time is not None:return float(container.start_time)/av.time_base
 if stream.start_time is not None:return float(stream.start_time*stream.time_base)
 return None

def _decoded(container,stream,origin,check):
 previous=None
 for frame in container.decode(stream):
  check()
  if frame.pts is None or frame.time_base is None:raise ValueError('video_frame_timestamp_missing')
  stamp=float(frame.pts*frame.time_base)
  if origin is None:origin=stamp
  ms=round((stamp-origin)*1000)
  if previous is not None and ms<previous:raise ValueError('video_frame_timestamp_regressed')
  previous=ms
  yield ms,frame

def display_image(frame):
 image=frame.to_ndarray(format='bgr24')
 rotation=getattr(frame,'rotation',0)
 if rotation==90:return cv2.rotate(image,cv2.ROTATE_90_COUNTERCLOCKWISE)
 if rotation==-90:return cv2.rotate(image,cv2.ROTATE_90_CLOCKWISE)
 if abs(rotation)==180:return cv2.rotate(image,cv2.ROTATE_180)
 if rotation:raise ValueError('video_display_rotation_unsupported')
 return image

def sample_frames_pyav(path,sample_seconds=2,*,check=lambda:None):
 if sample_seconds not in (2,3,4):raise ValueError('sample_seconds must be 2, 3 or 4')
 with av.open(str(path)) as container:
  if not container.streams.video:return
  stream=container.streams.video[0];stream.thread_type='AUTO';stream.thread_count=4
  due=0;last=-1
  for ms,frame in _decoded(container,stream,_origin(container,stream),check):
   if ms<due or ms<=last:continue
   yield ms,display_image(frame)
   last=ms;due=(ms//(sample_seconds*1000)+1)*sample_seconds*1000

def sample_frames_ffmpeg(path,sample_seconds=2,*,check=lambda:None):
 """FFmpeg selects originals internally; NUT carries pixels and their real PTS."""
 if sample_seconds not in (2,3,4):raise ValueError('sample_seconds must be 2, 3 or 4')
 check()
 with av.open(str(path)) as source:
  if not source.streams.video:return
  origin=_origin(source,source.streams.video[0])
 # Use the same integer-ms sampling grid as the sequential reference, no fps filter.
 relative=f'(t-({origin:.12f}))' if origin is not None else '(t-start_t)'
 previous=f'(prev_selected_t-({origin:.12f}))' if origin is not None else '(prev_selected_t-start_t)'
 bucket=f'floor(floor({relative}*1000+0.5)/{sample_seconds*1000})'
 prior=f'floor(floor({previous}*1000+0.5)/{sample_seconds*1000})'
 expression=f'gte({relative},0)*if(isnan(prev_selected_t),1,gt({bucket},{prior}))'
 command=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-copyts','-i',str(path),
          '-map','0:v:0','-an','-sn','-dn','-vf','select='+expression.replace(',',r'\,'),
          '-fps_mode','passthrough','-enc_time_base:v','1:1000000','-c:v','rawvideo','-threads:v','1','-pix_fmt','bgr24',
          '-avoid_negative_ts','disabled','-f','nut','pipe:1']
 process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 stop=threading.Event();failure=[];failure_reason=[];started=time.monotonic();count=0;status='failed';error_kind=None
 def monitor():
  while not stop.wait(.1):
   try:check()
   except BaseException as error:
    failure.append(error)
    if process.poll() is None:process.kill()
    return
 def drain():
  # Bounded transient bytes classify errors; raw stderr is never logged or saved.
  tail=b''
  patterns=((b'no such file or directory','video_input_unavailable'),(b'invalid data found','video_input_invalid'),
            (b'error while decoding','video_decode_failed'),(b'error initializing','video_filter_or_encoder_failed'),
            (b'unknown encoder','video_output_unavailable'),(b'no space left','video_output_io_failed'))
  try:
   while chunk:=process.stderr.read(1024):
    tail=(tail+chunk)[-4096:]
    for token,reason in patterns:
     if token in tail.lower():failure_reason[:]=[reason]
  except OSError:pass
 watcher=threading.Thread(target=monitor,name='sampled-ffmpeg-watch',daemon=True)
 stderr=threading.Thread(target=drain,name='sampled-ffmpeg-stderr',daemon=True)
 watcher.start();stderr.start()
 try:
  try:
   with av.open(process.stdout,format='nut',options={'probesize':'32','analyzeduration':'0'}) as output:
    for ms,frame in _decoded(output,output.streams.video[0],origin,check):
     if failure:raise failure[0]
     count+=1;yield ms,display_image(frame)
   if failure:raise failure[0]
   check()
   if process.wait()!=0:raise RuntimeError('video_frame_sampling_failed')
   status='completed'
  except Exception:
   if failure:raise failure[0]
   raise
 except BaseException as error:
  error_kind=type(error).__name__
  if isinstance(error,(CancelledError,GeneratorExit)):status='cancelled'
  raise
 finally:
  stop.set()
  if process.poll() is None:process.kill()
  process.wait();watcher.join();stderr.join()
  process.stdout.close();process.stderr.close()
  record_event('stage_completed' if status=='completed' else 'stage_failed',Path(path).name,operation='frame_pipeline',stage='decode',image_count=count,elapsed_ms=round((time.monotonic()-started)*1000),status=status,error_type=error_kind,exit_code=process.returncode,reason=(failure_reason[0] if failure_reason else 'video_frame_sampling_failed') if status=='failed' else None)


def sample_frames(path,sample_seconds=2,*,check=lambda:None):
 yield from sample_frames_ffmpeg(path,sample_seconds,check=check)


def preview(original,setting,time_ms,with_person):
 h,w=original.shape[:2];ratio=min(320/w,180/h)
 rw,rh=max(1,round(w*ratio)),max(1,round(h*ratio));x,y=(320-rw)//2,(180-rh)//2
 bgr=np.zeros((180,320,3),dtype=np.uint8)
 bgr[y:y+rh,x:x+rw]=cv2.resize(original,(rw,rh),interpolation=cv2.INTER_AREA)
 rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB) if with_person else None
 gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
 mask=None
 if setting:
  allowed=effective_mask(w,h,setting,time_ms)
  mask=np.zeros((180,320),dtype=bool)
  mask[y:y+rh,x:x+rw]=cv2.resize(allowed.astype(np.uint8),(rw,rh),interpolation=cv2.INTER_NEAREST).astype(bool)
  if not mask.any():raise ValueError('ignored_region_leaves_no_visible_pixels')
 return gray,rgb,mask

def accurate_frames(path,times_ms,*,check=lambda:None,with_request=False):
 """Find the frame displayed at target; actual PTS is the image/source identity."""
 for target in dict.fromkeys(times_ms):
  if type(target) is not int or target<0:raise ValueError('invalid_frame_time')
  preroll=5000;attempt=0;started=time.monotonic()
  while True:
   attempt+=1;check();start=max(0,target-preroll);found=None;actual=None;previous=None
   with av.open(str(path)) as container:
    if not container.streams.video:raise ValueError('video_stream_missing')
    if container.duration is not None and target>round(container.duration/av.time_base*1000):raise ValueError('frame_time_outside_video')
    stream=container.streams.video[0];stream.thread_count=2
    origin=_origin(container,stream)
    if start and origin is not None:
     container.seek(round((origin+start/1000)/float(stream.time_base)),stream=stream,backward=True,any_frame=False)
    else:start=0
    for ms,frame in _decoded(container,stream,origin,check):
     if ms==target:actual,found=ms,display_image(frame);break
     if ms>target:
      if previous is not None:actual,found=previous[0],display_image(previous[1])
      elif start==0:actual,found=ms,display_image(frame)
      break
     previous=(ms,frame)
    else:
     if previous is not None:
      # Last picture remains displayed through the known duration, not beyond it.
      end=round(container.duration/av.time_base*1000) if container.duration is not None else previous[0]
      if target<=end:actual,found=previous[0],display_image(previous[1])
   if found is not None:
    record_event('stage_completed',Path(path).name,operation='frame_pipeline',stage='capture',status='completed',requested_time_ms=target,actual_time_ms=actual,attempt=attempt,elapsed_ms=round((time.monotonic()-started)*1000))
    yield (target,actual,found) if with_request else (actual,found)
    break
   if start==0:raise ValueError('frame_time_outside_video')
   preroll*=2

class SavedFramePipeline:
 """One selector + one atomic saver; the caller consumes saved original frames."""
 def __init__(self,path,root,*,threshold,sample_seconds,regions,person_mode,save,capacity=QUEUE_CAPACITY):
  if not 1<=capacity<=4:raise ValueError('invalid_frame_queue_capacity')
  self.path=Path(path);self.root=Path(root) if root is not None else None
  self.threshold=threshold;self.sample_seconds=sample_seconds;self.regions=regions;self.person_mode=person_mode;self.save=save
  self.raw=queue.Queue(capacity);self.ready=queue.Queue(capacity);self.stop=threading.Event()
  self.guard=FrameRunGuard(self.root/'.analysis' if self.root else None)
  self.error=None;self.lock=threading.Lock();self.end=object();self.saved=0;self.queue_peak=0;self.started=time.monotonic();self.threads=[]
 def check(self,*,force=False):
  if self.error is not None:raise self.error
  if self.stop.is_set():raise CancelledError('analysis_cancelled')
  self.guard.check(force=force)
 def _put(self,q,value):
  while True:
   self.check()
   try:q.put(value,timeout=.1);self.queue_peak=max(self.queue_peak,q.qsize());return
   except queue.Full:pass
 def _get(self,q):
  while True:
   self.check()
   try:return q.get(timeout=.1)
   except queue.Empty:pass
 def _fail(self,error):
  with self.lock:
   if self.error is None:self.error=error
  self.stop.set()
 def _select(self):
  from visual_evidence import _candidate_times
  source=sample_frames(self.path,self.sample_seconds,check=self.check)
  try:
   _candidate_times(self.path,self.threshold,self.sample_seconds,self.regions,self.person_mode,
     _sample_source=source,_selected=lambda ms,frame:self._put(self.raw,(ms,frame)),_check=self.check)
   self._put(self.raw,self.end)
  except BaseException as error:
   if not self.stop.is_set():self._fail(error)
  finally:source.close() if hasattr(source,'close') else None
 def _save(self):
  try:
   while True:
    item=self._get(self.raw)
    if item is self.end:self._put(self.ready,self.end);return
    ms,frame=item;self.check()
    if self.root is not None:self.save(frame,self.root,ms,_check=lambda:self.check(force=True))
    self.check();self.saved+=1;self._put(self.ready,item)
  except BaseException as error:
   if not self.stop.is_set():self._fail(error)
 def __enter__(self):
  self.check(force=True)
  record_event('stage_started',self.root.name if self.root else 'unbound',operation='frame_pipeline',stage='selection')
  self.threads=[threading.Thread(target=f,name='same-frame-'+name,daemon=True) for f,name in ((self._select,'select'),(self._save,'save'))]
  for thread in self.threads:thread.start()
  return self
 def __iter__(self):
  while True:
   item=self._get(self.ready)
   if item is self.end:return
   self.check(force=True);yield item
 def __exit__(self,kind,error,tb):
  self.stop.set()
  for thread in self.threads:thread.join()
  # Release queued images before a retry starts.
  for q in (self.raw,self.ready):
   while not q.empty():
    try:q.get_nowait()
    except queue.Empty:break
  record_event('stage_completed' if kind is None else 'stage_failed',self.root.name if self.root else 'unbound',operation='frame_pipeline',stage='selection',status='completed' if kind is None else 'cancelled' if kind is CancelledError else 'failed',image_count=self.saved,queue_peak=self.queue_peak,elapsed_ms=round((time.monotonic()-self.started)*1000),error_type=kind.__name__ if kind else None,reason=str(error) if kind is not None else None)
  return False
