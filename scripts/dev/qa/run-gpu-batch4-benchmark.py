"""Launch an isolated offline benchmark using project-owned media and models."""
from pathlib import Path
from datetime import datetime,timezone
import json,subprocess,urllib.request,argparse
ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser();parser.add_argument('--reference');parser.add_argument('--timestamps',action='store_true');options=parser.parse_args()
reference=Path(options.reference).resolve() if options.reference else None
if reference and (not reference.is_relative_to(ROOT/'.local/qa') or not (reference/'results.json').is_file()):raise ValueError('Invalid local QA reference folder')
rows=json.load(urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions'))
if any(r['status'] in ('queued','processing') for r in rows):raise RuntimeError('A course analysis is active; benchmark must wait')
chosen=None
for row in rows:
 if row.get('name')!='40ren.mp4' or row['status']!='completed':continue
 result=json.load(urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions/'+row['id'])).get('result') or {}
 times=[v['frameTimeMs'] for v in result.get('visualEvidence') or []]
 folder=ROOT/'.local/keyframes'/row['id']
 if times and all((folder/f'{t}.jpg').is_file() for t in times):chosen=(row['id'],times,folder);break
if not chosen:raise RuntimeError('Existing OCR frames unavailable')
course,times,frames=chosen
output=ROOT/'.local/qa'/('batch4-benchmark-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));output.mkdir(parents=True)
(output/'manifest.json').write_text(json.dumps({'courseId':course,'frameTimesMs':times}),encoding='utf-8')
args=['docker','run','--rm','--name','videostudy-batch4-benchmark','--network','none','--gpus','all','--entrypoint','python',
 '-e','MODEL_DIR=/models','-e','OCR_DEVICE=gpu:0','-e','PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True','-e','QA_BENCH_OUT=/bench','-e','QA_BENCH_VIDEO=/input/video.mp4','-e','QA_BENCH_FRAMES=/frames',
 '-v',str(ROOT/'.local/models')+':/models:ro','-v',str(ROOT/'40ren.mp4')+':/input/video.mp4:ro','-v',str(frames)+':/frames:ro','-v',str(ROOT/'scripts/dev/qa')+':/source/scripts/dev/qa:ro','-v',str(output)+':/bench',
 *(['-e','QA_BENCH_TIMESTAMPS=1'] if options.timestamps else []),*(['-e','QA_BENCH_REFERENCE=/reference','-v',str(reference)+':/reference:ro'] if reference else []),
 'videostudy-agent-python:latest','/source/scripts/dev/qa/gpu-batch4-benchmark.py']
print('Benchmark output: '+str(output),flush=True)
with (output/'console.log').open('w',encoding='utf-8') as log:
 process=subprocess.Popen(args,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
 for line in process.stdout:
  log.write(line);log.flush()
  if line.startswith('{'):print(line.rstrip(),flush=True)
 code=process.wait()
if code:raise SystemExit(code)
print('Benchmark finished: '+str(output/'results.json'),flush=True)
