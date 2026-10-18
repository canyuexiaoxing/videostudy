"""Exact-frame person-mask sidecars for opt-in page grouping; no inference."""
import base64,hashlib,json
from pathlib import Path
from uuid import uuid4
import cv2,numpy as np
from person_selection import MODEL_SHA256
MASK_VERSION='selected-person-mask-v1'
GROUPING_VERSION='person-page-group-v2'

def enabled(mode=None):
 from person_selection import settings
 return settings(mode)['mode']!='off'

def _run(root):
 path=Path(root)/'.analysis/active-run.json'
 return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def save_visibility(root,time_ms,mask,frame_size,*,_check=lambda:None):
 root=Path(root)
 if type(time_ms) is not int or time_ms<0:raise ValueError('invalid_frame_time')
 width,height=frame_size
 if type(width) is not int or type(height) is not int or min(width,height)<=0:raise ValueError('invalid_frame_size')
 record={'version':MASK_VERSION,'frameTimeMs':time_ms,'frameSize':[width,height],'modelSha256':MODEL_SHA256,'run':_run(root),'status':'unavailable'}
 if mask is not None:
  if np.asarray(mask).shape!=(180,320):raise ValueError('invalid_person_mask_shape')
  record.update(status='available',imageSha256=hashlib.sha256((root/f'{time_ms}.jpg').read_bytes()).hexdigest(),data=base64.b64encode(np.packbits(np.asarray(mask,dtype=bool))).decode('ascii'))
 folder=root/'.person-masks';folder.mkdir(parents=True,exist_ok=True);path=folder/f'{time_ms}.json';temporary=folder/f'{time_ms}.{uuid4().hex}.tmp'
 try:
  _check();temporary.write_text(json.dumps(record,separators=(',',':')),encoding='utf-8');_check();temporary.replace(path)
 finally:temporary.unlink(missing_ok=True)

def load_visibility(root,time_ms,frame_size,*,_check=lambda:None):
 root=Path(root);path=root/'.person-masks'/f'{time_ms}.json'
 try:
  _check()
  if path.stat().st_size>20000:return None
  data=json.loads(path.read_text(encoding='utf-8'))
  if data.get('version')!=MASK_VERSION or data.get('status')!='available' or data.get('frameTimeMs')!=time_ms:return None
  if data.get('frameSize')!=list(frame_size) or data.get('modelSha256')!=MODEL_SHA256:return None
  if data.get('imageSha256')!=hashlib.sha256((root/f'{time_ms}.jpg').read_bytes()).hexdigest():return None
  packed=base64.b64decode(data['data'],validate=True)
  if len(packed)!=7200:return None
  mask=np.unpackbits(np.frombuffer(packed,np.uint8)).reshape(180,320)
  width,height=frame_size;ratio=min(320/width,180/height);rw,rh=max(1,round(width*ratio)),max(1,round(height*ratio));x,y=(320-rw)//2,(180-rh)//2
  _check();return cv2.resize(mask[y:y+rh,x:x+rw],(320,180),interpolation=cv2.INTER_NEAREST).astype(bool)
 except (OSError,ValueError,KeyError,TypeError,OverflowError):return None

def grouping_context(root,visuals,mode=None):
 if not enabled(mode):return {}
 root=Path(root);digest=hashlib.sha256();digest.update(GROUPING_VERSION.encode())
 for frame in sorted(visuals,key=lambda f:f['frameTimeMs']):
  t=frame['frameTimeMs'];digest.update(str(t).encode())
  for path in (root/'.person-masks'/f'{t}.json',root/f'{t}.jpg'):
   try:digest.update(hashlib.sha256(path.read_bytes()).digest())
   except OSError:digest.update(b'missing')
 return {'personGrouping':{'version':GROUPING_VERSION,'fingerprint':digest.hexdigest()}}
