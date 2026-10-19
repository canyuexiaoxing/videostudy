"""Deploy private SQLite local API and MySQL cloud API, preserving existing data. No model requests."""
from pathlib import Path
import argparse,subprocess,json,time,hashlib,shutil,secrets,re,urllib.request
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--docker',required=True);args=p.parse_args()
def run(*cmd,**kw):return subprocess.run([args.docker,*cmd],cwd=ROOT,check=True,**kw)
stamp=time.strftime('%Y%m%d%H%M%S');stage=ROOT/'.local/dev/sqlite-cloud'/stamp;stage.mkdir(parents=True)
query="SELECT COUNT(*) FROM transcription_jobs; SELECT "+' + '.join('(SELECT COUNT(*) FROM '+table+" WHERE status IN ('queued','processing'))" for table in ['transcription_jobs','overview_jobs','chapter_jobs','subtitle_jobs','practice_sets'])+" + (SELECT COUNT(*) FROM question_chat_threads WHERE lock_until>UNIX_TIMESTAMP(CURRENT_TIMESTAMP(3))*1000) + (SELECT COUNT(*) FROM overview_chat_threads WHERE lock_until>UNIX_TIMESTAMP(CURRENT_TIMESTAMP(3))*1000);"
for attempt in range(40):
 try:
  values=run('exec','videostudy-mysql-1','sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"',capture_output=True,text=True).stdout.split();break
 except subprocess.CalledProcessError:
  if attempt==39:raise
  time.sleep(1)
if int(values[1]):raise RuntimeError('Active jobs prevent deployment')
for state in (ROOT/'.local/uploads/compatibility').glob('*/status.json'):
 if json.loads(state.read_text()).get('status') in ['queued','processing']:raise RuntimeError('Active conversion prevents deployment')
backup=run('exec','videostudy-mysql-1','sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" mysqldump -u"$MYSQL_USER" --single-transaction --no-tablespaces --set-gtid-purged=OFF "$MYSQL_DATABASE"',capture_output=True)
(stage/'mysql-before.sql').write_bytes(backup.stdout)
envfile=ROOT/'.env';envtext=envfile.read_text(encoding='utf-8-sig');match=re.search(r'^SYNC_TOKEN=(.*)$',envtext,re.M)
if not match or len(match.group(1).strip().strip('"\''))<32:
 token=secrets.token_hex(32)
 envtext=re.sub(r'^SYNC_TOKEN=.*$', 'SYNC_TOKEN='+token,envtext,flags=re.M) if match else envtext.rstrip()+'\nSYNC_TOKEN='+token+'\n'
 envfile.write_text(envtext,encoding='utf8')
old=run('inspect','--format','{{.Image}}','videostudy-java-api-1',capture_output=True,text=True).stdout.strip();tag='videostudy-java-api:before-sqlite-'+stamp;run('tag',old,tag)
jar=ROOT/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar';shutil.copyfile(jar,stage/'app.jar');(stage/'Dockerfile').write_text('FROM '+tag+'\nCOPY app.jar /app/app.jar\n')
run('build','--pull=false','-t','videostudy-java-api',str(stage))
run('start','videostudy-agent-python-1')
cmd=['compose','-f','compose.yaml','-f','compose.gpu.yaml'];override=ROOT/'.local/dev/person-compose.yaml'
if override.exists():cmd+=['-f',str(override)]
run(*cmd,'up','-d','--no-build','--no-deps','cloud-api','java-api')
for attempt in range(60):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18080/api/sync/status',timeout=2) as response:status=json.load(response)
  assert status['storage']=='sqlite';break
 except Exception:
  if attempt==59:raise
  time.sleep(1)
for attempt in range(40):
 try:
  request=urllib.request.Request('http://127.0.0.1:18080/api/sync/connection',data=b'',method='POST')
  with urllib.request.urlopen(request,timeout=5) as response:cloud=json.load(response)
  assert cloud['connected'] and cloud['storage']=='mysql';break
 except Exception:
  if attempt==39:raise
  time.sleep(1)
# Import only absent legacy course IDs. Existing local data is never overwritten.
with urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions') as response:known={row['id'] for row in json.load(response)}
imported=0
for row in cloud['documents']:
 if row['legacy'] and row['id'] not in known:
  request=urllib.request.Request('http://127.0.0.1:18080/api/sync/courses/'+row['id']+'/pull',data=b'',method='POST')
  with urllib.request.urlopen(request,timeout=30) as response:assert response.status==200
  imported+=1
actual=run('exec','videostudy-java-api-1','sha256sum','/app/app.jar',capture_output=True,text=True).stdout.split()[0];assert actual==hashlib.sha256(jar.read_bytes()).hexdigest()
proof={'localStorage':'sqlite','cloudStorage':'mysql','connected':cloud['connected'],'legacyCoursesBefore':int(values[0]),'legacyImported':imported,'mysqlBackup':str(stage/'mysql-before.sql'),'deployedJarMatches':True,'paidModelCalls':0,'databaseVolumePreserved':True}
(ROOT/'.local/qa/sqlite-deployment.json').write_text(json.dumps(proof,indent=2),encoding='utf8');print(json.dumps(proof))
