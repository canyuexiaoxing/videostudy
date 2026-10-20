"""Occlusion-aware coarse selection. No neural runtime is imported in this process."""
import os,sys,json,base64,subprocess,threading,queue,hashlib,atexit
from pathlib import Path
import numpy as np
from model_diagnostics import record_event
VERSION='person-visibility-v2'
MODEL_SHA256='361fbfabab285c3237700b6bb91d7ecfa602cd945fffda8dbe1242829b71e73f'

def settings(selection_mode=None):
 if selection_mode is not None and selection_mode not in ('off','adjacent'):raise ValueError('invalid_person_selection_mode')
 mode=((os.environ.get('PERSON_DEVICE',os.environ.get('PERSON_SEGMENTATION','cpu')) if os.environ.get('FRAMEWISE_DEVICE_MODE') else 'cuda') if selection_mode=='adjacent' else 'off') if selection_mode is not None else os.environ.get('PERSON_SEGMENTATION','off')
 if mode not in ('off','auto','cpu','cuda'):raise ValueError('invalid_person_segmentation_mode')
 return {'mode':mode,'model':str(Path(os.environ.get('PERSON_MODEL_PATH',str(Path(os.environ.get('MODEL_DIR','../.local/models'))/'yolo26/yolo26n-seg.pt'))).resolve()),'python':os.environ.get('PERSON_PYTHON','/opt/person/bin/python'),'sha256':MODEL_SHA256,'version':VERSION,'imgsz':640,'threads':4,'libraryRoot':os.environ.get('PERSON_LIBRARY_ROOT','/opt/person-cuda/nvidia'),**({'strategy':'adjacent','strategyVersion':'adjacent-pair-v1'} if selection_mode=='adjacent' else {})}

def selection_context(selection_mode=None):
 config=settings(selection_mode)
 if config['mode']=='off':return {}
 def revision(path):
  try:
   s=Path(path).stat();return [s.st_size,s.st_mtime_ns]
  except OSError:return None
 from person_visibility import MASK_VERSION
 return {'personSelection':dict(config,modelRevision=revision(config['model']),runtimeRevision=revision(config['python']),libraryRevision=revision(config['libraryRoot']),groupingMaskVersion=MASK_VERSION)}

class VisibilitySelector:
 """Per-pixel comparison memory, never a synthesized screenshot or OCR source."""
 def __init__(self,threshold,max_wait_ms=30000):
  self.threshold=threshold;self.max_wait=max_wait_ms;self.reference=None;self.known=None;self.allowed=None;self.last_kept=None
  self.uncertain_frames=0;self.reveal_frames=0;self.pending_time=None;self.preserve_time=None
 def observe(self,frame,allowed,person,time_ms):
  self.preserve_time=None
  frame=np.asarray(frame);allowed=np.asarray(allowed,dtype=bool);person=np.asarray(person,dtype=bool)
  if frame.shape!=allowed.shape or frame.shape!=person.shape:raise ValueError('invalid_person_mask_shape')
  visible=allowed & ~person
  reset=self.reference is None or not np.array_equal(allowed,self.allowed)
  if reset:
   self.reference=np.zeros_like(frame);self.known=np.zeros_like(allowed);self.allowed=allowed.copy()
  known_visible=visible & self.known;unknown=visible & ~self.known
  denom=max(1,int(allowed.sum()))
  changed=(np.abs(frame.astype(np.int16)-self.reference.astype(np.int16))>25) & known_visible
  changed_fraction=int(changed.sum())/max(1,int(known_visible.sum()))
  reveal=int(unknown.sum())/denom
  if reveal>.001:self.reveal_frames+=1
  uncertain=int(visible.sum())/denom<.1
  if uncertain:self.uncertain_frames+=1
  elapsed=0 if self.last_kept is None else time_ms-self.last_kept
  keep=reset or self.last_kept is None
  if uncertain:keep=keep or elapsed>=self.max_wait
  else:keep=keep or reveal>.001 or changed_fraction>self.threshold or (elapsed>=self.max_wait and changed_fraction>.001)
  if keep:
   if self.pending_time is not None and (changed_fraction>self.threshold or uncertain or reset):self.preserve_time=self.pending_time
   self.pending_time=None
   if changed_fraction>.45:self.known[:]=False
   self.reference[visible]=frame[visible];self.known[visible]=True;self.last_kept=time_ms
  elif changed.any():self.pending_time=time_ms
  return bool(keep)

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

class PersonWorkerError(RuntimeError):
 def __init__(self,kind,reason):
  super().__init__(reason);self.error_type=kind;self.reason=reason

class PersonMaskProcess:
 """A separate interpreter keeps Torch/CUDA dependencies out of the Paddle worker."""
 def __init__(self,selection_mode=None):
  self.config=settings(selection_mode);self.process=None;self.answers=queue.Queue();self.device=None
 def __enter__(self):
  try:
   if not Path(self.config['python']).is_file():raise PersonWorkerError('FileNotFoundError','person_runtime_unavailable')
   if not Path(self.config['model']).is_file():raise PersonWorkerError('FileNotFoundError','person_model_invalid')
   env=dict(os.environ,PERSON_PARENT_PID=str(os.getpid()),PYTHONDONTWRITEBYTECODE='1',PERSON_SEGMENTATION=self.config['mode'])
   library_root=Path(self.config['libraryRoot'])
   if library_root.is_dir():
    libraries=[str(p) for p in sorted(library_root.glob('*/lib')) if p.parent.name!='nccl']
    env['LD_LIBRARY_PATH']=':'.join([*libraries,env.get('LD_LIBRARY_PATH','')])
   self.process=subprocess.Popen([self.config['python'],'-u',str(Path(__file__).with_name('person_mask_worker.py'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),text=True,encoding='utf-8',bufsize=1,env=env)
   def read():
    try:
     for line in self.process.stdout:self.answers.put(line)
    finally:self.answers.put(None)
   self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
   answer=self._receive();self.device=answer['device'];return self
  except BaseException:self.close();raise
 def _receive(self):
  try:line=self.answers.get(timeout=60)
  except queue.Empty:raise TimeoutError('person_worker_timeout')
  if line is None:raise RuntimeError('person_worker_stopped')
  value=json.loads(line)
  if not value.get('ok'):
   reason=value.get('reason')
   if reason not in {'person_model_invalid','person_cuda_unavailable','person_runtime_unavailable','person_model_load_failed','person_inference_failed'}:reason='person_inference_failed'
   raise PersonWorkerError(str(value.get('error_type','UnknownError')),reason)
  return value
 def predict(self,image):
  raw=np.asarray(image,dtype=np.uint8)
  self.process.stdin.write(json.dumps({'shape':list(raw.shape),'data':base64.b64encode(raw.tobytes()).decode('ascii')})+'\n');self.process.stdin.flush()
  value=self._receive();shape=tuple(value['shape'])
  if value.get('fallback'):
   self.device='cpu';os.environ['PERSON_DEVICE']='cpu'
  if shape!=raw.shape[:2]:raise ValueError('invalid_person_mask_shape')
  packed=base64.b64decode(value['data'],validate=True)
  if len(packed)!=(shape[0]*shape[1]+7)//8:raise ValueError('invalid_person_mask_size')
  return np.unpackbits(np.frombuffer(packed,dtype=np.uint8),count=shape[0]*shape[1]).reshape(shape).astype(bool)
 def alive(self):return self.process is not None and self.process.poll() is None
 def close(self):
  if self.process is not None:
   if self.process.stdin:
    try:self.process.stdin.close()
    except (OSError,BrokenPipeError):pass
   try:self.process.wait(timeout=3)
   except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=5)
   if self.process.stdout:self.process.stdout.close()
   if hasattr(self,'reader'):self.reader.join(timeout=1)
   self.process=None
 def __exit__(self,*args):self.close()

_person_lock=threading.RLock()
_cached_person=None
_cached_identity=None

def shutdown_person_worker():
 global _cached_person,_cached_identity
 with _person_lock:
  if _cached_person is not None:_cached_person.close()
  _cached_person=None;_cached_identity=None

atexit.register(shutdown_person_worker)

class PersonMaskLease:
 """Serialize calls and reuse weights only; each video keeps its own visibility memory."""
 def __init__(self,selection_mode=None):self.closed=True;self.worker=None;self.selection_mode=selection_mode
 def __enter__(self):
  global _cached_person,_cached_identity
  _person_lock.acquire();self.closed=False
  try:
   identity=selection_context(self.selection_mode)
   if _cached_person is not None and (_cached_identity!=identity or not _cached_person.alive()):shutdown_person_worker()
   if _cached_person is None:
    _cached_person=(PersonMaskProcess() if self.selection_mode is None else PersonMaskProcess(self.selection_mode)).__enter__();_cached_identity=identity
   self.worker=_cached_person;self.device=self.worker.device;return self
  except BaseException:self.close();raise
 def predict(self,image):return self.worker.predict(image)
 def invalidate(self):
  try:shutdown_person_worker()
  finally:self.close()
 def close(self):
  if not self.closed:self.closed=True;_person_lock.release()
 def __exit__(self,*args):self.close()


