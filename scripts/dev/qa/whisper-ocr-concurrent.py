"""Local small-GPU/OCR overlap smoke; no external AI or task/database writes."""
import sys,subprocess,threading,time,json
sys.path.insert(0,'/app')
if sys.argv[1]=='ocr':
 import cv2
 from visual_evidence import _ocr_model,_recognize
 image=cv2.imread(sys.argv[2]);assert image is not None
 _ocr_model();print('OCR_READY',flush=True)
 for _ in range(12):_recognize(image)
else:
 from transcription import transcription_config,_get_model
 from pathlib import Path
 import os
 readings=[];stopped=threading.Event()
 def monitor():
  while not stopped.is_set():
   result=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True)
   if result.returncode==0:readings.append(int(result.stdout.strip().splitlines()[0]))
   stopped.wait(.2)
 monitor_thread=threading.Thread(target=monitor);monitor_thread.start()
 worker=subprocess.Popen([sys.executable,__file__,'ocr',sys.argv[3]],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:
  while True:
   line=worker.stdout.readline()
   if not line:raise RuntimeError('OCR startup failed: '+worker.stderr.read()[-1000:])
   if 'OCR_READY' in line:break
  name,device,precision=transcription_config();assert(name,device)==('small','cuda')
  model=_get_model(str(Path(os.environ['MODEL_DIR'])/('faster-whisper-'+name)),device,precision)
  start=time.perf_counter();segments,info=model.transcribe(sys.argv[2],beam_size=5,vad_filter=True);segments=list(segments);seconds=time.perf_counter()-start
  stdout,stderr=worker.communicate(timeout=90)
  if worker.returncode:raise RuntimeError('Concurrent OCR failed: '+stderr[-1000:])
  print(json.dumps(dict(config=[name,device,precision],speechSeconds=round(seconds,3),speechSegments=len(segments),ocrFrames=12,totalGpuPeakMiB=max(readings) if readings else None,success=True)),flush=True)
 finally:
  if worker.poll() is None:worker.kill();worker.communicate()
  stopped.set();monitor_thread.join()
