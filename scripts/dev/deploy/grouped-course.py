"""Deploy tested modules locally without model calls or historical reanalysis."""
from pathlib import Path
import subprocess,time,json,urllib.request
ROOT=Path(__file__).resolve().parents[3]
STAGE=ROOT/'.local/dev/grouped-course';STAGE.mkdir(parents=True,exist_ok=True)
def run(args):subprocess.run(args,cwd=ROOT,check=True)
query="SELECT (SELECT COUNT(*) FROM transcription_jobs WHERE status IN ('queued','processing')) + (SELECT COUNT(*) FROM overview_jobs WHERE status IN ('queued','processing')) + (SELECT COUNT(*) FROM chapter_jobs WHERE status IN ('queued','processing')) + (SELECT COUNT(*) FROM practice_sets WHERE status IN ('queued','processing'))"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
if subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',command],text=True).strip()!='0':raise RuntimeError('分析任务正在运行，不能重启')
subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python','videostudy-agent-python:latest','-c',"import av; assert 18 <= int(av.__version__.split('.')[0]) < 19 and hasattr(av.VideoFrame,'rotation'), 'Rebuild agent image with av>=18,<19'"],check=True)
modules=('agent_review.py','person_selection.py','person_mask_worker.py','analysis.py','analysis_progress.py','app.py','transcription.py','visual_evidence.py','frame_stream.py','slide_grouping.py','group_scheduler.py','group_understanding.py','grouped_analysis.py','course_mind_map.py','course_citations.py','course_json.py','course_outline.py','model_diagnostics.py','direct_analysis.py','direct_course_map.py','overview.py','map_conversation.py','practice_materials.py','practice_history.py','practice.py')
python=STAGE/'python';python.mkdir(exist_ok=True)
for name in modules:(python/name).write_bytes((ROOT/'agent-python'/name).read_bytes())
(python/'Dockerfile').write_text('FROM videostudy-agent-python:latest\nCOPY '+' '.join(modules)+' /app/\n')
java=STAGE/'java';java.mkdir(exist_ok=True)
(java/'app.jar').write_bytes((ROOT/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar').read_bytes())
(java/'Dockerfile').write_text('FROM videostudy-java-api:latest\nCOPY app.jar /app/app.jar\n')
run(['docker','build','--pull=false','-t','videostudy-agent-python',str(python)])
run(['docker','build','--pull=false','-t','videostudy-java-api',str(java)])
override=ROOT/'.local/dev/person-compose.yaml'
run(['docker','compose','-f','compose.yaml','-f','compose.gpu.yaml',*(['-f',str(override)] if override.is_file() else []),'up','-d','--no-build','--no-deps','agent-python','java-api'])
for attempt in range(55):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions',timeout=2) as reply:rows=json.load(reply)
  assert isinstance(rows,list)
  state=subprocess.check_output(['docker','inspect','--format','{{.State.Health.Status}}','videostudy-agent-python-1'],text=True).strip()
  if state=='healthy':break
 except Exception:pass
 if attempt==54:raise RuntimeError('Local service health timeout')
 time.sleep(1)
run(['docker','exec','videostudy-agent-python-1','python','-c','import grouped_analysis, group_understanding, course_mind_map; print(group_understanding.GROUP_PROMPT_VERSION, course_mind_map.PROMPT_VERSION)'])
print(json.dumps({'localServicesHealthy':True,'historyRecords':len(rows),'paidModelCalls':0}))
