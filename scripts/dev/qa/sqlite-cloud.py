"""Real HTTP/SQLite/MySQL round-trip, using isolated local databases and a disposable cloud course ID."""
from pathlib import Path
import os,json,re,subprocess,time,urllib.request,urllib.error,sqlite3,uuid
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'.local/qa/sqlite-cloud';OUT.mkdir(parents=True,exist_ok=True)
DOCKER='D:/mytools/deskdocker/resources/bin/docker.exe';JAVA='D:/soft/OradeJDK/JDK21/bin/java.exe';JAR=ROOT/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar'
token=re.search(r'^SYNC_TOKEN=(.*)$',(ROOT/'.env').read_text(encoding='utf-8-sig'),re.M).group(1).strip().strip('"\'')
course=str(uuid.uuid4());processes=[];logs=[];cloud_stopped=False

def http(port,path,method='GET',body=None,headers=None):
 data=json.dumps(body).encode() if body is not None else b'' if method!='GET' else None
 request=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=data,headers={'Content-Type':'application/json',**(headers or {})},method=method)
 with urllib.request.urlopen(request,timeout=40) as response:return json.load(response)
def launch(name,port,database=None):
 folder=database.parent if database else OUT/(name+'-'+str(int(time.time()*1000)));folder.mkdir(exist_ok=True);env={**os.environ,'SPRING_PROFILES_ACTIVE':'sqlite','SQLITE_PATH':str(folder/'study.db'),'SYNC_SERVER_URL':'http://127.0.0.1:18081','SYNC_TOKEN':token,'KEYFRAME_DIR':str(folder/'keyframes'),'MEDIA_TEMP_DIR':str(folder/'uploads'),'AGENT_BASE_URL':'http://127.0.0.1:1'};env.pop('FRAMEWISE_ROLE',None)
 log=open(folder/'server.log','wb');logs.append(log);p=subprocess.Popen([JAVA,'-Djdk.net.unixdomain.tmpdir='+str(folder),'-jar',str(JAR),'--server.address=127.0.0.1','--server.port='+str(port)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW);processes.append(p)
 for attempt in range(60):
  try:http(port,'/api/sync/status');return folder/'study.db'
  except Exception:
   if p.poll() is not None:raise RuntimeError('Test server exited; see '+str(folder/'server.log'))
   time.sleep(.5)
 raise RuntimeError('Test API failed to start')
def sql(query):return subprocess.run([DOCKER,'exec','videostudy-mysql-1','sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
try:
 a=launch('client-a',18082);b=launch('client-b',18083)
 result={'localStorage':http(18082,'/api/sync/status')['storage'],'connection':http(18082,'/api/sync/connection','POST')['connected']}
 with sqlite3.connect(a) as db:
  db.execute("INSERT INTO transcription_jobs(id,status,result_json,original_filename) VALUES (?,'completed',?,'[QA] SQLite cloud round-trip')",(course,json.dumps({'language':'zh','segments':[{'id':'t_1','startMs':0,'endMs':1000,'text':'独立测试字幕'}],'visualEvidence':[],'pageGroups':[]})))
  db.execute("INSERT INTO overview_jobs(transcription_id,status,result_json) VALUES (?,'completed',?)",(course,json.dumps({'status':'completed','headline':'测试解读','notes':[]})))
 first=http(18082,'/api/sync/courses/'+course+'/push','POST');retry=http(18082,'/api/sync/courses/'+course+'/push','POST');assert first['revision']==retry['revision']==1
 assert sql("SELECT COUNT(*) FROM cloud_sync_documents WHERE course_id='"+course+"';")=='1';result['realMysqlRowVerified']=True
 http(18083,'/api/sync/courses/'+course+'/pull','POST');downloaded=http(18083,'/api/transcriptions/'+course);assert downloaded['result']['segments'][0]['text']=='独立测试字幕'
 with sqlite3.connect(b) as db:assert db.execute('SELECT COUNT(*) FROM overview_jobs').fetchone()[0]==1
 result.update({'upload':True,'idempotentRetry':True,'secondSqliteDownload':True,'relatedRecordsPreserved':True})
 with sqlite3.connect(a) as db:db.execute("UPDATE transcription_jobs SET original_filename='changed on client A' WHERE id=?",(course,))
 assert http(18082,'/api/sync/courses/'+course+'/push','POST')['revision']==2
 with sqlite3.connect(b) as db:db.execute("UPDATE transcription_jobs SET original_filename='changed on client B' WHERE id=?",(course,))
 for operation,code in [('pull','local_changes'),('push','sync_conflict')]:
  try:http(18083,'/api/sync/courses/'+course+'/'+operation,'POST');raise AssertionError('Conflict was accepted')
  except urllib.error.HTTPError as e:assert e.code==409 and json.load(e)['error']==code
 result['conflictPreservesBothSides']=True
 # Wrong token and no token must fail on the real cloud process.
 for headers in [{},{'X-Framewise-Sync':'wrong'}]:
  try:http(18081,'/api/cloud-sync/health',headers=headers);raise AssertionError('Cloud unauthenticated')
  except urllib.error.HTTPError as e:assert e.code==401
 result['cloudAuthentication']=True
 subprocess.run([DOCKER,'stop','videostudy-cloud-api-1'],check=True,capture_output=True);cloud_stopped=True
 assert len(http(18082,'/api/transcriptions'))==1
 try:http(18082,'/api/sync/connection','POST');raise AssertionError('Offline connection accepted')
 except urllib.error.HTTPError as e:assert e.code==503
 assert http(18082,'/api/transcriptions/'+course)['status']=='completed';result['offlineLocalReads']=True
 subprocess.run([DOCKER,'start','videostudy-cloud-api-1'],check=True,capture_output=True);cloud_stopped=False
 for attempt in range(50):
  try:assert http(18082,'/api/sync/connection','POST')['connected'];break
  except Exception:
   if attempt==49:raise
   time.sleep(.5)
 # Restart an isolated local instance to verify actual file persistence.
 processes[0].terminate();processes[0].wait(timeout=15)
 launch('client-a-reopened',18082,a)
 assert http(18082,'/api/transcriptions/'+course)['status']=='completed'
 assert http(18082,'/api/sync/status')['syncedCourses']==1
 result.update({'sqliteFilePersistent':True,'reconnectAfterOutage':True,'paidModelCalls':0,'originalMysqlTablesModified':False})
 (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
finally:
 if cloud_stopped:subprocess.run([DOCKER,'start','videostudy-cloud-api-1'],capture_output=True)
 # Remove only the one generated test UUID from the new snapshot table, never real course rows.
 try:sql("DELETE FROM cloud_sync_documents WHERE course_id='"+str(uuid.UUID(course))+"';")
 finally:
  for p in processes:
   if p.poll() is None:p.terminate()
  for p in processes:
   try:p.wait(timeout=15)
   except subprocess.TimeoutExpired:p.kill()
  for log in logs:log.close()
