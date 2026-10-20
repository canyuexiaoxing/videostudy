"""Authorized paid tests using ONLY synthetic in-script materials, no user courses/images."""
from pathlib import Path
import argparse,collections,json,os,sys,time,uuid
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
p=argparse.ArgumentParser();p.add_argument('--confirm-paid-calls',action='store_true');p.add_argument('--probe-growth',action='store_true');a=p.parse_args()
if not a.confirm_paid_calls:raise SystemExit('Authorization flag required')
# Read service credentials only. Never read any database, saved course, image, or user settings.
for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
 k,sep,v=line.strip().partition('=')
 if sep and k in ('DEEPSEEK_API_KEY','DEEPSEEK_BASE_URL','DEEPSEEK_MODEL') and not os.environ.get(k):os.environ[k]=v.strip().strip('\"\'')
from urllib.parse import urlparse
assert os.environ.get('DEEPSEEK_API_KEY')
assert urlparse(os.environ.get('DEEPSEEK_BASE_URL','https://api.deepseek.com')).hostname=='api.deepseek.com'
import practice
from practice import generate_practice,ask,validate_question
from model_diagnostics import close_logs
out=ROOT/'.local/qa/practice-delivery'/('synthetic-live-'+time.strftime('%Y%m%d-%H%M%S'));out.mkdir(parents=True)
os.environ['MODEL_LOG_DIR']=str(out/'logs')
materials={
 'growth':('增长量和增长率','本资料为测试现场编写。增长量=现期-基期；增长率=(现期-基期)/基期。基期为正；增长率以百分数表示。先算增长量，再除以基期。注意增长率与增长量单位不同。可比较不同对象的增长量与增长率，自设正数数据。'),
 'function':('二次函数图像与函数值','本资料为测试现场编写。二次函数y=a(x-h)^2+k，a不为0，顶点(h,k)，对称轴x=h。a>0开口向上，最小值k；a<0开口向下，最大值k。函数值代入x计算。零点由y=0求解；可分析单调区间、区间最大最小值和图像平移。所有运算使用实数。'),
 'circuit':('串并联电路和欧姆定律','本资料为测试现场编写。理想直流电路中U=IR。串联总电阻为各电阻之和，电流相同；并联各支路电压相同，1/R=1/R1+1/R2。功率P=UI=I^2R=U^2/R。电阻、电压为正，单位分别为欧姆、伏特，电流安培、功率瓦特。可自设明确的串联、并联或串并联条件，不考虑电源内阻。')}
plan=[('growth_basic','growth','basic','related_materials'),('growth_context_application','growth','application','map_context'),('function_advanced','function','advanced','related_materials'),('circuit_application','circuit','application','related_materials')]
if a.probe_growth:plan=plan[:1]
report={'materials':'synthetic_only_no_user_courses_or_images','startedAt':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'model':os.environ.get('DEEPSEEK_MODEL','deepseek-flash'),'maximumPaidCalls':12,'attemptedCalls':0,'recordsWritten':False,'cases':[]}
transport=practice.urlopen;calls=collections.Counter();active=None
# The only network destination is the configured official DeepSeek HTTPS endpoint.
def bounded(request,timeout):
 if report['attemptedCalls']>=12 or calls[active]>=3:raise RuntimeError('live_call_budget_exhausted')
 if urlparse(request.full_url).hostname!='api.deepseek.com':raise RuntimeError('unexpected_provider')
 report['attemptedCalls']+=1;calls[active]+=1
 print(json.dumps({'stage':'request_started','case':active,'call':report['attemptedCalls']}),flush=True)
 return transport(request,timeout=timeout)
practice.urlopen=bounded
start=time.monotonic();history=[]
def save():
 report['elapsedSeconds']=round(time.monotonic()-start,3);(out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
for name,topic,difficulty,mode in plan:
 active=name;t=time.monotonic();task=str(uuid.uuid4());title,lesson=materials[topic]
 ref={'sourceId':'t_1','sourceType':'transcript','startMs':0,'endMs':60000,'quote':lesson}
 node={'id':'n1','title':title,'evidenceRefs':[ref]}
 context={'knowledgeHierarchy':node,'referenceExamples':[],'speech':[{'id':'t_1','startMs':0,'endMs':60000,'text':lesson}],'ocr':[],'pageIndices':[],'_images':[],'_diagnosticTaskId':task}
 if mode=='map_context':context.update(systemText='根据给定模拟课程生成思维导图。',userText=lesson,assistantText=json.dumps({'root':node},ensure_ascii=False))
 case={'case':name,'taskId':task,'requested':10,'difficulty':difficulty,'mode':mode};report['cases'].append(case);batches=[]
 try:
  def provider(payload):
   value=ask(payload);batches.append(len(value.get('questions',[])))
   failures=[]
   for item in value.get('questions',[]):
    try:validate_question(item,[node])
    except Exception as error:
     calc=item.get('calculation') if isinstance(item,dict) else None
     failures.append({'errorType':type(error).__name__,'check':str(error)[:80],'expression':calc.get('expression') if isinstance(calc,dict) else None,'options':item.get('options') if isinstance(item,dict) else None})
   case.setdefault('failureExamples',[]).extend(failures[:3])
   return value
  result=generate_practice([node],[],10,difficulty,provider,mode=mode,context=context,history=history if name=='growth_context_application' else None,fill_missing=not a.probe_growth)
  qs=result['questions'];case.update(status=result['status'],firstReturned=batches[0],batchReturned=batches,accepted=len(qs),rejected=result['rejectedCount'],missing=result['shortfallCount'],fillAttempts=result['fillAttempts'],fillStatus=result['fillStatus'],calculationChecked=sum(q['validation']['calculationChecked'] for q in qs),calculationUnchecked=sum(q['validation'].get('calculationMissing',False) for q in qs),diagrams=dict(collections.Counter(q['diagram']['kind'] for q in qs if q.get('diagram'))),questionKinds=dict(collections.Counter(q['kind'] for q in qs)),historyQuestions=result['historyQuestions'])
  # Small generated excerpts for human inspection, never complete wire replies.
  case['reviewSamples']=[{'prompt':q['prompt'][:300],'options':[v[:100] for v in q['options']],'correctOption':q['options'][q['answerIndex']][:100],'explanationExcerpt':q['explanation'][:300]} for q in qs[:2]]
  if name=='growth_basic':history=[{'id':'synthetic-first','request':{'scopeTitle':title,'difficulty':difficulty,'count':10},'questions':qs}]
 except Exception as e:case.update(status='failed',errorType=type(e).__name__)
 logfile=out/'logs/model-events.jsonl';events=[json.loads(v) for v in logfile.read_text(encoding='utf-8').splitlines()] if logfile.exists() else [];events=[e for e in events if e.get('task')==task];responses=[e for e in events if e['event']=='response_received']
 case.update(calls=calls[name],seconds=round(time.monotonic()-t,3),formatRepair=sum(e['event']=='stage_started' and e.get('stage')=='reply_repair' for e in events),finishReasons=[e.get('finish_reason') for e in responses])
 case['usage']={k:sum(e[k] for e in responses) if responses and all(k in e for e in responses) else None for k in ('prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens')}
 case['rejectionReasons']=dict(collections.Counter(e.get('reason') for e in events if e['event']=='diagnostic_check' and e.get('stage') in ('validation','diagram_validation') and e.get('reason')!='practice_calculation_unchecked'))
 save();print(json.dumps({'stage':'case_completed',**{k:v for k,v in case.items() if k not in ('reviewSamples','failureExamples')}},ensure_ascii=False),flush=True)
close_logs();save();print(json.dumps({'stage':'completed','folder':str(out),'seconds':report['elapsedSeconds'],'calls':report['attemptedCalls']}),flush=True)
