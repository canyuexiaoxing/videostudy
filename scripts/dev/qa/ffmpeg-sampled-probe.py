"""Probe actual PTS/rawvideo transport. Offline generated media only."""
import subprocess,av,tempfile,json
from pathlib import Path
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'offset.ts'
 subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=25:duration=5','-c:v','libx264','-g','250','-f','mpegts',str(p)],check=True)
 with av.open(str(p)) as c:origin=c.start_time/av.time_base
 expression=f"gte(t,{origin})*if(isnan(prev_selected_t),1,gt(floor((t-{origin})/2+0.0000001),floor((prev_selected_t-{origin})/2+0.0000001)))"
 command=['ffmpeg','-v','error','-copyts','-i',str(p),'-an','-vf','select='+expression.replace(',',r'\,'),'-fps_mode','passthrough','-c:v','rawvideo','-pix_fmt','bgr24','-f','nut','pipe:1']
 proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  with av.open(proc.stdout,format='nut') as out:
   rows=[{'pts':f.pts,'timeBase':str(f.time_base),'relativeMs':round((float(f.pts*f.time_base)-origin)*1000),'rotation':f.rotation} for f in out.decode(video=0)]
  code=proc.wait();assert code==0,proc.stderr.read().decode();print(json.dumps({'origin':origin,'frames':rows}))
 finally:
  if proc.poll() is None:proc.kill();proc.wait()
