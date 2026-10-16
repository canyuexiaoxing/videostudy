"""Full offline visual pipeline: actual coarse selection, HD capture, OCR and page grouping."""
import os,sys,json,time
from pathlib import Path
sys.path.insert(0,'/src/agent-python')
OUT=Path('/out');OUT.mkdir(parents=True,exist_ok=True)
os.environ['MODEL_LOG_DIR']=str(OUT/'logs')
import visual_evidence as ve
from slide_grouping import group_pages
from person_selection import shutdown_person_worker
MODE=os.environ['PERSON_SEGMENTATION'];clock=time.perf_counter
STRATEGY=os.environ.get('QA_PERSON_STRATEGY','history')
if STRATEGY=='adjacent':
    sys.path.insert(0,str(Path(__file__).parent))
    from adjacent_pair_selector import AdjacentPairSelector
    ve.VisibilitySelector=AdjacentPairSelector
original_candidate=ve._candidate_times;original_frames=ve._frames_at;original_ocr=ve._recognize;original_save=ve._save_keyframe
original_event=ve.record_event
report={'strategy':STRATEGY,'mode':MODE,'ocr_device':os.environ.get('OCR_DEVICE'),'scope':'Actual analyze_visuals then group_pages; no cache reuse, no paid boundary model calls; no manual include/ignore region','runs':[]}
metrics={};events=[]
def capture(*args,**kwargs):events.append(dict(event=args[0],**kwargs));return original_event(*args,**kwargs)
ve.record_event=capture

def candidate(*args,**kwargs):
    begin=clock();value=original_candidate(*args,**kwargs);metrics['coarse_s']+=clock()-begin;metrics['candidate_count']=len(value);return value

def frames(*args,**kwargs):
    iterator=iter(original_frames(*args,**kwargs))
    try:
        while True:
            begin=clock()
            try:value=next(iterator)
            except StopIteration:metrics['hd_extract_s']+=clock()-begin;break
            metrics['hd_extract_s']+=clock()-begin;yield value
    finally:
        if hasattr(iterator,'close'):iterator.close()

def recognize(frame):
    begin=clock();value=original_ocr(frame);metrics['ocr_s']+=clock()-begin;metrics['ocr_frames']+=1
    if metrics['ocr_frames']%50==0:print(json.dumps({'mode':MODE,'state':state,'progress_frames':metrics['ocr_frames'],'elapsed_s':round(clock()-started,1)}),flush=True)
    return value

def save(*args,**kwargs):
    begin=clock();value=original_save(*args,**kwargs);metrics['save_jpeg_s']+=clock()-begin;return value
ve._candidate_times=candidate;ve._frames_at=frames;ve._recognize=recognize;ve._save_keyframe=save
try:
    if os.environ.get('QA_PREWARM')=='1':
        import numpy as np
        warm_started=clock();original_ocr(np.full((180,320,3),255,np.uint8))
        if MODE!='off':
            from person_selection import PersonMaskLease
            with PersonMaskLease() as worker:worker.predict(np.full((180,320,3),255,np.uint8))
        report['prewarm_s']=round(clock()-warm_started,3)
    for state in os.environ.get('QA_STATES','cold,warm').split(','):
        metrics={'coarse_s':0.,'hd_extract_s':0.,'ocr_s':0.,'save_jpeg_s':0.,'ocr_frames':0};events.clear();started=clock()
        visuals=ve.analyze_visuals(Path('/video.mp4'),keyframe_dir=OUT/state/'frames')
        visual_end=clock();reviews=[0]
        def offline_review(payload):
            reviews[0]+=1;return {'samePage':False,'reason':'offline benchmark; conservative split; no cloud call'}
        pages,transitions=group_pages(visuals,OUT/state/'frames',[],ask_json=offline_review)
        finished=clock()
        if any(e['event']=='stage_failed' for e in events):raise RuntimeError(json.dumps(events))
        assert metrics['ocr_frames']==len(visuals)==metrics['candidate_count']
        row={'state':state,**{k:round(v,3) if isinstance(v,float) else v for k,v in metrics.items()},'visual_total_s':round(visual_end-started,3),'grouping_s':round(finished-visual_end,3),'total_s':round(finished-started,3),'page_count':len(pages),'representative_count':sum(len(p['representativeFrameTimesMs']) for p in pages),'uncertain_boundaries_local_fallback':reviews[0],'events':list(events)}
        report['runs'].append(row)
        (OUT/state/'visuals.json').write_text(json.dumps(visuals,ensure_ascii=False),encoding='utf-8');(OUT/state/'pages.json').write_text(json.dumps(pages,ensure_ascii=False),encoding='utf-8');(OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(row,ensure_ascii=False),flush=True)
finally:shutdown_person_worker()
