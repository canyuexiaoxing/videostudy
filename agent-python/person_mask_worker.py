"""Offline person-mask IPC worker. Only this process loads the neural runtime."""
import os,sys,json,base64,hashlib,threading,time
from pathlib import Path
from contextlib import redirect_stdout
import numpy as np

def reply(value):print(json.dumps(value,separators=(',',':')),flush=True)
def main():
 parent=int(os.environ.get('PERSON_PARENT_PID','0'))
 def watch():
  while parent:
   if os.getppid()!=parent:os._exit(0)
   time.sleep(1)
 threading.Thread(target=watch,daemon=True).start()
 from person_selection import settings
 config=settings();path=Path(config['model'])
 if hashlib.sha256(path.read_bytes()).hexdigest()!=config['sha256']:raise ValueError('person_model_digest_mismatch')
 with redirect_stdout(sys.stderr):
  import torch,cv2
  from ultralytics import YOLO
  mode=config['mode'];device='0' if mode=='cuda' or (mode=='auto' and torch.cuda.is_available()) else 'cpu'
  if device=='0' and not torch.cuda.is_available():raise RuntimeError('person_cuda_unavailable')
  model=YOLO(str(path));torch.set_num_threads(config['threads'])
 reply({'ok':True,'device':'cuda' if device=='0' else 'cpu'})
 for line in sys.stdin:
  try:
   request=json.loads(line);shape=tuple(request['shape'])
   if len(shape)!=3 or shape[2]!=3 or not 1<=shape[0]<=640 or not 1<=shape[1]<=640:raise ValueError('invalid_preview_shape')
   raw=base64.b64decode(request['data'],validate=True)
   if len(raw)!=int(np.prod(shape)):raise ValueError('invalid_preview_size')
   image=np.frombuffer(raw,dtype=np.uint8).reshape(shape)
   with redirect_stdout(sys.stderr):
    result=model.predict(image,device=device,half=device!='cpu',imgsz=640,classes=[0],conf=.25,retina_masks=True,verbose=False)[0]
    # select_device can override CPU threads on the first call.
    torch.set_num_threads(config['threads'])
   mask=np.zeros(shape[:2],dtype=np.uint8)
   if result.masks is not None:mask=np.any(result.masks.data.cpu().numpy()>0,axis=0).astype(np.uint8)
   # A small safety margin protects body edges; original images remain untouched.
   mask=cv2.dilate(mask,np.ones((3,3),np.uint8))
   reply({'ok':True,'shape':list(mask.shape),'data':base64.b64encode(np.packbits(mask).tobytes()).decode('ascii')})
  except Exception as error:reply({'ok':False,'error_type':type(error).__name__,'reason':'person_inference_failed'});break
if __name__=='__main__':
 try:main()
 except Exception as error:
  code=str(error)
  reason='person_model_invalid' if code=='person_model_digest_mismatch' or isinstance(error,FileNotFoundError) else 'person_cuda_unavailable' if code=='person_cuda_unavailable' else 'person_runtime_unavailable' if isinstance(error,ImportError) else 'person_model_load_failed'
  reply({'ok':False,'error_type':type(error).__name__,'reason':reason});sys.exit(1)
