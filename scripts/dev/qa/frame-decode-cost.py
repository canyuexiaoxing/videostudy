"""Offline 60s decode/cancellation-I/O probe; production code stays unchanged."""
from pathlib import Path
import sys,time,json,subprocess
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
from frame_stream import sample_frames,FrameRunGuard
out=ROOT/'.local/qa/frame-decode-cost';out.mkdir(parents=True,exist_ok=True)
guardroot=out/'guard';guardroot.mkdir(exist_ok=True);(guardroot/'active-run.json').write_text('{"runId":"probe"}')
video=ROOT/'30MIN.mp4'
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_name,width,height,r_frame_rate:format=duration,size','-of','json',str(video)]))
rows=[]
for mode in ('no_filesystem_check','current_check_every_frame','check_at_most_every_200ms'):
 guard=FrameRunGuard(guardroot);calls=[0];last=[0.]
 def check():
  calls[0]+=1
  if mode=='no_filesystem_check':return
  now=time.monotonic()
  if mode=='check_at_most_every_200ms' and now-last[0]<.2:return
  guard.check();last[0]=now
 started=time.perf_counter();count=0
 with __import__('contextlib').closing(sample_frames(video,2,check=check)) as frames:
  for ms,image in frames:
   count+=1
   if ms>=60000:break
 rows.append({'mode':mode,'elapsedS':round(time.perf_counter()-started,3),'samples':count,'checkCalls':calls[0]});print(json.dumps(rows[-1]),flush=True)
report={'video':probe,'firstSeconds':60,'runs':rows,'ocr':False,'paidCalls':0}
(out/'results.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
