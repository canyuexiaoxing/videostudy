"""Compare offline coarse modes with sampled process-tree resources and mask previews."""
import os,sys,json,time,threading,subprocess,statistics
from pathlib import Path
import cv2,numpy as np,psutil
sys.path.insert(0,'/src/agent-python')
OUT=Path('/out');OUT.mkdir(parents=True,exist_ok=True)
os.environ['MODEL_LOG_DIR']=str(OUT/'logs')
import visual_evidence as ve
from person_selection import shutdown_person_worker,PersonMaskLease
EVENTS=[]
original=ve.record_event
def capture(*args,**kwargs):
    EVENTS.append(dict(event=args[0],**kwargs));return original(*args,**kwargs)
ve.record_event=capture
class Monitor:
    def __init__(self):self.stop=threading.Event();self.samples=[];self.proc=psutil.Process();self.prev={}
    def sample(self):
        now=time.perf_counter();cpu=0;rss=0;pss=0
        for p in [self.proc,*self.proc.children(recursive=True)]:
            try:
                t=p.cpu_times();total=t.user+t.system;old=self.prev.get(p.pid)
                if old:cpu+=max(0,total-old[1])/max(.001,now-old[0])*100
                self.prev[p.pid]=(now,total);rss+=p.memory_info().rss
                pss+=getattr(p.memory_full_info(),'pss',0)
            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        row={'cpu_whole_machine_pct':cpu/psutil.cpu_count(),'rss_mib':rss/2**20,'pss_mib':pss/2**20}
        try:
            result=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=3).splitlines()[0].split(',')
            row.update(card_mib=int(result[0]),card_gpu_pct=int(result[1]))
        except Exception:pass
        self.samples.append(row)
    def __enter__(self):
        self.sample()
        def loop():
            while not self.stop.wait(1):self.sample()
        self.thread=threading.Thread(target=loop,daemon=True);self.thread.start();return self
    def __exit__(self,*args):self.stop.set();self.thread.join(5);self.sample()
    def result(self):
        return {'samples':self.samples,'cpu_mean_pct':round(statistics.mean(s['cpu_whole_machine_pct'] for s in self.samples[1:]),2),'rss_peak_mib':round(max(s['rss_mib'] for s in self.samples),1),'pss_peak_mib':round(max(s['pss_mib'] for s in self.samples),1),'card_before_mib':self.samples[0].get('card_mib'),'card_peak_mib':max((s.get('card_mib',0) for s in self.samples),default=None)}
cap=cv2.VideoCapture('/video.mp4');duration=cap.get(cv2.CAP_PROP_FRAME_COUNT)/cap.get(cv2.CAP_PROP_FPS);cap.release()
report={'video':os.environ['QA_VIDEO_NAME'],'duration_s':duration,'sample_seconds':2,'scope':'coarse selection only, full video; no OCR, ASR or paid model calls','resource_notes':'CPU normalized across logical cores; process tree includes decode and model. RSS sum counts shared pages repeatedly; PSS proportional shared memory. Whole card includes desktop. One-second sampling may miss peaks. Cold includes initialization; warm reuses weights.','runs':[]}
try:
    for mode in ['off','cpu','cuda','auto']:
        shutdown_person_worker();os.environ['PERSON_SEGMENTATION']=mode;previous=None
        for state in ['cold','warm']:
            EVENTS.clear()
            with Monitor() as monitor:
                start=time.perf_counter();times=ve._candidate_times(Path('/video.mp4'),sample_seconds=2);elapsed=time.perf_counter()-start
            if any(e['event']=='stage_failed' for e in EVENTS):raise RuntimeError(json.dumps(EVENTS))
            assert times==sorted(set(times))
            if previous is not None:assert times==previous
            previous=times
            row={'mode':mode,'state':state,'seconds':round(elapsed,3),'candidate_count':len(times),'events':list(EVENTS),'timestamps_ms':times,'resources':monitor.result()}
            report['runs'].append(row);(OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in row.items() if k not in ['timestamps_ms','resources']},ensure_ascii=False),flush=True)
    cap=cv2.VideoCapture('/video.mp4');tiles=[];checks=[]
    with PersonMaskLease() as model:
        for i,fraction in enumerate([.05,.2,.4,.6,.8,.95]):
            sec=duration*fraction;cap.set(cv2.CAP_PROP_POS_MSEC,sec*1000);ok,frame=cap.read()
            if not ok:continue
            h,w=frame.shape[:2];scale=min(320/w,180/h);nw,nh=round(w*scale),round(h*scale);small=np.zeros((180,320,3),np.uint8);x=(320-nw)//2;y=(180-nh)//2;small[y:y+nh,x:x+nw]=cv2.resize(frame,(nw,nh))
            mask=model.predict(small);overlay=small.copy();overlay[mask]=(overlay[mask]*.45+np.array([0,150,255])*.55).astype(np.uint8)
            tile=cv2.resize(overlay,(640,360));cv2.putText(tile,f'{int(sec)//60:02d}:{int(sec)%60:02d} mask={100*mask.mean():.1f}%',(12,25),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,0,255),2)
            cv2.imwrite(str(OUT/f'original-{i}.jpg'),frame);cv2.imwrite(str(OUT/f'mask-{i}.png'),mask.astype(np.uint8)*255);tiles.append(tile);checks.append({'time_s':sec,'mask_pixels':int(mask.sum())})
    cap.release()
    if len(tiles)==6:cv2.imwrite(str(OUT/'mask-contact.jpg'),np.vstack([np.hstack(tiles[:3]),np.hstack(tiles[3:])]))
    report['mask_checks']=checks;(OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'mask_checks':checks}),flush=True)
finally:shutdown_person_worker()
