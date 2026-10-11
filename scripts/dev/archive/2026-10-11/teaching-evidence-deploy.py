from pathlib import Path
import subprocess
root=Path(r'E:\workp\videostudy')
stage=Path(__file__).parent/'teaching-evidence-image'
stage.mkdir(exist_ok=True)
query="SELECT COUNT(*) FROM transcription_jobs WHERE status IN ('queued','processing')"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
active=subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',command],text=True).strip()
if active!='0': raise RuntimeError('存在进行中的分析任务，暂不重启：'+active)
(stage/'mind_map.py').write_bytes((root/'agent-python/mind_map.py').read_bytes())
(stage/'Dockerfile').write_text('FROM videostudy-agent-python:latest\nCOPY mind_map.py /app/mind_map.py\n')
subprocess.run(['docker','build','--pull=false','-t','videostudy-agent-python',str(stage)],cwd=root,check=True)
subprocess.run(['docker','compose','-f','compose.yaml','-f','compose.gpu.yaml','up','-d','--no-build','--no-deps','agent-python'],cwd=root,check=True)
