"""Deploy tested coarse-threshold defaults without starting any analysis."""
from pathlib import Path
import argparse,subprocess,shutil,time,json,urllib.request
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--docker',required=True);a=p.parse_args()
def run(*cmd,**kw):return subprocess.run([a.docker,*cmd],cwd=ROOT,check=True,**kw)
query="SELECT (SELECT COUNT(*) FROM transcription_jobs WHERE status IN ('queued','processing')) + (SELECT COUNT(*) FROM overview_jobs WHERE status IN ('queued','processing')) + (SELECT COUNT(*) FROM chapter_jobs WHERE status IN ('queued','processing')) + (SELECT COUNT(*) FROM practice_sets WHERE status IN ('queued','processing'))"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
if run('exec','videostudy-mysql-1','sh','-c',command,capture_output=True,text=True).stdout.strip()!='0':raise RuntimeError('Active tasks prevent service restart')
for service,image in [('java-api','videostudy-java-api'),('agent-python','videostudy-agent-python')]:
 old=run('inspect','--format','{{.Image}}','videostudy-'+service+'-1',capture_output=True,text=True).stdout.strip();run('tag',old,image+':before-coarse-threshold-20261018')
stage=ROOT/'.local/dev/coarse-threshold-java';stage.mkdir(parents=True,exist_ok=True)
shutil.copyfile(ROOT/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar',stage/'app.jar')
(stage/'Dockerfile').write_text('FROM videostudy-java-api:before-coarse-threshold-20261018\nCOPY app.jar /app/app.jar\n',encoding='utf-8')
run('build','--pull=false','-t','videostudy-java-api',str(stage))
subprocess.run([str(ROOT/'agent-python/.venv/Scripts/python.exe'),'-B',str(ROOT/'scripts/dev/deploy/person-selection.py'),'--mode','off','--docker',a.docker],cwd=ROOT,check=True)
run('compose','-f','compose.yaml','-f','compose.gpu.yaml','-f',str(ROOT/'.local/dev/person-compose.yaml'),'up','-d','--no-build','--no-deps','java-api')
for attempt in range(45):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions',timeout=2) as r:assert r.status==200
  break
 except Exception:
  if attempt==44:raise
  time.sleep(1)
print(json.dumps({'java_api_ready':True,'agent_updated':True,'default_percent':3,'added_options':[4,5],'paid_calls':0,'history_reanalysis':False}),flush=True)
