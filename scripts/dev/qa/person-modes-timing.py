"""Offline full-video timing for all deployed person-selection modes."""
import os, sys, json, time, statistics
from pathlib import Path
sys.path.insert(0, '/src/agent-python')
os.environ.setdefault('MODEL_LOG_DIR', '/qa/person-modes-timing/logs')
import visual_evidence as ve
from person_selection import shutdown_person_worker
out=Path('/out'); out.mkdir(parents=True,exist_ok=True)
events=[]
original=ve.record_event
def capture(*args,**kwargs):
    events.append(dict(event=args[0] if args else None, **kwargs))
    return original(*args,**kwargs)
ve.record_event=capture
report={'video':'40ren.mp4','sample_seconds':2,'scope':'full video coarse selection only; includes decode, IPC, person inference and comparison; excludes OCR/ASR/LLM','runs':[]}
try:
    for mode in ['off','cpu','cuda','auto']:
        shutdown_person_worker()
        os.environ['PERSON_SEGMENTATION']=mode
        previous=None
        for state in ['cold','warm']:
            events.clear()
            start=time.perf_counter()
            times=ve._candidate_times(Path('/video.mp4'),sample_seconds=2)
            elapsed=time.perf_counter()-start
            failures=[e for e in events if e['event']=='stage_failed']
            if failures: raise RuntimeError(json.dumps(failures))
            assert times==sorted(set(times))
            if previous is not None: assert times==previous, 'cold/warm timestamps differ'
            previous=times
            row={'mode':mode,'state':state,'seconds':round(elapsed,3),'candidate_count':len(times),'events':list(events),'timestamps_ms':times}
            report['runs'].append(row)
            (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in row.items() if k!='timestamps_ms'}),flush=True)
finally:
    shutdown_person_worker()
