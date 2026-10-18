"""Isolated real-JPG YOLO-only regression. No OCR, ASR, providers or original mutation."""
import sys,json,time,shutil,statistics,importlib.util,hashlib
from pathlib import Path
import cv2,numpy as np,torch
from ultralytics import YOLO
sys.path.insert(0,'/src/agent-python')
from person_visibility import save_visibility,grouping_context
from slide_grouping import group_pages
R=Path('/src');O=Path('/out');ID='427ff2cd-8534-4f04-bc75-0a275c9e918b'
data=json.loads((R/'.local/qa/grouping-multi-20261017'/f'{ID}.json').read_text());frames=data['visualEvidence'];folder=O/ID;folder.mkdir(exist_ok=True)
meta=json.loads((R/'.local/qa/grouping-multi-20261017/metadata.json').read_text());region=json.loads(meta[ID]['region']) if meta[ID]['region'] else None
model=YOLO(str(R/'.local/models/yolo26/yolo26n-seg.pt'));torch.set_num_threads(4)
kw=dict(device='0',half=True,imgsz=640,classes=[0],conf=.25,retina_masks=True,verbose=False)
model.predict(np.zeros((180,320,3),np.uint8),**kw);torch.cuda.synchronize();torch.set_num_threads(4)
infer=[];persist=[];person=[]
for f in frames:
 t=f['frameTimeMs'];target=folder/f'{t}.jpg';shutil.copyfile(R/'.local/keyframes'/ID/f'{t}.jpg',target);image=cv2.imread(str(target));h,w=image.shape[:2];ratio=min(320/w,180/h);rw,rh=max(1,round(w*ratio)),max(1,round(h*ratio));x,y=(320-rw)//2,(180-rh)//2
 preview=np.zeros((180,320,3),np.uint8);preview[y:y+rh,x:x+rw]=cv2.resize(image,(rw,rh),interpolation=cv2.INTER_AREA)
 torch.cuda.synchronize();start=time.perf_counter();result=model.predict(preview,**kw)[0];mask=np.zeros((180,320),np.uint8)
 if result.masks is not None:mask=np.any(result.masks.data.cpu().numpy()>0,axis=0).astype(np.uint8)
 mask=cv2.dilate(mask,np.ones((3,3),np.uint8)).astype(bool);torch.cuda.synchronize();infer.append(time.perf_counter()-start)
 start=time.perf_counter();save_visibility(folder,t,mask,(w,h));persist.append(time.perf_counter()-start)
 if mask.any():person.append(t)
report={'frames':len(frames),'person_frames':len(person),'input':'production-matching BGR letterboxed preview; saved JPG replay','historical_mask_note':'Previous offline acquisition incorrectly used RGB input; old masks not reused.','offline_reacquire_s':sum(infer),'mask_write_s':sum(persist),'trials':{},'limitations':['Saved JPG replay, no fresh full-video decode/OCR/ASR.','Mask-write measurement includes Windows bind filesystem.','Model startup and offline mask regeneration are not incremental production overhead.']}
results={}
for mode in ['off','adjacent']:
 durations=[];contexts=[]
 for _ in range(5):
  start=time.perf_counter();context=grouping_context(folder,frames,mode);contexts.append(time.perf_counter()-start)
  start=time.perf_counter();pages,trans=group_pages(frames,folder,[],ask_json=lambda _:{'samePage':False},ignore_region=region,person_selection_mode=mode);durations.append(time.perf_counter()-start)
 results[mode]=pages;report['trials'][mode]={'group_s':durations,'group_median_s':statistics.median(durations),'cache_context_s':contexts,'groups':len(pages),'representatives':len(set(t for p in pages for t in p['representativeFrameTimesMs']))}
 (O/f'{mode}-pages.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2))
old={t:i for i,p in enumerate(results['off']) for t in p['memberFrameTimesMs']};changes=[]
for p in results['adjacent']:
 sources=sorted(set(old[t]+1 for t in p['memberFrameTimesMs']))
 if len(sources)>1:changes.append({'original_groups':sources,'members':p['memberFrameTimesMs'],'representatives':p['representativeFrameTimesMs']})
report['merged']=changes;report['all_original_representatives_preserved']=set(t for p in results['off'] for t in p['representativeFrameTimesMs'])<=set(t for p in results['adjacent'] for t in p['representativeFrameTimesMs'])
(O/'real-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False),flush=True)
