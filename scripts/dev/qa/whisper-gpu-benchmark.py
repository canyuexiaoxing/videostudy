"""Compare local speech inference only; run inside the agent container with an audio path."""
import json,os,sys,time
from pathlib import Path
sys.path.insert(0,'/app')
from transcription import _get_model
root=Path(os.environ.get('MODEL_DIR','/models'))
audio=sys.argv[1]
for name,device,precision in (('base','cpu','int8'),('small','cuda','float16')):
 started=time.perf_counter();model=_get_model(str(root/('faster-whisper-'+name)),device,precision);load=time.perf_counter()-started
 for run in range(2):
  started=time.perf_counter();segments,info=model.transcribe(audio,beam_size=5,vad_filter=True);segments=list(segments);elapsed=time.perf_counter()-started
  print(json.dumps(dict(model=name,device=device,precision=precision,loadSeconds=round(load,3),run=run+1,inferenceSeconds=round(elapsed,3),language=info.language,segments=len(segments),firstText=segments[0].text if segments else ''),ensure_ascii=False),flush=True)
