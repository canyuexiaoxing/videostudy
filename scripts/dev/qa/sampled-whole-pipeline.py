"""Offline old/new visual chain benchmark. No ASR, course synthesis or paid calls."""
import hashlib,importlib.util,json,os,sys,time,threading,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
OUT=ROOT/'.local/qa/sampled-whole-pipeline';OUT.mkdir(parents=True,exist_ok=True)
os.environ['MODEL_LOG_DIR']=str(OUT/'logs')
import numpy as np,psutil
import frame_stream
import visual_evidence as current
from slide_grouping import group_pages
from person_selection import shutdown_person_worker
spec=importlib.util.spec_from_file_location('old_visual',ROOT/'.local/qa/frame-stream-baseline.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
video=ROOT/'30MIN.mp4'
clock=time.perf_counter
# Load the same OCR once for both variants; inputs/results otherwise never reused.
warm=clock();current._recognize(np.full((180,320,3),255,np.uint8))
report={'prewarm_s':round(clock()-warm,3),'scope':'whole-video selection + HD save + GPU OCR + local grouping; no ASR, supplements or cloud calls','cpu_scope':'main Python process only; excludes FFmpeg child','vram_scope':'whole GPU, including other resident processes','runs':[],'paidCalls':0}
for variant in os.environ.get('QA_VARIANTS','baseline_off,pyav_throttled,ffmpeg_sampled').split(','):
 mode='adjacent' if variant.endswith('adjacent') else 'off';module=old if variant.startswith('baseline') else current
 metrics={'ocr_s':0.,'save_s':0.,'selection_elapsed_s':0.,'ocr_count':0,'rss_peak_mib':0.,'main_python_cpu_percent_peak':0.,'vram_peak_mib':0.}
 resources_stop=threading.Event();proc=psutil.Process();cpu_begin=sum(proc.cpu_times()[:2]);started=clock()
 def resources():
  proc.cpu_percent(None)
  while not resources_stop.wait(.5):
   try:
    processes=[proc]+proc.children(recursive=True)
    metrics['rss_peak_mib']=max(metrics['rss_peak_mib'],sum(p.memory_info().rss for p in processes if p.is_running())/1024**2)
    metrics['main_python_cpu_percent_peak']=max(metrics['main_python_cpu_percent_peak'],proc.cpu_percent(None))
    value=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
    if value.returncode==0:metrics['vram_peak_mib']=max(metrics['vram_peak_mib'],float(value.stdout.strip().splitlines()[0]))
   except (OSError,ValueError,psutil.Error,subprocess.TimeoutExpired):pass
 monitor=threading.Thread(target=resources,daemon=True);monitor.start()
 original_source=frame_stream.sample_frames
 if variant=='pyav_throttled':frame_stream.sample_frames=frame_stream.sample_frames_pyav
 original_candidate=module._candidate_times;original_save=module._save_keyframe
 def candidate(*a,**k):
  before=clock();value=original_candidate(*a,**k);metrics['selection_elapsed_s']+=clock()-before;return value
 def save(*a,**k):
  before=clock();value=original_save(*a,**k);metrics['save_s']+=clock()-before;return value
 def recognize(frame):
  before=clock();value=current._recognize(frame);metrics['ocr_s']+=clock()-before;metrics['ocr_count']+=1
  if metrics['ocr_count']%100==0:print(json.dumps({'variant':variant,'ocr':metrics['ocr_count'],'elapsed_s':round(clock()-started,1)}),flush=True)
  return value
 module._candidate_times=candidate;module._save_keyframe=save
 folder=OUT/variant/'frames';folder.mkdir(parents=True,exist_ok=True)
 guardroot=folder/'.analysis';guardroot.mkdir(exist_ok=True);(guardroot/'active-run.json').write_text('{"runId":"offline-benchmark"}')
 try:
  values=module.analyze_visuals(video,keyframe_dir=folder,recognize=recognize,person_selection_mode=mode)
  visual_end=clock();reviews=[0]
  def local_review(payload):reviews[0]+=1;return {'samePage':False,'reason':'offline conservative split'}
  pages,transitions=group_pages(values,folder,[],ask_json=local_review)
  ended=clock();cpu_used=sum(proc.cpu_times()[:2])-cpu_begin
 finally:
  resources_stop.set();monitor.join();module._candidate_times=original_candidate;module._save_keyframe=original_save;frame_stream.sample_frames=original_source
 files=list(folder.glob('*.jpg'));hashes={hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
 row={'variant':variant,**{k:round(v,3) if isinstance(v,float) else v for k,v in metrics.items()},'visual_s':round(visual_end-started,3),'grouping_s':round(ended-visual_end,3),'total_s':round(ended-started,3),'main_python_cpu_core_equivalent_mean':round(cpu_used/(ended-started),3),'pages':len(pages),'saved':len(files),'unique_jpegs':len(hashes),'local_boundary_checks':reviews[0]}
 report['runs'].append(row);(OUT/variant/'visuals.json').write_text(json.dumps(values,ensure_ascii=False),encoding='utf-8');(OUT/variant/'pages.json').write_text(json.dumps(pages,ensure_ascii=False),encoding='utf-8');(OUT/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(row),flush=True)
shutdown_person_worker()
