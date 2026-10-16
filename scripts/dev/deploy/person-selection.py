"""Deploy optional person filtering using the already-tested local runtime."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,time,urllib.request
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['off','auto','cpu','cuda'],default='off');p.add_argument('--docker',default='docker');args=p.parse_args()
def run(*cmd,**kw):return subprocess.run([args.docker,*cmd],cwd=ROOT,check=True,**kw)
query="SELECT (SELECT COUNT(*) FROM transcription_jobs WHERE status IN ('queued','processing')) + (SELECT COUNT(*) FROM overview_jobs WHERE status IN ('queued','processing')) + (SELECT COUNT(*) FROM chapter_jobs WHERE status IN ('queued','processing')) + (SELECT COUNT(*) FROM practice_sets WHERE status IN ('queued','processing'))"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
if run('exec','videostudy-mysql-1','sh','-c',command,capture_output=True,text=True).stdout.strip()!='0':raise RuntimeError('Active tasks prevent service restart')
run('run','--rm','--network','none','--entrypoint','python','videostudy-agent-python:latest','-c',"import av; assert 18 <= int(av.__version__.split('.')[0]) < 19 and hasattr(av.VideoFrame,'rotation'), 'Rebuild agent image with av>=18,<19'")
model=ROOT/'.local/models/yolo26/yolo26n-seg.pt';runtime=ROOT/'.local/dev/yolo-runtime/venv'
if not runtime.is_dir() or hashlib.sha256(model.read_bytes()).hexdigest()!='361fbfabab285c3237700b6bb91d7ecfa602cd945fffda8dbe1242829b71e73f':raise RuntimeError('Verified local model/runtime unavailable; use the documented clean Docker build')
stage=ROOT/'.local/dev/person-deploy';stage.mkdir(parents=True,exist_ok=True)
modules=[f.name for f in (ROOT/'agent-python').glob('*.py') if not f.name.startswith('test_')]
for name in modules:shutil.copyfile(ROOT/'agent-python'/name,stage/name)
probe=run('run','--rm','--network','none','--entrypoint','python','videostudy-agent-python:latest','-c',"from pathlib import Path; import json; print(json.dumps([Path('/opt/person-cuda/nvidia/cublas/lib').is_dir(),Path('/opt/person-cuda/nvidia/cusparselt/lib/libcusparseLt.so.0').is_file()]))",capture_output=True,text=True)
has_nvidia,has_cusparselt=json.loads(probe.stdout)
libraries=('' if has_nvidia else 'COPY --from=person-cuda /usr/local/lib/python3.11/site-packages/nvidia/ /opt/person-cuda/nvidia/\n')+('' if has_cusparselt else 'COPY --from=person-cuda /usr/local/lib/python3.11/site-packages/cusparselt/ /opt/person-cuda/nvidia/cusparselt/\n')
(stage/'Dockerfile').write_text(('FROM videostudy-agent-python:gpu-base AS person-cuda\n' if libraries else '')+'FROM videostudy-agent-python:latest\n'+libraries+'COPY '+' '.join(modules)+' /app/\n')
run('build','--pull=false','-t','videostudy-agent-python',str(stage))
override=ROOT/'.local/dev/person-compose.yaml'
override.write_text('services:\n  agent-python:\n    environment:\n      PERSON_SEGMENTATION: '+json.dumps(args.mode)+'\n      PERSON_PYTHON: /opt/person/bin/python\n    volumes:\n      - ./.local/dev/yolo-runtime/venv:/opt/person:ro\n')
run('compose','-f','compose.yaml','-f','compose.gpu.yaml','-f',str(override),'up','-d','--no-build','--no-deps','agent-python')
for attempt in range(60):
 state=run('inspect','--format','{{.State.Health.Status}}','videostudy-agent-python-1',capture_output=True,text=True).stdout.strip()
 if state=='healthy':break
 if attempt==59:raise RuntimeError('Service health timeout')
 time.sleep(1)
run('exec','videostudy-agent-python-1','python','-c','from person_selection import settings; s=settings(); print({"mode":s["mode"],"runtime":s["python"],"model":s["model"]})')
print(json.dumps({'healthy':True,'personSegmentation':args.mode,'historyReanalysis':False,'paidCalls':0}))
