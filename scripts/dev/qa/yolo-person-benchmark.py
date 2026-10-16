"""Offline YOLO person-mask benchmark; does not modify analysis records."""
from pathlib import Path
from time import perf_counter
import json, os, statistics, subprocess, traceback, gc
import cv2, numpy as np, psutil, torch, ultralytics
from ultralytics import YOLO
OUT=Path(os.environ.get('YOLO_QA_OUT','/out'))
OUT.mkdir(parents=True,exist_ok=True)
START=perf_counter()
def log(stage, **fields):
    row={'stage':stage,'elapsed_s':round(perf_counter()-START,3),**fields}
    line=json.dumps(row,ensure_ascii=False)
    print(line,flush=True)
    with (OUT/'events.jsonl').open('a',encoding='utf-8') as f:f.write(line+'\n')
def card():
    try:
        r=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
        return r.stdout.strip()
    except Exception:return None
def sync(device):
    if device!='cpu':torch.cuda.synchronize()
def run():
    torch.set_num_threads(4)
    cap=cv2.VideoCapture('/video.mp4')
    if not cap.isOpened():raise RuntimeError('Existing course video cannot be opened')
    frames=[]
    for sec in [0,60,300,900,1500,2400]:
        cap.set(cv2.CAP_PROP_POS_MSEC,sec*1000)
        ok,image=cap.read()
        if not ok:raise RuntimeError('Unable to decode sample frame')
        cv2.imwrite(str(OUT/f'frame-{sec}.jpg'),image)
        frames.append((sec,image))
    cap.release()
    log('frames_ready',count=len(frames))
    baseline=card()
    report={'model':'yolo26n-seg.pt','torch':torch.__version__,'ultralytics':ultralytics.__version__,'cpu_threads_requested':4,'cpu':Path('/proc/cpuinfo').read_text().split('model name')[1].split('\n')[0].strip() if Path('/proc/cpuinfo').exists() else None,'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,'format':'PyTorch, batch 1, imgsz 640/320, person only, retina_masks true, includes mask transfer to CPU','baseline_card':baseline,'cases':[],'limitations':['Six samples of one slide course with a webcam overlay; not a walking teacher blackboard benchmark.','Frames decoded before timing. Loading, output rendering and disk writes excluded from steady-state latency.','No concurrent OCR or transcription in this test.','Not an ONNX or TensorRT benchmark.']}
    variants=[('cpu',False,640),('0',False,640),('0',True,640),('cpu',False,320),('0',True,320)]
    for device,half,imgsz in variants:
        if device!='cpu' and not torch.cuda.is_available():continue
        label=('cpu-fp32' if device=='cpu' else ('gpu-fp16' if half else 'gpu-fp32'))+'-'+str(imgsz)
        case_frames=frames if imgsz==640 else [(sec,cv2.resize(im,(320,180))) for sec,im in frames]
        log('case_start',case=label,card=card())
        load_start=perf_counter()
        model=YOLO('/models/yolo26n-seg.pt')
        load_ms=(perf_counter()-load_start)*1000
        kw=dict(device=device,half=half,imgsz=imgsz,classes=[0],conf=.25,verbose=False,retina_masks=True)
        sync(device);before=perf_counter()
        first=model.predict(case_frames[0][1],**kw)[0]
        sync(device);cold_ms=(perf_counter()-before)*1000
        for _ in range(2):model.predict(case_frames[0][1],**kw)
        sync(device)
        if device!='cpu':torch.cuda.reset_peak_memory_stats()
        samples=[];details=[]
        for repeat in range(3):
            for sec,image in case_frames:
                sync(device);before=perf_counter()
                result=model.predict(image,**kw)[0]
                if result.masks is not None:
                    mask=result.masks.data.cpu().numpy()
                    del mask
                sync(device);wall_ms=(perf_counter()-before)*1000
                samples.append(wall_ms)
                if repeat==0:
                    boxes=result.boxes.xyxy.cpu().tolist()
                    confidence=result.boxes.conf.cpu().tolist()
                    details.append({'time_s':sec,'persons':len(boxes),'boxes':boxes,'confidence':confidence,'mask_shape':list(result.masks.data.shape) if result.masks is not None else None,'model_speed_ms':result.speed})
                    cv2.imwrite(str(OUT/f'{label}-{sec}.jpg'),result.plot())
                del result
        row={'case':label,'torch_threads_actual':torch.get_num_threads(),'imgsz':imgsz,'input_shape':list(case_frames[0][1].shape),'model_load_ms':round(load_ms,2),'first_prediction_ms':round(cold_ms,2),'warm_samples':len(samples),'warm_mean_ms':round(statistics.mean(samples),2),'warm_median_ms':round(statistics.median(samples),2),'warm_p95_ms':round(float(np.percentile(samples,95)),2),'warm_total_s':round(sum(samples)/1000,3),'estimated_900_frames_s':round(statistics.mean(samples)*900/1000,2),'process_rss_mib':round(psutil.Process().memory_info().rss/2**20,1),'gpu_peak_allocated_mib':round(torch.cuda.max_memory_allocated()/2**20,1) if device!='cpu' else None,'gpu_peak_reserved_mib':round(torch.cuda.max_memory_reserved()/2**20,1) if device!='cpu' else None,'card_after':card(),'detections':details}
        report['cases'].append(row)
        (OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        log('case_complete',**{k:v for k,v in row.items() if k!='detections'})
        del first,model;gc.collect()
        if torch.cuda.is_available():torch.cuda.empty_cache()
    lines=['# YOLO26n-seg local benchmark','', '| Mode | First prediction ms | Warm mean ms | P95 ms | 900 frames extrapolation s |','|---|---:|---:|---:|---:|']
    for r in report['cases']:lines.append(f"| {r['case']} | {r['first_prediction_ms']} | {r['warm_mean_ms']} | {r['warm_p95_ms']} | {r['estimated_900_frames_s']} |")
    lines+=['','Extrapolation only; video decoding and concurrent task contention excluded.','']+report['limitations']
    (OUT/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    log('complete',report='results.json')
try:run()
except Exception as e:
    log('failed',type=type(e).__name__,reason=str(e)[:300]);traceback.print_exc();raise
