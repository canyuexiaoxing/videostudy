"""Measure isolated YOLO process resources during continuous offline inference."""
from pathlib import Path
from time import perf_counter
import os,json,threading,subprocess,statistics
import cv2,torch,psutil
from ultralytics import YOLO
OUT=Path('/out');OUT.mkdir(parents=True,exist_ok=True)
mode=os.environ.get('QA_MODE','cpu');size=int(os.environ.get('QA_SIZE','640'));seconds=12
process=psutil.Process();cores=psutil.cpu_count();samples=[];stop=threading.Event()
def card():
 try:
  row=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=3).strip().splitlines()[0].split(',')
  return {'memory_mib':int(row[0]),'gpu_percent':int(row[1])}
 except Exception:return {}
def monitor():
 process.cpu_percent(None)
 while not stop.wait(.25):
  samples.append({'cpu_percent_one_core_scale':process.cpu_percent(None),'rss_mib':process.memory_info().rss/2**20,**card()})
start=perf_counter();before=card();torch.set_num_threads(4)
images=[cv2.imread('/frames/frame-'+str(t)+'.jpg') for t in [60,300,900,1500,2400]]
if any(x is None for x in images):raise RuntimeError('Missing prior local sample image')
if size==320:images=[cv2.resize(x,(320,180)) for x in images]
model=YOLO('/models/yolo26n-seg.pt');kw=dict(imgsz=size,device='cpu' if mode=='cpu' else '0',half=mode=='gpu',classes=[0],conf=.25,retina_masks=True,verbose=False)
for im in images:model.predict(im,**kw)
if mode=='gpu':torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats()
thread=threading.Thread(target=monitor,daemon=True);thread.start();count=0;begin=perf_counter()
while perf_counter()-begin<seconds:
 result=model.predict(images[count%len(images)],**kw)[0]
 if result.masks is not None:mask=result.masks.data.cpu().numpy();del mask
 if mode=='gpu':torch.cuda.synchronize()
 count+=1
elapsed=perf_counter()-begin;stop.set();thread.join(4)
report={'mode':mode,'imgsz':size,'duration_s':elapsed,'predictions':count,'cpu_logical_cores':cores,'cpu_threads_requested':4,'torch_threads_actual':torch.get_num_threads(),'sampling_count':len(samples),'cpu_mean_one_core_scale_pct':statistics.mean(s['cpu_percent_one_core_scale'] for s in samples),'cpu_peak_one_core_scale_pct':max(s['cpu_percent_one_core_scale'] for s in samples),'cpu_mean_whole_machine_pct':statistics.mean(s['cpu_percent_one_core_scale'] for s in samples)/cores,'cpu_peak_whole_machine_pct':max(s['cpu_percent_one_core_scale'] for s in samples)/cores,'rss_mean_mib':statistics.mean(s['rss_mib'] for s in samples),'rss_peak_mib':max(s['rss_mib'] for s in samples),'card_before':before,'card_peak_mib':max((s['memory_mib'] for s in samples if 'memory_mib' in s),default=None),'card_mean_utilization_pct':statistics.mean(s['gpu_percent'] for s in samples if 'gpu_percent' in s),'torch_peak_allocated_mib':torch.cuda.max_memory_allocated()/2**20 if mode=='gpu' else 0,'torch_peak_reserved_mib':torch.cuda.max_memory_reserved()/2**20 if mode=='gpu' else 0,'conditions':'Each mode is a separate process. Continuous inference, not one image every two wall-clock seconds. Video decoding, OCR and transcription excluded. CPU percentage normalized across visible logical cores; container sees host logical cores. GPU total includes desktop and other processes.','samples':samples}
(OUT/'resources.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='samples'}),flush=True)
