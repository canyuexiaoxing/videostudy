"""Offline GPU benchmark; artifacts stay in .local/qa, never touch course records."""
from pathlib import Path
from time import perf_counter,sleep
from concurrent.futures import ThreadPoolExecutor
import json,os,sys,threading,subprocess,multiprocessing as mp,hashlib,difflib,re,resource
ROOT=Path(__file__).resolve().parents[3]
EVENT_LOCK=threading.Lock()
TIMESTAMPS=os.environ.get('QA_BENCH_TIMESTAMPS')=='1'
OUT=Path(os.environ.get('QA_BENCH_OUT',str(ROOT/'.local/qa/batch4-benchmark')))
VIDEO=Path(os.environ.get('QA_BENCH_VIDEO',str(ROOT/'40ren.mp4')))
FRAMES=Path(os.environ.get('QA_BENCH_FRAMES',str(ROOT/'.local/keyframes')))

def event(name,**data):
    row={'run_elapsed_s':round(perf_counter()-START,3),'event':name,**data}
    line=json.dumps(row,ensure_ascii=False)
    with EVENT_LOCK:
        print(line,flush=True)
        with (OUT/'events.jsonl').open('a',encoding='utf-8') as file:file.write(line+'\n')

class Telemetry:
    def __init__(self):self.samples=[];self.stop=threading.Event();self.thread=threading.Thread(target=self.run,daemon=True)
    def run(self):
        while not self.stop.is_set():
            try:
                r=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
                fields=r.stdout.strip().splitlines()[0].split(',')
                self.samples.append({'time_s':perf_counter(),'memory_mib':int(fields[0]),'total_mib':int(fields[1]),'gpu_percent':int(fields[2])})
            except Exception:pass
            self.stop.wait(.5)
    def start(self):self.thread.start()
    def finish(self):self.stop.set();self.thread.join(timeout=4)
    def interval(self,a,b):
        values=[x for x in self.samples if a<=x['time_s']<=b]
        return {'gpu_samples':len(values),'peak_total_gpu_mib':max((x['memory_mib'] for x in values),default=None),'mean_gpu_percent':round(sum(x['gpu_percent'] for x in values)/len(values),1) if values else None}

def ocr_worker(pipe,times):
    # Paddle uses a separate process, matching the production OCR worker.
    with (OUT/'ocr-worker.log').open('w',encoding='utf-8') as output:
        sys.stdout=output;sys.stderr=output
        try:
            sys.path.insert(0,'/app');import cv2
            from visual_evidence import _ocr_model,_recognize
            before=perf_counter();_ocr_model();_recognize(cv2.imread(str(FRAMES/f'{times[0]}.jpg')))
            pipe.send({'event':'ready','initialization_s':perf_counter()-before})
            while True:
                command=pipe.recv()
                if command=='stop':break
                before=perf_counter();items=[]
                for i,t in enumerate(times):
                    image=cv2.imread(str(FRAMES/f'{t}.jpg'))
                    if image is None:raise ValueError('Missing benchmark frame')
                    blocks=_recognize(image);texts=[b['text'] for b in blocks]
                    items.append({'frameTimeMs':t,'texts':texts})
                    if (i+1)%10==0:pipe.send({'event':'progress','frames':i+1,'elapsed_s':perf_counter()-before})
                (OUT/f'{command}-texts.json').write_text(json.dumps(items,ensure_ascii=False),encoding='utf-8')
                pipe.send({'event':'result','seconds':perf_counter()-before,'frames':len(items),'blocks':sum(len(i['texts']) for i in items),'text_digest':hashlib.sha256(json.dumps(items,ensure_ascii=False).encode()).hexdigest()})
        except Exception as error:
            pipe.send({'event':'error','error_type':type(error).__name__})
            import traceback;traceback.print_exc()

def run_ocr(pipe,name):
    before=perf_counter();event('stage_start',stage=name);pipe.send(name)
    while True:
        if not pipe.poll(180):raise TimeoutError('OCR benchmark worker stopped responding')
        item=pipe.recv()
        if item['event']=='error':raise RuntimeError('OCR benchmark failed: '+item['error_type'])
        if item['event']=='progress':event('ocr_progress',stage=name,frames=item['frames'],elapsed_s=round(item['elapsed_s'],2));continue
        if item['event']=='result':
            item.pop('event');item.update(telemetry.interval(before,perf_counter()));event('stage_completed',stage=name,**item);return item

def run_asr(model,audio,name,batch=False):
    before=perf_counter();event('stage_start',stage=name);last=before
    if batch:
        from faster_whisper import BatchedInferencePipeline
        from faster_whisper.vad import VadOptions
        segments,info=BatchedInferencePipeline(model).transcribe(audio,beam_size=5,batch_size=4,without_timestamps=not TIMESTAMPS,vad_filter=True,vad_parameters={'min_silence_duration_ms':VadOptions().min_silence_duration_ms})
    else:segments,info=model.transcribe(audio,beam_size=5,vad_filter=True)
    values=[]
    for segment in segments:
        values.append({'start':segment.start,'end':segment.end,'text':segment.text})
        if perf_counter()-last>=10:
            event('asr_progress',stage=name,segments=len(values),audio_position_s=round(segment.end,1),elapsed_s=round(perf_counter()-before,1));last=perf_counter()
    end=perf_counter();(OUT/f'{name}-transcript.json').write_text(json.dumps(values,ensure_ascii=False),encoding='utf-8')
    invalid=sum(v['start']<0 or v['end']<v['start'] or v['end']>len(audio)/16000+1 for v in values)
    regressions=sum(values[i]['start']<values[i-1]['start'] for i in range(1,len(values)))
    summary={'seconds':end-before,'segments':len(values),'characters':sum(len(v['text']) for v in values),'language':info.language,'invalid_time_segments':invalid,'out_of_order_segments':regressions,'duration_after_vad_s':info.duration_after_vad,**telemetry.interval(before,end)}
    event('stage_completed',stage=name,**summary);return summary

def text(name):
    values=json.loads((OUT/f'{name}-transcript.json').read_text())
    return re.sub(r'\s+','', ''.join(v['text'] for v in values))

def main():
    global START,telemetry
    START=perf_counter();OUT.mkdir(parents=True,exist_ok=True);telemetry=Telemetry();telemetry.start();worker=None
    results={'network':'disabled','paidModelCalls':0,'model':'small','device':'cuda','compute_type':'float16','beam_size':5,'batch_size':4,'batch_segment_timestamps':TIMESTAMPS,'gpu_memory_metric':'whole GPU including desktop/other processes; sampled at 0.5s'}
    try:
        manifest=json.loads((OUT/'manifest.json').read_text());times=manifest['frameTimesMs'];results['ocr_frames']=len(times)
        event('benchmark_start',frames=len(times),model='small',batch_size=4)
        from faster_whisper import WhisperModel,BatchedInferencePipeline
        from faster_whisper.audio import decode_audio
        before=perf_counter();audio=decode_audio(str(VIDEO),sampling_rate=16000);results['audio_decode_s']=perf_counter()-before;results['audio_duration_s']=len(audio)/16000
        event('audio_decoded',seconds=round(results['audio_decode_s'],2),duration_s=results['audio_duration_s'])
        before=perf_counter();model=WhisperModel(str(Path(os.environ['MODEL_DIR'])/'faster-whisper-small'),device='cuda',compute_type='float16');results['asr_model_load_s']=perf_counter()-before
        event('asr_model_loaded',seconds=round(results['asr_model_load_s'],2))
        warm=audio[:30*16000];list(model.transcribe(warm,beam_size=5,vad_filter=True)[0]);list(BatchedInferencePipeline(model).transcribe(warm,beam_size=5,vad_filter=True,batch_size=4,without_timestamps=not TIMESTAMPS)[0]);event('asr_warmup_completed')
        reference=os.environ.get('QA_BENCH_REFERENCE')
        if reference:
            old=Path(reference);results['standard_alone']=json.loads((old/'results.json').read_text())['standard_alone'];results['standard_baseline_reused']=True
            (OUT/'standard-alone-transcript.json').write_bytes((old/'standard-alone-transcript.json').read_bytes())
            event('standard_baseline_reused',seconds=round(results['standard_alone']['seconds'],2))
        else:results['standard_alone']=run_asr(model,audio,'standard-alone')
        results['batch4_alone']=run_asr(model,audio,'batch4-alone',True)
        ctx=mp.get_context('spawn');parent,child=ctx.Pipe();worker=ctx.Process(target=ocr_worker,args=(child,times));worker.start();child.close()
        if not parent.poll(180):raise TimeoutError('OCR model initialization timed out')
        ready=parent.recv()
        if ready['event']!='ready':raise RuntimeError('OCR initialization failed: '+ready.get('error_type','unknown'))
        results['ocr_model_initialization_s']=ready['initialization_s'];event('ocr_model_loaded',seconds=round(ready['initialization_s'],2))
        results['ocr_alone']=run_ocr(parent,'ocr-alone')
        before=perf_counter();event('concurrent_start')
        with ThreadPoolExecutor(max_workers=2) as pool:
            speech=pool.submit(run_asr,model,audio,'batch4-with-ocr',True);vision=pool.submit(run_ocr,parent,'ocr-with-batch4')
            results['batch4_with_ocr']=speech.result();results['ocr_with_batch4']=vision.result()
        end=perf_counter();results['concurrent_wall_s']=end-before;results['concurrent_gpu']=telemetry.interval(before,end)
        results['standard_vs_batch4_text_similarity']=difflib.SequenceMatcher(None,text('standard-alone'),text('batch4-alone'),autojunk=False).ratio()
        results['batch4_alone_vs_concurrent_text_equal']=text('batch4-alone')==text('batch4-with-ocr')
        results['ocr_alone_vs_concurrent_text_equal']=results['ocr_alone']['text_digest']==results['ocr_with_batch4']['text_digest']
        results['batch4_speedup_vs_standard']=results['standard_alone']['seconds']/results['batch4_alone']['seconds']
        results['parent_peak_ram_mib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
        event('benchmark_completed',concurrent_wall_s=round(results['concurrent_wall_s'],2),batch4_speedup=round(results['batch4_speedup_vs_standard'],2),text_equal=results['batch4_alone_vs_concurrent_text_equal'])
    except Exception as error:
        results['failed']=True;results['error_type']=type(error).__name__;event('benchmark_failed',error_type=type(error).__name__)
        import traceback;traceback.print_exc();raise
    finally:
        if worker and worker.is_alive():
            try:parent.send('stop');worker.join(timeout=15)
            except Exception:pass
            if worker.is_alive():worker.terminate();worker.join(timeout=5)
        telemetry.finish();(OUT/'gpu-samples.json').write_text(json.dumps(telemetry.samples),encoding='utf-8');(OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
