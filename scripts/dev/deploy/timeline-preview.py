"""Deploy the read-only preview idle gate; local thumbnail generation stays client-side."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,time,urllib.request
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--docker',required=True);a=p.parse_args()
def run(*cmd,**kw):return subprocess.run([a.docker,*cmd],cwd=ROOT,check=True,**kw)
query="SELECT "+" + ".join("(SELECT COUNT(*) FROM "+table+" WHERE status IN ('queued','processing'))" for table in ('transcription_jobs','overview_jobs','chapter_jobs','subtitle_jobs','practice_sets'))+" + (SELECT COUNT(*) FROM question_chat_threads WHERE lock_until>UNIX_TIMESTAMP(CURRENT_TIMESTAMP(3))*1000)"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
if run('exec','videostudy-mysql-1','sh','-c',command,capture_output=True,text=True).stdout.strip()!='0':raise RuntimeError('Active foreground jobs prevent restart')
for state in (ROOT/'.local/uploads/compatibility').glob('*/status.json'):
 if json.loads(state.read_text(encoding='utf-8')).get('status') in ('queued','processing'):raise RuntimeError('Active conversion prevents restart')
old=run('inspect','--format','{{.Image}}','videostudy-java-api-1',capture_output=True,text=True).stdout.strip();run('tag',old,'videostudy-java-api:before-timeline-preview-20261018')
stage=ROOT/'.local/dev/timeline-preview-java';stage.mkdir(parents=True,exist_ok=True)
jar=ROOT/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar';shutil.copyfile(jar,stage/'app.jar')
(stage/'Dockerfile').write_text('FROM videostudy-java-api:before-timeline-preview-20261018\nCOPY app.jar /app/app.jar\n',encoding='utf-8')
run('build','--pull=false','-t','videostudy-java-api',str(stage))
run('compose','-f','compose.yaml','-f','compose.gpu.yaml','-f',str(ROOT/'.local/dev/person-compose.yaml'),'up','-d','--no-build','--no-deps','java-api')
for attempt in range(45):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions',timeout=2) as r:assert r.status==200
  break
 except Exception:
  if attempt==44:raise
  time.sleep(1)
actual=run('exec','videostudy-java-api-1','sha256sum','/app/app.jar',capture_output=True,text=True).stdout.split()[0]
assert actual==hashlib.sha256(jar.read_bytes()).hexdigest()
print(json.dumps({'javaReady':True,'jarMatches':True,'paidCalls':0,'historyReanalysis':False,'generationLocation':'client-device'}))
