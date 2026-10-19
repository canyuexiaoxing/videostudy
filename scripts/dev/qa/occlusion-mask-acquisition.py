"""GPU mask acquisition for offline grouping experiment, network disabled by Docker."""
import os,time,json,hashlib,statistics
from pathlib import Path
import cv2,numpy as np,torch
from ultralytics import YOLO
ROOT=Path('/src');OUT=Path('/out');SOURCE=ROOT/'.local/qa/grouping-multi-20261017'
IDS=['d517b4f7-58d3-483d-bd9f-a0966341461b','56ac6493-3085-45e2-b9c4-130b583b95d1','cbacd60e-c271-48b2-9353-2bc88d7c2aec','427ff2cd-8534-4f04-bc75-0a275c9e918b']
OUT.mkdir(parents=True,exist_ok=True)
def emit(stage,**kw):
 row={'stage':stage,**kw};print(json.dumps(row,ensure_ascii=False),flush=True)
 with (OUT/'mask-events.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
model_path=ROOT/'.local/models/yolo26/yolo26n-seg.pt'
assert hashlib.sha256(model_path.read_bytes()).hexdigest()=='361fbfabab285c3237700b6bb91d7ecfa602cd945fffda8dbe1242829b71e73f'
assert torch.cuda.is_available();torch.set_num_threads(4)
t0=time.perf_counter();model=YOLO(str(model_path));load_s=time.perf_counter()-t0
kw=dict(device='0',half=True,imgsz=640,classes=[0],conf=.25,retina_masks=True,verbose=False)
t0=time.perf_counter();model.predict(np.zeros((180,320,3),np.uint8),**kw);torch.cuda.synchronize();cold_s=time.perf_counter()-t0
torch.set_num_threads(4);torch.cuda.reset_peak_memory_stats()
report={'model':'yolo26n-seg.pt','input':'same letterboxed 320x180 RGB preview and 640 inference settings as production person worker; masks remapped to stretched grouping grid','model_load_s':load_s,'cold_first_prediction_s':cold_s,'runs':3,'device':torch.cuda.get_device_name(0),'courses':{},'limitations':['Isolated inference without concurrent OCR/ASR.','Historical saved JPGs, not original sampled pixels; no video decode or IPC measured.','No-detection does not prove absence of occlusion.','CPU runtime not benchmarked.']}
for run in range(3):
 for course in (IDS if run%2==0 else IDS[::-1]):
  data=json.loads((SOURCE/f'{course}.json').read_text());masks={};rows=[];inference=[];reads=[];writes=[];start=time.perf_counter()
  for frame in data['visualEvidence']:
   t=frame['frameTimeMs'];path=ROOT/'.local/keyframes'/course/f'{t}.jpg';begin=time.perf_counter();raw=path.read_bytes();image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR);h,w=image.shape[:2]
   ratio=min(320/w,180/h);rw,rh=max(1,round(w*ratio)),max(1,round(h*ratio));x,y=(320-rw)//2,(180-rh)//2
   preview=np.zeros((180,320,3),np.uint8);preview[y:y+rh,x:x+rw]=cv2.resize(image,(rw,rh),interpolation=cv2.INTER_AREA);preview=cv2.cvtColor(preview,cv2.COLOR_BGR2RGB);reads.append(time.perf_counter()-begin)
   torch.cuda.synchronize();begin=time.perf_counter();result=model.predict(preview,**kw)[0]
   mask=np.zeros((180,320),np.uint8)
   if result.masks is not None:mask=np.any(result.masks.data.cpu().numpy()>.5,axis=0).astype(np.uint8)
   mask=cv2.dilate(mask,np.ones((3,3),np.uint8));mask=cv2.resize(mask[y:y+rh,x:x+rw],(320,180),interpolation=cv2.INTER_NEAREST).astype(bool)
   torch.cuda.synchronize();inference.append(time.perf_counter()-begin)
   if run==0:
    masks[str(t)]=np.packbits(mask);rows.append({'time_ms':t,'width':w,'height':h,'sha256':hashlib.sha256(raw).hexdigest(),'person_pixels':int(mask.sum()),'detections':len(result.boxes),'mask_grid':[180,320]})
  infer_total=sum(inference);read_total=sum(reads)
  if run==0:
   begin=time.perf_counter();np.savez_compressed(OUT/f'{course}-masks.npz',**masks);(OUT/f'{course}-mask-index.json').write_text(json.dumps({'model_sha256':hashlib.sha256(model_path.read_bytes()).hexdigest(),'frames':rows}),encoding='utf-8');write_s=time.perf_counter()-begin
  else:write_s=0.
  row={'run':run+1,'frames':len(data['visualEvidence']),'read_resize_s':read_total,'infer_transfer_mask_s':infer_total,'write_s':write_s,'wall_s':time.perf_counter()-start,'per_image_median_ms':statistics.median(inference)*1000,'per_image_p95_ms':float(np.percentile(inference,95))*1000}
  report['courses'].setdefault(course,[]).append(row);emit('course_complete',course=course,**row)
  report['gpu_peak_allocated_mib']=torch.cuda.max_memory_allocated()/2**20;report['gpu_peak_reserved_mib']=torch.cuda.max_memory_reserved()/2**20
  (OUT/'mask-timing.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
emit('complete',model_load_s=load_s,cold_first_prediction_s=cold_s)
