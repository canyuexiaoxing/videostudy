"""Run inside deployed service via stdin; generated media, no model requests."""
import tempfile,subprocess,json
from pathlib import Path
import av,numpy as np
from frame_stream import FRAME_PIPELINE_VERSION,accurate_frames
from visual_evidence import analyze_visuals
with tempfile.TemporaryDirectory() as d:
 root=Path(d);video=root/'fixture.ts';frames=root/'frames';events=[]
 subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=25:duration=3','-c:v','libx264','-g','250','-f','mpegts',str(video)],check=True)
 def published(value):
  assert (frames/(str(value['frameTimeMs'])+'.jpg')).is_file()
  events.append(value)
 rows=analyze_visuals(video,keyframe_dir=frames,recognize=lambda image:[],on_frame=published,person_selection_mode='off')
 assert len(rows)>=2 and len(rows)==len(events)
 for row in rows:
  actual,image=next(accurate_frames(video,[row['frameTimeMs']]))
  assert actual==row['frameTimeMs']
 print(json.dumps({'pipeline':FRAME_PIPELINE_VERSION,'av':av.__version__,'savedBeforeCallback':True,'times':[v['frameTimeMs'] for v in rows],'paidCalls':0}))
