"""Stage/deploy the bounded practice format repair, preserving data and previous images."""
from pathlib import Path
import argparse,json,subprocess,time,shutil,hashlib,urllib.request
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--docker',required=True);p.add_argument('--deploy',action='store_true');args=p.parse_args();proof=ROOT/'.local/qa/practice-format/build.json'
def run(*cmd,**kw):return subprocess.run([args.docker,*cmd],cwd=ROOT,check=True,**kw)
if not args.deploy:
 stamp=time.strftime('%Y%m%d%H%M%S');stage=ROOT/'.local/dev/practice-format'/stamp;images={}
 files={'agent-python':[(ROOT/'agent-python'/n,n,'/app/'+n) for n in ('practice_reply.py','practice.py','app.py','model_diagnostics.py','practice_diagrams.py')],'java-api':[(ROOT/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar','app.jar','/app/app.jar')]}
 for service,entries in files.items():
  old=run('inspect','--format','{{.Image}}','videostudy-'+service+'-1',capture_output=True,text=True).stdout.strip();folder=stage/service;folder.mkdir(parents=True)
  for source,name,dest in entries:shutil.copyfile(source,folder/name)
  base='videostudy-'+service+':practice-format-base-'+stamp;run('tag',old,base)
  (folder/'Dockerfile').write_text('FROM '+base+'\n'+''.join('COPY '+name+' '+dest+'\n' for source,name,dest in entries),encoding='utf8')
  tag='videostudy-'+service+':practice-format-'+stamp;run('build','--pull=false','-t',tag,str(folder));images[service]={'before':old,'staged':tag,'files':{dest:hashlib.sha256(source.read_bytes()).hexdigest() for source,name,dest in entries}}
 proof.write_text(json.dumps({'stage':str(stage),'images':images},indent=2));print('BUILD_PROOF '+str(proof))
else:
 data=json.loads(proof.read_text());stage=Path(data['stage']);images=data['images']
 # Query and back up local SQLite from Linux, consistent with the running backend's WAL locks.
 code='import sqlite3,json,time\nsource=sqlite3.connect("file:/db/framewise.db?mode=ro",uri=True,timeout=10)\ntables=["transcription_jobs","overview_jobs","chapter_jobs","subtitle_jobs","practice_sets"]\nactive=sum(source.execute("SELECT COUNT(*) FROM "+table+" WHERE status IN (?,?)",("queued","processing")).fetchone()[0] for table in tables)\nactive+=sum(source.execute("SELECT COUNT(*) FROM "+table+" WHERE lock_until>?",(time.time()*1000,)).fetchone()[0] for table in ["question_chat_threads","overview_chat_threads"])\nassert active==0,"Active local jobs prevent restart"\nsource.backup(sqlite3.connect("/qa/sqlite-before.db"))\nprint(json.dumps({"activeLocalJobs":active,"sqliteBackup":True}))\n'
 run('run','--rm','--network','none','-v',str(ROOT/'.local/database')+':/db:ro','-v',str(stage)+':/qa','--entrypoint','python',images['agent-python']['staged'],'-c',code)
 for status in (ROOT/'.local/uploads/compatibility').glob('*/status.json'):
  assert json.loads(status.read_text()).get('status') not in ('queued','processing'),'Active conversion prevents restart'
 for service,entry in images.items():
  current=run('inspect','--format','{{.Image}}','videostudy-'+service+'-1',capture_output=True,text=True).stdout.strip();assert current==entry['before'],'Service image changed since QA staging'
  run('tag',current,'videostudy-'+service+':before-practice-format-'+stage.name);run('tag',entry['staged'],'videostudy-'+service)
 cmd=['compose','-f','compose.yaml','-f','compose.gpu.yaml'];override=ROOT/'.local/dev/person-compose.yaml'
 if override.exists():cmd+=['-f',str(override)]
 run(*cmd,'up','-d','--no-build','--no-deps','agent-python','java-api')
 for attempt in range(60):
  try:
   with urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions',timeout=3) as r:assert r.status==200
   health=run('inspect','--format','{{.State.Health.Status}}','videostudy-agent-python-1',capture_output=True,text=True).stdout.strip()
   if health=='healthy':break
  except Exception:pass
  if attempt==59:raise RuntimeError('Updated backend not ready')
  time.sleep(1)
 for service,entry in images.items():
  for target,expected in entry['files'].items():assert run('exec','videostudy-'+service+'-1','sha256sum',target,capture_output=True,text=True).stdout.split()[0]==expected
 result={'deployedFilesMatch':True,'ready':True,'paidModelCalls':0,'sqliteBackup':str(stage/'sqlite-before.db'),'cloudDataChanged':False};(proof.parent/'deployment.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
