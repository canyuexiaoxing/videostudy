"""Deploy persistent media identity; never invokes course analysis or models."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,time,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--docker',required=True);a=p.parse_args()
def run(*cmd,**kw):return subprocess.run([a.docker,*cmd],cwd=ROOT,check=True,**kw)
query="SELECT "+" + ".join("(SELECT COUNT(*) FROM "+table+" WHERE status IN ('queued','processing'))" for table in ('transcription_jobs','overview_jobs','chapter_jobs','subtitle_jobs','practice_sets'))+" + (SELECT COUNT(*) FROM question_chat_threads WHERE lock_until>UNIX_TIMESTAMP(CURRENT_TIMESTAMP(3))*1000)"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
if run('exec','videostudy-mysql-1','sh','-c',command,capture_output=True,text=True).stdout.strip()!='0':raise RuntimeError('Active tasks prevent restart')
stamp=time.strftime('%Y%m%d%H%M%S');stage=ROOT/'.local/dev/desktop-media'/stamp;stage.mkdir(parents=True)
source=ROOT/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar'
old=run('inspect','--format','{{.Image}}','videostudy-java-api-1',capture_output=True,text=True).stdout.strip()
backup='videostudy-java-api:before-desktop-media-'+stamp;run('tag',old,backup)
shutil.copyfile(source,stage/'app.jar');(stage/'Dockerfile').write_text('FROM '+backup+'\nCOPY app.jar /app/app.jar\n',encoding='utf-8')
run('build','--pull=false','-t','videostudy-java-api',str(stage))
cmd=['compose','-f','compose.yaml','-f','compose.gpu.yaml'];override=ROOT/'.local/dev/person-compose.yaml'
if override.is_file():cmd+=['-f',str(override)]
run(*cmd,'up','-d','--no-build','--no-deps','java-api')
for attempt in range(50):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions',timeout=2) as response:history=json.load(response)
  break
 except Exception:
  if attempt==49:raise
  time.sleep(1)
actual=run('exec','videostudy-java-api-1','sha256sum','/app/app.jar',capture_output=True,text=True).stdout.split()[0]
assert actual==hashlib.sha256(source.read_bytes()).hexdigest()
counts={'available':0,'originalUnavailable':0}
for item in history:
 try:
  with urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions/'+item['id']+'/media',timeout=10) as response:
   identity=json.load(response);assert identity['size']>=0 and len(identity['fingerprint'])==64;counts['available']+=1
 except urllib.error.HTTPError as error:
  if error.code!=410:raise
  counts['originalUnavailable']+=1
result={'ready':True,'deployedFileMatches':True,'historyMedia':counts,'paidModelCalls':0,'historyReanalysis':False}
(ROOT/'.local/qa/native-media/deployment.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
