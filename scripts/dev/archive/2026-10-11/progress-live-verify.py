import subprocess,json,time
from uuid import uuid4
from urllib.request import urlopen
from urllib.error import HTTPError,URLError
fid=str(uuid4())
def sql(query):
 command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
 return subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',command],text=True)
def python(code):
 subprocess.run(['docker','exec','-i','videostudy-agent-python-1','python','-B','-'],input=code,text=True,check=True)
for i in range(15):
 try:
  urlopen('http://127.0.0.1:18080/api/transcriptions/'+fid,timeout=2)
 except HTTPError as e:
  if e.code==404:break
  raise
 except (URLError,TimeoutError):
  if i==14:raise
  time.sleep(1)
try:
 sql(f"INSERT INTO transcription_jobs (id,status) VALUES ('{fid}','failed')")
 python(f"from pathlib import Path\nfrom analysis_progress import AnalysisProgress\np=AnalysisProgress(Path('/data/keyframes/{fid}/.analysis'))\np.enter('pages',3,20)\nfor i in range(8):p.unit_done(str(i),'pages')\n")
 with urlopen('http://127.0.0.1:18080/api/transcriptions/'+fid) as response:
  value=json.load(response)
 assert value['status']=='failed' and value['progress']['completedUnits']==8,value
 assert value['progress']['totalUnits']==20
 print('Live Python progress -> shared task directory -> Java GET passed')
finally:
 sql(f"DELETE FROM transcription_jobs WHERE id='{fid}'")
 python(f"from pathlib import Path\np=Path('/data/keyframes/{fid}/.analysis')\n(p/'progress.json').unlink(missing_ok=True)\nif p.exists():p.rmdir()\nif p.parent.exists():p.parent.rmdir()\n")
print('Temporary local QA record cleaned; no media analysis or model calls')
