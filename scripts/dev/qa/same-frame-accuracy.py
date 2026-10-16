"""Offline real TS frame identity + short GPU-person integration; no provider calls."""
from pathlib import Path
import sys,json,time,subprocess
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
OUT=ROOT/'.local/qa/same-frame-accuracy';OUT.mkdir(parents=True,exist_ok=True)
import os
os.environ['MODEL_LOG_DIR']=str(OUT/'logs')
import av,cv2,numpy as np
from frame_stream import accurate_frames,display_image,_origin,_decoded
from visual_evidence import analyze_visuals
from person_selection import shutdown_person_worker
video=next(ROOT.glob('[[]3.15.1]*.mp4'))
requests=[102000,104000,106000];expected={};previous=None
with av.open(str(video)) as c:
 s=c.streams.video[0]
 for ms,f in _decoded(c,s,_origin(c,s),lambda:None):
  while len(expected)<len(requests) and requests[len(expected)]<ms:
   expected[requests[len(expected)]]=previous or (ms,display_image(f))
  if len(expected)==len(requests):break
  previous=(ms,display_image(f)) if ms>=101000 else None
rows=[]
for requested,actual,img in accurate_frames(video,requests,with_request=True):
 stamp,ref=expected[requested];assert actual==stamp and np.array_equal(img,ref),(requested,actual,stamp)
 cv2.imwrite(str(OUT/f'{requested}-actual-{actual}.jpg'),img)
 rows.append({'requestedMs':requested,'actualMs':actual,'matchesSequentialDecode':True})
assert not np.array_equal(cv2.imread(str(OUT/f'{rows[0]["requestedMs"]}-actual-{rows[0]["actualMs"]}.jpg')),cv2.imread(str(OUT/f'{rows[1]["requestedMs"]}-actual-{rows[1]["actualMs"]}.jpg')))
# A copied 60-second segment avoids reanalyzing any historical course.
clip=OUT/'person-clip.ts'
subprocess.run(['ffmpeg','-v','error','-y','-ss','900','-i',str(video),'-t','60','-c','copy','-f','mpegts',str(clip)],check=True)
start=time.perf_counter();seen=[]
try:
 values=analyze_visuals(clip,keyframe_dir=OUT/'gpu-person-frames',person_selection_mode='adjacent',recognize=lambda image:[],on_frame=lambda value:seen.append(value['frameTimeMs']))
finally:shutdown_person_worker()
assert values and seen==[v['frameTimeMs'] for v in values]
events=[]
for log in (OUT/'logs').glob('*.jsonl'):
 for line in log.read_text().splitlines():
  try:events.append(json.loads(line))
  except ValueError:pass
person=[e for e in events if e.get('operation')=='person_selection']
assert not any(e.get('stage')=='fallback' for e in person),person
assert any(e.get('device') in ('cuda','cuda:0') for e in person),person
assert any(e.get('person_frames',0)>0 for e in person),person
report={'accuracy':rows,'gpuPerson':{'durationS':60,'elapsedS':round(time.perf_counter()-start,3),'keptFrames':len(values),'ocr':'mock; integration only','events':person},'paidCalls':0}
(OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
