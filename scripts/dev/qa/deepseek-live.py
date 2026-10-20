"""User-authorized paid integration tests. Synthetic material; no real course changes or raw provider logging."""
from pathlib import Path
import os,json,subprocess,time,uuid,urllib.request,urllib.error,sqlite3,shutil,math,re
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[3];DOCKER='D:/mytools/deskdocker/resources/bin/docker.exe';stamp=time.strftime('%Y%m%d-%H%M%S');RESUME=os.environ.get('FRAMEWISE_LIVE_QA_RESUME');OUT=ROOT/'.local/qa/deepseek-live'/stamp;OUT=Path(RESUME) if RESUME else OUT;OUT.mkdir(parents=True,exist_ok=True);(OUT/'database').mkdir(exist_ok=True);(OUT/'keyframes').mkdir(exist_ok=True);(OUT/'uploads').mkdir(exist_ok=True);shutil.copyfile(ROOT/'scripts/dev/qa/deepseek-live-agent.py',OUT/'agent_runner.py');(OUT/'current-case.json').write_text('{"name":"startup"}')
BASE='http://127.0.0.1:18082/api/transcriptions';agent_name='framewise-live-agent-'+stamp;java_name='framewise-live-api-'+stamp;env={**os.environ};containers=[];results=json.loads((OUT/'summary.json').read_text(encoding='utf8'))['cases'] if RESUME and (OUT/'summary.json').exists() else [];contexts={};client=str(uuid.uuid4());dbfile=OUT/'database/study.db'

def docker(*args,**kw):return subprocess.run([DOCKER,*args],cwd=ROOT,check=True,**kw)
def database(sql,params):
 code='import sqlite3,json,sys; p=json.load(sys.stdin); db=sqlite3.connect("/qa/database/study.db",timeout=30); c=db.execute(p["sql"],p["params"]); rows=c.fetchall(); db.commit(); print(json.dumps(rows,ensure_ascii=False))'
 output=docker('exec','-i',agent_name,'python','-c',code,input=json.dumps({'sql':sql,'params':params},ensure_ascii=False),capture_output=True,text=True)
 return json.loads(output.stdout)
def api(path='',method='GET',body=None,headers=None):
 data=json.dumps(body,ensure_ascii=False).encode() if body is not None else b'' if method!='GET' else None
 request=urllib.request.Request(BASE+path,data=data,headers={'Content-Type':'application/json',**(headers or {})},method=method)
 with urllib.request.urlopen(request,timeout=600) as response:return json.load(response)
def wait(path):
 for _ in range(300):
  value=api(path)
  if value.get('status') in ['completed','empty','failed','partial','unsupported']:return value
  time.sleep(.5)
 raise TimeoutError('job_poll_timeout')
def requests():
 file=OUT/'requests.jsonl';return [json.loads(line) for line in file.read_text().splitlines()] if file.exists() else []
def excerpt(value,limit=180):return value[:min(limit,max(0,len(value)//2))]
def run(name,callback):
 (OUT/'current-case.json').write_text(json.dumps({'name':name}));start=time.monotonic();before=len(requests());print('START '+name,flush=True)
 row={'case':name}
 try:row.update(callback());row.setdefault('success',True)
 except urllib.error.HTTPError as e:
  try:data=json.load(e);code=data.get('error') or data.get('detail')
  except Exception:code=None
  row.update(success=False,httpStatus=e.code,error=code or 'http_error')
 except Exception as e:row.update(success=False,errorType=type(e).__name__,error=str(e)[:160])
 results[:]=[previous for previous in results if previous['case']!=name]
 row['elapsedMs']=round((time.monotonic()-start)*1000);row['newProviderRequests']=len(requests())-before;results.append(row);
 with (OUT/'attempts.jsonl').open('a',encoding='utf8') as file:file.write(json.dumps(row,ensure_ascii=False)+'\n')
 save();print(json.dumps(row,ensure_ascii=False),flush=True)
def save():
 usage={};wire=requests()
 for key in ['prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens']:
  supplied=[row.get('usage',{}).get(key) for row in wire];usage[key]=sum(v for v in supplied if v is not None) if any(v is not None for v in supplied) else None
 (OUT/'summary.json').write_text(json.dumps({'cases':results,'providerRequests':wire,'usage':usage,'model':env.get('DEEPSEEK_MODEL'),'syntheticMaterials':True,'productionCoursesModified':False,'requestLimit':int(os.environ.get('FRAMEWISE_LIVE_LIMIT','20'))},ensure_ascii=False,indent=2),encoding='utf8')
def seed(topic,texts,lines,kind):
 course=str(uuid.uuid4());folder=OUT/'keyframes'/course;folder.mkdir();picture=np.full((600,1000,3),245,np.uint8)
 for i,line in enumerate(lines):cv2.putText(picture,line,(35,65+i*62),cv2.FONT_HERSHEY_SIMPLEX,.85,(20,25,40),2,cv2.LINE_AA)
 if kind=='geometry':
  pts=[(570,485),(870,485),(570,260)];cv2.polylines(picture,[np.array(pts)],True,(40,80,160),3);cv2.putText(picture,'A(0,0)',(555,520),0,.8,(0,0,0),2);cv2.putText(picture,'B(4,0)',(805,520),0,.8,(0,0,0),2);cv2.putText(picture,'C(0,3)',(560,245),0,.8,(0,0,0),2)
 if kind=='function':
  cv2.line(picture,(540,480),(950,480),(80,80,80),2);cv2.line(picture,(740,520),(740,240),(80,80,80),2);points=np.array([(round(740+x*55),round(480-x*x*25)) for x in np.linspace(-2.8,2.8,101)]);cv2.polylines(picture,[points],False,(160,60,10),3)
 if kind=='circuit':
  cv2.rectangle(picture,(580,280),(910,490),(70,70,70),3);cv2.rectangle(picture,(675,265),(745,295),(70,70,70),3);cv2.rectangle(picture,(780,265),(850,295),(70,70,70),3);cv2.putText(picture,'R1=4',(660,250),0,.8,(0,0,0),2);cv2.putText(picture,'R2=2',(785,250),0,.8,(0,0,0),2);cv2.putText(picture,'12V',(590,400),0,.8,(0,0,0),2)
 cv2.imwrite(str(folder/'1000.jpg'),picture)
 segments=[{'id':'s'+str(i+1),'startMs':i*10000,'endMs':(i+1)*10000,'text':text} for i,text in enumerate(texts)];end=len(segments)*10000
 refs=[{'sourceType':'transcript','sourceId':s['id'],'startMs':s['startMs'],'endMs':s['endMs'],'quote':s['text']} for s in segments]
 if kind!='text':refs.append({'sourceType':'image','sourceId':'frame_1000','startMs':1000,'endMs':1000,'quote':'课件截图'})
 node={'id':'n1','title':topic,'startMs':0,'endMs':end,'evidenceRefs':refs,'children':[],'details':[]};mindmap={'status':'completed','provider':'fixture','modelId':'synthetic','promptVersion':'qa','createdAt':'2026-10-19','root':{'id':'root','title':topic,'startMs':0,'endMs':end,'evidenceRefs':refs,'children':[node],'details':[]},'examples':[],'uncertainties':[]}
 understanding={'status':'completed','title':topic,'content':'；'.join(texts),'visualElements':[],'uncertainties':[]};visuals=[];pages=[]
 if kind!='text':
  blocks=[{'text':line,'score':1,'polygon':[[30,30+i*62],[950,30+i*62],[950,75+i*62],[30,75+i*62]]} for i,line in enumerate(lines)]
  visuals=[{'frameTimeMs':1000,'ocrBlocks':blocks,'imageAnalysis':understanding}];pages=[{'pageIndex':0,'firstFrameTimeMs':0,'lastFrameTimeMs':end,'memberFrameTimesMs':[1000],'representativeFrameTimesMs':[1000],'decision':'initial','decisionReason':'synthetic fixture','ocrLines':[{'text':line,'sourceFrameTimeMs':1000,'sourceBlockIndex':i} for i,line in enumerate(lines)],'imageAnalysis':understanding}]
 result={'language':'zh','segments':segments,'visualEvidence':visuals,'pageGroups':pages,'mindMap':mindmap,'visualAnalysisMode':'both','review':{'status':'completed','resampledTimesMs':[],'concerns':[]}}
 database("INSERT INTO transcription_jobs(id,status,result_json,original_filename,mind_map_mode) VALUES (?,'completed',?,?,'direct')",(course,json.dumps(result,ensure_ascii=False),'[QA] '+topic))
 contexts[kind]={'id':course,'segments':segments,'map':mindmap};return course

def practice(kind,mode='related_materials',difficulty='basic'):
 context=contexts[kind];course=context['id'];job=api('/'+course+'/practice','POST',{'nodeId':None,'count':3,'difficulty':difficulty,'mode':mode,'retry':True});sid=job['id'];result=wait('/'+course+'/practice/'+sid);context['setId']=sid
 if result['status']!='completed':return {'success':False,'status':result['status'],'error':result.get('error'),'rejectedCount':result.get('rejectedCount')}
 private=json.loads(database('SELECT result_json FROM practice_sets WHERE id=?',(sid,))[0][0])
 context['questions']=private['questions'];public=result.get('questions',[])
 return {'success':bool(public),'accepted':len(public),'requested':3,'rejected':result.get('rejectedCount'),'attachedImages':private.get('imageCount'),'samples':[{'title':q['title'],'prompt':q['prompt'][:240],'options':[option[:70] for option in q['options']],'answerIndex':private['questions'][i]['answerIndex'],'diagramKind':(q.get('diagram') or {}).get('kind'),'latex':bool(re.search(r'\\[\[(]|\$',q['prompt']))} for i,q in enumerate(public)]}
def chat_overview(message):
 course=contexts['growth']['id'];headers={'X-Study-Client':client};state=api('/'+course+'/overview/chat',headers=headers);reply=api('/'+course+'/overview/chat','POST',{'contextKey':state['contextKey'],'requestId':str(uuid.uuid4()),'message':message},headers);return {'success':True,'citations':len(reply.get('citations',[])),'contextMode':reply.get('contextMode'),'excerpt':excerpt(reply['reply']),'acknowledgesLimit':bool(re.search('不足|没有|未涉及|未讲|未出现',reply['reply']))}
def chat_question(kind,message):
 c=contexts[kind];course=c['id'];sid=c['setId'];q=c['questions'][0];headers={'X-Practice-Client':client}
 if not c.get('session'):
  session=api('/'+course+'/practice/'+sid+'/sessions','POST',{'fresh':False},headers);c['session']=session['id'];feedback=api('/'+course+'/practice/'+sid+'/sessions/'+session['id']+'/answers','POST',{'questionId':q['id'],'selectedIndex':(q['answerIndex']+1)%len(q['options'])},headers);c['wrongFeedback']=not feedback['correct']
 requestId=str(uuid.uuid4());body={'sessionId':c['session'],'requestId':requestId,'message':message};path='/'+course+'/practice/'+sid+'/questions/'+q['id']+'/chat';reply=api(path,'POST',body,headers);before=len(requests());cached=api(path,'POST',body,headers);assert cached==reply and len(requests())==before
 return {'success':True,'wrongAnswerFeedback':c['wrongFeedback'],'citations':len(reply.get('citations',[])),'excerpt':excerpt(reply['reply']),'idempotentRetryNoExtraModelCall':True}
try:
 environment=json.loads(docker('inspect','--format','{{json .Config.Env}}','videostudy-agent-python-1',capture_output=True,text=True).stdout)
 for setting in environment:
  key,_,value=setting.partition('=')
  if key.startswith('DEEPSEEK_'):env[key]=value
 assert env.get('DEEPSEEK_API_KEY')
 agent_image=docker('inspect','--format','{{.Image}}','videostudy-agent-python-1',capture_output=True,text=True).stdout.strip();java_image=docker('inspect','--format','{{.Image}}','videostudy-java-api-1',capture_output=True,text=True).stdout.strip();network=list(json.loads(docker('inspect','--format','{{json .NetworkSettings.Networks}}','videostudy-java-api-1',capture_output=True,text=True).stdout))[0]
 agent_image=os.environ.get('FRAMEWISE_LIVE_AGENT_IMAGE') or agent_image
 docker('run','-d','--name',agent_name,'--network',network,'-v',str(OUT)+':/qa','-v',str(ROOT/'.local/logs')+':/data/logs','-e','DEEPSEEK_API_KEY','-e','DEEPSEEK_MODEL','-e','DEEPSEEK_BASE_URL','-e','FRAMEWISE_LIVE_LIMIT','-e','KEYFRAME_DIR=/qa/keyframes','-e','MEDIA_TEMP_DIR=/qa/uploads','-e','MODEL_LOG_DIR=/data/logs','--entrypoint','python',agent_image,'/qa/agent_runner.py',env=env,capture_output=True);containers.append(agent_name)
 docker('run','-d','--name',java_name,'-v',str(ROOT/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar')+':/app/app.jar:ro','--network',network,'-p','127.0.0.1:18082:18080','-v',str(OUT)+':/qa','-e','SPRING_PROFILES_ACTIVE=sqlite','-e','FRAMEWISE_ROLE=local','-e','SQLITE_PATH=/qa/database/study.db','-e','KEYFRAME_DIR=/qa/keyframes','-e','MEDIA_TEMP_DIR=/qa/uploads','-e','AGENT_BASE_URL=http://'+agent_name+':8000',java_image,capture_output=True);containers.append(java_name)
 for agent_attempt in range(80):
  ready=subprocess.run([DOCKER,'exec',agent_name,'python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2)"],capture_output=True)
  if ready.returncode==0:break
  state=docker('inspect','--format','{{.State.Running}}',agent_name,capture_output=True,text=True).stdout.strip()
  if state!='true':raise RuntimeError('QA agent stopped during startup; see agent.log')
  if agent_attempt==79:raise TimeoutError('QA agent startup timeout')
  time.sleep(.5)
 for attempt in range(80):
  try:api();break
  except Exception:
   if attempt==79:raise
   time.sleep(.5)
 if RESUME:
  for course,filename in database('SELECT id,original_filename FROM transcription_jobs',[]):
   for kind,topic in [('growth','增长量'),('function','二次函数'),('geometry','直角三角形'),('circuit','串联电路'),('text','光合作用')]:
    if topic in filename:contexts[kind]={'id':course}
  growth=contexts['growth']['id']
 else:
  growth=seed('增长量与增长率：先量后率',['本课用先量后率的方法：先用现期减基期求增长量，再用增长量除以基期求增长率。','例如基期160，现期192，增长量是192减160等于32，增长率是32除以160等于百分之二十。','分母要用基期160，不能用现期192；这两者表示不同的比例。','图表中一月160、二月192，可以根据两期数据计算增加量和增长率。'],['BASE = 160; CURRENT = 192','INCREASE = 192 - 160 = 32','RATE = 32 / 160 = 20%','METHOD: difference first, ratio second'],'growth')
  seed('二次函数图像与函数值',['今天研究函数y等于x的平方，定义域为全体实数。','图像为开口向上的抛物线，顶点为原点，关于y轴对称。','求函数值时先找到横坐标，再代入平方，x等于2时y等于4。','图像上的点如零零、一一、二四都满足函数表达式。'],['y = x^2; x in R','Vertex O(0,0); symmetry: y-axis','f(2)=4; f(-2)=4'],'function')
  seed('直角三角形与勾股定理',['在直角三角形ABC中，A是直角，AB长4，AC长3。','老师的方法是先确认直角边和斜边，再用斜边平方等于两条直角边平方之和。','因此BC的平方等于4的平方加3的平方，等于25，BC等于5。','图中A坐标零零，B坐标四零，C坐标零三，不能把任意一条直角边当作斜边。'],['RIGHT TRIANGLE ABC; angle A=90 deg','A(0,0), B(4,0), C(0,3)','BC^2 = AB^2 + AC^2 = 4^2 + 3^2','BC = 5'],'geometry')
  seed('串联电路与欧姆定律',['这是理想直流串联电路，电源电压12伏，电阻R1为4欧，电阻R2为2欧。','老师先判断串联关系，将电阻相加得到总电阻6欧。','再用欧姆定律，总电流等于12除以6，等于2安，串联各处电流相等。','R1电压为8伏，R2电压为4伏，两者相加等于电源电压。'],['IDEAL DC SERIES CIRCUIT','V=12V; R1=4 ohm; R2=2 ohm','Rtotal=6 ohm; I=2 A','U1=8 V; U2=4 V'],'circuit')
  seed('光合作用基础',['绿色植物的光合作用需要光能。','本课介绍光合作用以二氧化碳和水为原料，生成有机物并释放氧气。','叶绿体是进行光合作用的重要场所，光能转化为化学能。'],[],'text')
  run('direct_map_with_image',lambda: {'success':(value:=api('/'+growth+'/mind-map?refresh=true&mindMapMode=direct','POST')).get('status')=='completed','status':value.get('status'),'topics':len(value.get('root',{}).get('children',[]))})
  run('overview_saved_sqlite',lambda:{'success':(value:=wait('/'+growth+'/overview')).get('status')=='completed','status':value.get('status'),'notes':len((value.get('result') or {}).get('notes',[]))})
  run('chapters',lambda:(api('/'+growth+'/chapters','POST'),{'success':(value:=wait('/'+growth+'/chapters')).get('status')=='completed','status':value.get('status'),'chapters':len((value.get('result') or {}).get('chapters',[]))})[1])
  for target in ['source','en']:
   def subtitles(target=target):
    api('/'+growth+'/subtitles','POST',{'targetLanguage':target});value=wait('/'+growth+'/subtitles?targetLanguage='+target);result=value.get('result') or {};return {'success':value['status']=='completed','status':value['status'],'segments':len(result.get('segments',[])),'changes':len(result.get('changes',[])),'rejected':result.get('rejectedCount'),'excerpt':excerpt((result.get('segments') or [{}])[0].get('text',''))}
   run('subtitle_'+target,subtitles)
 if os.environ.get('FRAMEWISE_LIVE_QA_PHASE')=='format':
  for kind in ['geometry','function','circuit']:run('format_practice_'+kind,lambda kind=kind:practice(kind))
  run('format_practice_original_conversation',lambda:practice('growth','map_context','application'))
 elif os.environ.get('FRAMEWISE_LIVE_QA_PHASE')=='focused':
  for kind,c in contexts.items():
   rows=database("SELECT id,result_json FROM practice_sets WHERE transcription_id=? AND status='completed' ORDER BY created_at DESC",[c['id']])
   for sid,result in rows:
    qs=json.loads(result).get('questions',[])
    if qs:c.update(setId=sid,questions=qs);break
  run('question_chat_wrong_answer',lambda:chat_question('function','我选错了，请按本课老师的方法分步讲，不要只给答案。'))
  run('question_chat_followup',lambda:chat_question('function','接着上一个问题，请用本课的具体数值举一个例子。'))
  run('question_chat_circuit_image',lambda:chat_question('circuit','请结合课件图解释串联电流相等，并按老师的方法计算总电流。'))
  run('practice_geometry_retry',lambda:practice('geometry'))
  run('overview_chat_missing_material_retry',lambda:chat_overview('老师这节课讲过复利计算公式吗？没有材料就明确说明，不能编造。'))
  run('practice_growth_related_materials',lambda:practice('growth'))
 else:
  run('practice_original_map_conversation',lambda:practice('growth','map_context','application'))
  for kind in ['function','geometry','circuit']:run('practice_'+kind+'_with_image',lambda kind=kind:practice(kind))
  run('practice_text_only',lambda:practice('text','legacy'))
  run('overview_chat_teacher_method',lambda:chat_overview('请按老师先量后率的方法解释，为何不能把增长量32直接说成增长率？'))
  run('overview_chat_missing_material',lambda:chat_overview('老师这节课讲过复利计算公式吗？没有材料就明确说明，不能编造。'))
  if contexts['growth'].get('questions'):
   run('question_chat_wrong_answer',lambda:chat_question('growth','我选错了，请按本课老师的方法分步讲，不要只给答案。'))
   run('question_chat_followup',lambda:chat_question('growth','接着刚才的解释，分母为什么用基期，不用现期？'))
  if contexts['geometry'].get('questions'):run('question_chat_geometry_image',lambda:chat_question('geometry','请结合课件图，指出直角和斜边，并用老师的勾股定理方法讲。'))
 # Repeated non-paid requests test persistence/idempotency at controller boundaries.
 run('repeat_overview_no_regeneration',lambda:{'success':bool(api('/'+growth+'/overview','POST'))})
 run('repeat_chapters_no_regeneration',lambda:{'success':bool(api('/'+growth+'/chapters','POST'))})
 save();print('OUTPUT '+str(OUT),flush=True)
finally:
 save()
 for name in containers:
  log=docker('logs',name,capture_output=True);(OUT/('agent.log' if name==agent_name else 'api.log')).write_bytes(log.stdout+log.stderr)
 for name in reversed(containers):subprocess.run([DOCKER,'rm','-f',name],capture_output=True)
 (ROOT/'.local/qa/deepseek-live/latest.json').write_text(json.dumps({'folder':str(OUT)},ensure_ascii=False))
