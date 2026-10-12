from pathlib import Path
import subprocess,urllib.request,json,time
root=Path(__file__).resolve().parents[3];stage=root/'.local/dev/history-sync/java';stage.mkdir(parents=True,exist_ok=True)
def run(args):subprocess.run(args,cwd=root,check=True)
query="SELECT COUNT(*) FROM transcription_jobs WHERE status IN ('queued','processing')"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
active=subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',command],text=True).strip()
if active!='0':raise RuntimeError('分析任务正在运行，不能重启: '+active)
(stage/'app.jar').write_bytes((root/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar').read_bytes())
(stage/'Dockerfile').write_text('FROM videostudy-java-api:latest'+chr(10)+'COPY app.jar /app/app.jar'+chr(10))
run(['docker','build','--pull=false','-t','videostudy-java-api',str(stage)])
run(['docker','compose','-f','compose.yaml','-f','compose.gpu.yaml','up','-d','--no-build','--no-deps','java-api'])
for attempt in range(45):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions',timeout=2) as reply:rows=json.load(reply)
  assert isinstance(rows,list);print('History endpoint healthy: '+str(len(rows))+' server records');break
 except Exception:
  if attempt==44:raise
  time.sleep(1)
