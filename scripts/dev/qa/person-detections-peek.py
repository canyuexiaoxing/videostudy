"""Inspect positive person detections from sequentially decoded sparse video frames."""
import os,sys,json,subprocess
from pathlib import Path
import cv2,numpy as np
sys.path.insert(0,'/src/agent-python')
from person_selection import PersonMaskLease,shutdown_person_worker
os.environ['PERSON_SEGMENTATION']='auto';out=Path('/out');found=[];tiles=[]
with (out/'preview-decode.log').open('wb') as log:
    proc=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-i','/video.mp4','-vf','fps=1/30,scale=320:180','-f','rawvideo','-pix_fmt','bgr24','pipe:1'],stdout=subprocess.PIPE,stderr=log)
    try:
        with PersonMaskLease() as model:
            i=0
            while True:
                raw=proc.stdout.read(320*180*3)
                if not raw:break
                if len(raw)!=320*180*3:raise RuntimeError('incomplete_frame')
                frame=np.frombuffer(raw,np.uint8).reshape(180,320,3).copy();mask=model.predict(frame)
                if mask.any():
                    found.append({'sample_index':i,'approx_seconds':i*30,'pixels':int(mask.sum())})
                    if len(tiles)<12:
                        cv2.imwrite(str(out/f'positive-original-{i}.jpg'),frame)
                        frame[mask]=(frame[mask]*.45+np.array([0,150,255])*.55).astype(np.uint8)
                        tile=cv2.resize(frame,(640,360));cv2.putText(tile,f'~{i*30//60:02d}:{i*30%60:02d}',(10,25),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,0,255),2);tiles.append(tile)
                i+=1
        proc.wait();assert proc.returncode==0
    finally:
        if proc.poll() is None:proc.terminate();proc.wait()
        shutdown_person_worker()
if tiles:
    while len(tiles)%3:tiles.append(np.zeros_like(tiles[0]))
    cv2.imwrite(str(out/'positive-contact.jpg'),np.vstack([np.hstack(tiles[j:j+3]) for j in range(0,len(tiles),3)]))
(out/'positive-check.json').write_text(json.dumps({'samples':i,'positive_samples':found},indent=2));print(json.dumps({'samples':i,'positive_samples':found}),flush=True)
