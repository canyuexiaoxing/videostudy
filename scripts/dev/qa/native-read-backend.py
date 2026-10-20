from pathlib import Path
import os,sqlite3,json,socket,secrets,subprocess,time,urllib.request
ROOT=Path(__file__).resolve().parents[3];out=ROOT/'.local/qa/native-read-backend';out.mkdir(parents=True,exist_ok=True)
source=Path(os.environ['APPDATA'])/'Framewise/data/database/framewise.db';src=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);dst=sqlite3.connect(out/'snapshot.db');src.backup(dst);dst.close();course=src.execute('select id from transcription_jobs order by created_at desc limit 1').fetchone()[0];src.close()
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();origin=f'http://127.0.0.1:{port}';token=secrets.token_urlsafe(32)
env={**os.environ,'FRAMEWISE_RUNTIME_TOKEN':token,'SERVER_PORT':str(port),'SERVER_ADDRESS':'127.0.0.1','SPRING_PROFILES_ACTIVE':'sqlite','FRAMEWISE_ROLE':'local','SQLITE_PATH':str(out/'snapshot.db'),'MEDIA_TEMP_DIR':str(out/'uploads'),'KEYFRAME_DIR':str(out/'keyframes'),'AGENT_BASE_URL':'http://127.0.0.1:1','JAVA_INTERNAL_BASE_URL':origin,'DEEPSEEK_API_KEY':''}
for k in ['SPRING_DATASOURCE_URL','SPRING_DATASOURCE_PASSWORD','JAVA_TOOL_OPTIONS','_JAVA_OPTIONS']:env.pop(k,None)
log=(out/'java.log').open('w',encoding='utf-8');java=ROOT/'.local/native/runtime/java/bin/java.exe';jar=ROOT/'.local/native/runtime/app.jar'
process=subprocess.Popen([str(java),'-Xms64m','-Xmx512m','-Djdk.net.unixdomain.tmpdir='+str(ROOT/'.local/dev/sockets'),'-jar',str(jar)],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=0x08000000)
try:
 for i in range(100):
  if process.poll() is not None:raise RuntimeError('qa_java_exited')
  try:
   with urllib.request.urlopen(urllib.request.Request(origin+'/api/runtime/health',headers={'X-Framewise-Runtime':token}),timeout=1) as r:
    if r.status==200:break
  except Exception:time.sleep(.2)
 else:raise RuntimeError('qa_java_not_ready')
 report=[]
 for endpoint in ['/api/transcriptions','/api/transcriptions/'+course]:
  try:
   with urllib.request.urlopen(urllib.request.Request(origin+endpoint,headers={'X-Framewise-Runtime':token,'Origin':'app://framewise'}),timeout=8) as r:
    value=json.load(r);report.append({'httpStatus':r.status,'cors':r.headers.get('Access-Control-Allow-Origin'),'isArray':isinstance(value,list),'records':len(value) if isinstance(value,list) else None,'jobStatus':value.get('status') if isinstance(value,dict) else None})
  except Exception as e:report.append({'errorType':type(e).__name__,'httpStatus':getattr(e,'code',None)})
 print('direct',json.dumps(report),flush=True);(out/'direct-result.json').write_text(json.dumps(report,indent=2))
 eenv={**os.environ,'FRAMEWISE_QA_ORIGIN':origin,'FRAMEWISE_QA_CAPABILITY':token,'FRAMEWISE_QA_COURSE':course};eenv.pop('ELECTRON_RUN_AS_NODE',None)
 result=subprocess.run([str(ROOT/'desktop/node_modules/electron/dist/electron.exe'),str(ROOT/'scripts/dev/qa/native-read-backend.cjs')],env=eenv,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=30,creationflags=0x08000000)
 print('electron',result.stdout[:3000],flush=True)
finally:
 process.terminate();process.wait(timeout=15);log.close()
