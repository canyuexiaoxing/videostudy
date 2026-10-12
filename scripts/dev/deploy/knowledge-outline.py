from pathlib import Path
import subprocess,urllib.request,json,time
root=Path(__file__).resolve().parents[3];stage=root/'.local/dev/knowledge-outline/python';stage.mkdir(parents=True,exist_ok=True)
def run(args):subprocess.run(args,cwd=root,check=True)
query="SELECT COUNT(*) FROM transcription_jobs WHERE status IN ('queued','processing')"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
if subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',command],text=True).strip()!='0':raise RuntimeError('分析任务正在运行，不能重启')
for name in ('mind_map.py','knowledge_outline.py'):(stage/name).write_bytes((root/'agent-python'/name).read_bytes())
(stage/'Dockerfile').write_text('FROM videostudy-agent-python:latest'+chr(10)+'COPY mind_map.py knowledge_outline.py /app/'+chr(10))
run(['docker','build','--pull=false','-t','videostudy-agent-python',str(stage)])
run(['docker','compose','-f','compose.yaml','-f','compose.gpu.yaml','up','-d','--no-build','--no-deps','agent-python'])
for attempt in range(45):
 state=subprocess.check_output(['docker','inspect','--format','{{.State.Health.Status}}','videostudy-agent-python-1'],text=True).strip()
 if state=='healthy':break
 if attempt==44:raise RuntimeError('Agent health timeout')
 time.sleep(1)
run(['docker','cp',str(root/'agent-python/test_knowledge_outline.py'),'videostudy-agent-python-1:/tmp/test_knowledge_outline.py'])
run(['docker','exec','-e','PYTHONPATH=/app','videostudy-agent-python-1','python','-m','unittest','discover','-s','/tmp','-p','test_knowledge_outline.py','-q'])
print('Knowledge outline agent deployed and healthy')
