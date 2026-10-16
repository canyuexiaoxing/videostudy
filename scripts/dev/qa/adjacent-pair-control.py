"""Coarse-only control: same adjacent rule with no person masks/model."""
import os,sys,time,json,subprocess
from pathlib import Path
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).parent))
from adjacent_pair_selector import AdjacentPairSelector
out=Path('/out');out.mkdir(parents=True,exist_ok=True);selected=[];selector=AdjacentPairSelector(.02);start=time.perf_counter();i=0
with (out/'no-person-control-decode.log').open('wb') as log:
    proc=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-i','/video.mp4','-vf','fps=1/2,scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2,format=rgb24','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE,stderr=log)
    try:
        while True:
            raw=proc.stdout.read(320*180*3)
            if not raw:break
            if len(raw)!=320*180*3:raise RuntimeError('incomplete_frame')
            gray=cv2.cvtColor(np.frombuffer(raw,np.uint8).reshape(180,320,3),cv2.COLOR_RGB2GRAY)
            if selector.observe(gray,np.ones_like(gray,bool),np.zeros_like(gray,bool),i*2000):selected.append(i*2000)
            i+=1
        proc.wait();assert proc.returncode==0
    finally:
        if proc.poll() is None:proc.terminate();proc.wait()
if i and (not selected or selected[-1]!=(i-1)*2000):selected.append((i-1)*2000)
report={'strategy':'adjacent_no_person_masks','sample_frames':i,'candidate_count':len(selected),'seconds':round(time.perf_counter()-start,3),'timestamps_ms':selected,'scope':'coarse-only control, no YOLO/OCR/grouping; same adjacent threshold and final-frame rule'}
(out/'no-person-control.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='timestamps_ms'}),flush=True)
