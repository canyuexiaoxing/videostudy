"""Exercise the real isolated worker and coarse sampler without OCR or paid calls."""
from pathlib import Path
import cv2,os,json,subprocess,time,sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
from person_selection import PersonMaskProcess
from visual_evidence import _candidate_times
OUT=Path(os.environ.get('PERSON_QA_OUT',str(ROOT/'.local/qa/person-integration')));OUT.mkdir(parents=True,exist_ok=True)
frame=cv2.imread('/frames/frame-900.jpg');small=cv2.resize(frame,(320,180));started=time.perf_counter()
with PersonMaskProcess() as worker:
 pid=worker.process.pid;device=worker.device;mask=worker.predict(small)
 visualization=small.copy();visualization[mask]=(0,180,255);cv2.imwrite(str(OUT/'mask-smoke.jpg'),visualization)
 assert mask.shape==(180,320) and mask.dtype.name=='bool' and 0<int(mask.sum())<mask.size*.4
 closed_process=worker.process
assert closed_process.poll() is not None
report={'device':device,'mask_pixels':int(mask.sum()),'worker_closed':closed_process.poll() is not None,'worker_smoke_ms':round((time.perf_counter()-started)*1000),'timings':{},'candidates':{}}
clip=OUT/'clip.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss','60','-i','/video.mp4','-t','60','-c','copy',str(clip)],check=True)
for label,mode in [('off','off'),('auto_cold','auto'),('auto_warm','auto')]:
 os.environ['PERSON_SEGMENTATION']=mode;start=time.perf_counter();times=_candidate_times(clip)
 report['timings'][label]=round((time.perf_counter()-start)*1000);report['candidates'][label]=times
 assert times==sorted(set(times)) and times and times[-1]>=56000
from person_selection import shutdown_person_worker
shutdown_person_worker()
assert report['candidates']['auto_cold']==report['candidates']['auto_warm']
(OUT/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
