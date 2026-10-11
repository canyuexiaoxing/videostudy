from pathlib import Path
import subprocess
root=Path(r'E:\workp\videostudy')
stage=Path(__file__).parent/'core-map-images'
def run(args):
 subprocess.run(args,cwd=root,check=True)
query='SELECT COUNT(*) FROM transcription_jobs WHERE status IN (\'queued\',\'processing\')'
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
active=subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',command],text=True).strip()
if active!='0': raise RuntimeError('当前有分析任务，暂不重启服务：'+active)
for name in ('python','java'): (stage/name).mkdir(parents=True,exist_ok=True)
for name in ('app.py','analysis.py','visual_evidence.py','slide_grouping.py','ignored_region.py','analysis_progress.py','mind_map.py'):
 (stage/'python'/name).write_bytes((root/'agent-python'/name).read_bytes())
(stage/'python/Dockerfile').write_text('FROM videostudy-agent-python:latest\nCOPY app.py analysis.py visual_evidence.py slide_grouping.py ignored_region.py analysis_progress.py mind_map.py /app/\n')
(stage/'java/app.jar').write_bytes((root/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar').read_bytes())
(stage/'java/Dockerfile').write_text('FROM videostudy-java-api:latest\nCOPY app.jar /app/app.jar\n')
for name,tag in (('python','videostudy-agent-python'),('java','videostudy-java-api')):
 run(['docker','build','--pull=false','-t',tag,str(stage/name)])
run(['docker','compose','-f','compose.yaml','-f','compose.gpu.yaml','up','-d','--no-build','--no-deps','agent-python','java-api'])
