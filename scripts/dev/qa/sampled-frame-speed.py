"""Same 60-second source/guard/interval comparison, no OCR or provider calls."""
from pathlib import Path
import sys,importlib.util,json,time,contextlib
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
import frame_stream as now
spec=importlib.util.spec_from_file_location('old_stream',ROOT/'.local/qa/pre-sampled-runtime/frame_stream.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
out=ROOT/'.local/qa/sampled-frame-speed';out.mkdir(parents=True,exist_ok=True)
guardroot=out/'guard';guardroot.mkdir(exist_ok=True);(guardroot/'active-run.json').write_text('{"runId":"offline-probe"}')
rows=[]
for name,source,guard in [('old_pyav_disk_every_frame',old.sample_frames,old.FrameRunGuard(guardroot).check),('pyav_throttled',now.sample_frames_pyav,now.FrameRunGuard(guardroot).poll),('ffmpeg_sampled',now.sample_frames_ffmpeg,now.FrameRunGuard(guardroot).poll),('ffmpeg_sampled_repeat',now.sample_frames_ffmpeg,now.FrameRunGuard(guardroot).poll),('pyav_throttled_repeat',now.sample_frames_pyav,now.FrameRunGuard(guardroot).poll)]:
 start=time.perf_counter();count=0;times=[]
 with contextlib.closing(source(ROOT/'30MIN.mp4',2,check=guard)) as samples:
  for ms,image in samples:
   count+=1;times.append(ms)
   if ms>=60000:break
 row={'mode':name,'seconds':round(time.perf_counter()-start,3),'samples':count,'times':times};rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='times'}),flush=True)
assert all(r['times']==rows[0]['times'] for r in rows)
(out/'results.json').write_text(json.dumps({'firstSeconds':60,'intervalSeconds':2,'runs':rows,'sameActualTimes':True,'paidCalls':0},indent=2))
