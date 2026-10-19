"""Deploy math rendering and structured practice diagrams without running models or reanalysing saved courses."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,time,urllib.request
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--docker',required=True);p.add_argument('--java-only',action='store_true');a=p.parse_args()
def run(*cmd,**kw):return subprocess.run([a.docker,*cmd],cwd=ROOT,check=True,**kw)
query="SELECT "+" + ".join("(SELECT COUNT(*) FROM "+table+" WHERE status IN ('queued','processing'))" for table in ('transcription_jobs','overview_jobs','chapter_jobs','subtitle_jobs','practice_sets'))+" + (SELECT COUNT(*) FROM question_chat_threads WHERE lock_until>UNIX_TIMESTAMP(CURRENT_TIMESTAMP(3))*1000)"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
table_query="SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=0x"+'overview_chat_threads'.encode().hex()
table=run('exec','videostudy-mysql-1','sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+table_query+'"',capture_output=True,text=True).stdout.strip()
if table=='1':
 query+=" + (SELECT COUNT(*) FROM overview_chat_threads WHERE lock_until>UNIX_TIMESTAMP(CURRENT_TIMESTAMP(3))*1000)"
 command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
if run('exec','videostudy-mysql-1','sh','-c',command,capture_output=True,text=True).stdout.strip()!='0':raise RuntimeError('Active foreground jobs prevent restart')
for state in (ROOT/'.local/uploads/compatibility').glob('*/status.json'):
 if json.loads(state.read_text(encoding='utf-8')).get('status') in ('queued','processing'):raise RuntimeError('Active conversion prevents restart')
stamp=time.strftime('%Y%m%d%H%M%S');stage=ROOT/'.local/dev/math-figures'/stamp
files={'agent-python':[(ROOT/'agent-python'/name,name,'/app/'+name) for name in ('practice.py','practice_diagrams.py','question_chat.py','overview_chat.py','model_diagnostics.py')],'java-api':[(ROOT/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar','app.jar','/app/app.jar')]}
if a.java_only:files.pop('agent-python')
for service,entries in files.items():
 old=run('inspect','--format','{{.Image}}','videostudy-'+service+'-1',capture_output=True,text=True).stdout.strip()
 backup='videostudy-'+service+':before-math-figures-'+stamp;run('tag',old,backup)
 folder=stage/service;folder.mkdir(parents=True)
 for source,name,destination in entries:shutil.copyfile(source,folder/name)
 (folder/'Dockerfile').write_text('FROM '+backup+'\n'+''.join('COPY '+name+' '+destination+'\n' for source,name,destination in entries),encoding='utf-8')
 run('build','--pull=false','-t','videostudy-'+service,str(folder))
cmd=['compose','-f','compose.yaml','-f','compose.gpu.yaml'];override=ROOT/'.local/dev/person-compose.yaml'
if override.is_file():cmd+=['-f',str(override)]
run(*cmd,'up','-d','--no-build','--no-deps',*files)
for attempt in range(50):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions',timeout=2) as response:assert response.status==200
  state=run('inspect','--format','{{.State.Health.Status}}','videostudy-agent-python-1',capture_output=True,text=True).stdout.strip()
  if state=='healthy':break
 except Exception:pass
 if attempt==49:raise RuntimeError('Updated services not ready')
 time.sleep(1)
for service,entries in files.items():
 for source,name,destination in entries:
  actual=run('exec','videostudy-'+service+'-1','sha256sum',destination,capture_output=True,text=True).stdout.split()[0]
  assert actual==hashlib.sha256(source.read_bytes()).hexdigest()
print(json.dumps({'ready':True,'deployedFilesMatch':True,'paidModelCalls':0,'historyReanalysis':False}))
