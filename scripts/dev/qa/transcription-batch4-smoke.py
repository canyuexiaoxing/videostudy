"""Isolated local 90-second smoke of the production transcription entry point."""
from datetime import datetime,timezone
from pathlib import Path
import json,subprocess,urllib.request
ROOT=Path(__file__).resolve().parents[3]
rows=json.load(urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions'))
if any(r['status'] in ('queued','processing') for r in rows):raise RuntimeError('Course analysis active')
out=ROOT/'.local/qa'/('batch4-integration-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir(parents=True)
worker="""
import json,os,subprocess,time,uuid
from pathlib import Path
from transcription import transcribe_file,speech_checkpoint_key
from model_diagnostics import close_logs
root=Path('/tmp/uploads');root.mkdir();file_id=str(uuid.uuid4())
subprocess.run(['ffmpeg','-v','error','-i','/input/video.mp4','-t','90','-vn','-ar','16000','-ac','1','-f','wav',str(root/file_id)],check=True)
assert ':batch4:segment-timestamps' in speech_checkpoint_key(), 'Expected updated production batch4 module'
callbacks=[];started=time.monotonic();result=transcribe_file(file_id,callbacks.append)
assert result['segments'] and result['segments']==callbacks
assert all(0<=s['startMs']<=s['endMs']<=91000 for s in result['segments'])
report={'elapsedSeconds':round(time.monotonic()-started,3),'segments':len(callbacks),'checkpointKey':speech_checkpoint_key(),'callbacksMatch':True,'timestampsValid':True,'paidModelCalls':0}
close_logs();Path('/qa/result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
"""
args=['docker','run','--rm','--network','none','--gpus','all','--workdir','/source','--entrypoint','python',
 '-e','MEDIA_TEMP_DIR=/tmp/uploads','-e','MODEL_DIR=/models','-e','MODEL_LOG_DIR=/qa/logs','-e','WHISPER_MODEL=small','-e','WHISPER_DEVICE=cuda','-e','WHISPER_COMPUTE_TYPE=float16','-e','WHISPER_BATCH_SIZE=4',
 '-v',str(ROOT/'agent-python')+':/source:ro','-e','PYTHONPATH=/source',
 '-v',str(ROOT/'.local/models')+':/models:ro','-v',str(ROOT/'40ren.mp4')+':/input/video.mp4:ro','-v',str(out)+':/qa',
 'videostudy-agent-python:latest','-c',worker]
print('Smoke output: '+str(out),flush=True)
with (out/'console.log').open('w',encoding='utf-8') as log:subprocess.run(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
print((out/'result.json').read_text())
