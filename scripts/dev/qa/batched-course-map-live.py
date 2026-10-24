"""Live comparison on a saved long course; explicit opt-in, no database writes.
Only metadata and transformed final maps are saved. No raw requests/replies/keys.
"""
from pathlib import Path
import argparse,copy,hashlib,json,os,sqlite3,sys,time,uuid
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import URLError,HTTPError
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
import course_mind_map as course
import model_diagnostics as diagnostics
from direct_course_map import _prepare
from course_citations import wire_registry,translate_references
from course_json import parse_course_json
from experimental_batched_map import run_batched,validate_plan

def configured_api(data):
 """Use the project's existing authorized test API key, in memory only."""
 settings=json.loads((data/'settings.json').read_text(encoding='utf-8-sig'));values={}
 for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
  if line.strip() and not line.lstrip().startswith('#') and '=' in line:
   name,value=line.split('=',1)
   if name.strip()=='DEEPSEEK_API_KEY':values[name.strip()]=value.strip().strip(chr(34)).strip(chr(39))
 key=values.get('DEEPSEEK_API_KEY','')
 if not key or key.startswith('${'):raise RuntimeError('project_test_api_key_missing')
 return key,settings['deepseek']

def metrics(raw,final):
 def walk(nodes,depth=1):
  for node in nodes:
   yield node,depth
   yield from walk(node.get('children',[]),depth+1)
 nodes=list(walk(raw.get('children',[])));refs=[ref for node,_ in nodes for ref in node.get('sourceIds',[])+node.get('imageIds',[])];details=[d for node,_ in nodes for d in node.get('details',[])];examples=raw.get('examples',[])
 for item in details+examples:refs+=item.get('sourceIds',[])+item.get('imageIds',[])
 return {'status':final['status'],'modules':len(raw.get('children',[])),'knowledgeNodes':len(nodes),'details':len(details),'examples':len(examples),'maxDepth':max((depth for _,depth in nodes),default=0),'citedImages':len({r for r in refs if r.startswith('frame_')}),'citedTranscriptSegments':len({r for r in refs if r.startswith('t_')}),'uncertaintyCount':len(final.get('uncertainties',[])),'mapCharacters':len(json.dumps(raw,ensure_ascii=False))}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--task',required=True);parser.add_argument('--allow-real-api',action='store_true');parser.add_argument('--dry-run',action='store_true');parser.add_argument('--baseline-report',type=Path);parser.add_argument('--baseline-only',action='store_true');parser.add_argument('--expected-input-sha256');args=parser.parse_args();uuid.UUID(args.task)
 if not args.allow_real_api and not args.dry_run:raise RuntimeError('explicit_real_api_flag_required')
 started=time.monotonic();data=Path(os.environ['APPDATA'])/'Framewise/data';key,settings=configured_api(data)
 os.environ.update(DEEPSEEK_API_KEY=key,DEEPSEEK_MODEL=settings['model'],DEEPSEEK_BASE_URL=settings['baseUrl'],MODEL_LOG_DIR=str(ROOT/'.local/logs'))
 db=sqlite3.connect((data/'database/framewise.db').as_uri()+'?mode=ro',uri=True)
 row=db.execute('select original_filename,result_json,ignored_region_json from transcription_jobs where id=?',(args.task,)).fetchone();db.close()
 if not row:raise RuntimeError('saved_course_missing')
 saved=json.loads(row[1]);payload,images,hashes=_prepare(saved['segments'],saved['pageGroups'],saved['visualEvidence'],data/'keyframes'/args.task,json.loads(row[2]) if row[2] else None)
 base=None
 class Captured(BaseException):pass
 def capture(request,*a,**kw):
  nonlocal base
  base=json.loads(request.data);raise Captured()
 try:
  with patch.object(course,'request_model_json',capture):course._deepseek_course_json(payload,images)
 except Captured:pass
 if base is None:raise RuntimeError('request_capture_failed')
 wire,aliases=wire_registry(payload);allowed_sources={r['sourceId'] for r in payload['sourceEvidence']};allowed_images=set(aliases)
 source_fingerprint=hashlib.sha256(json.dumps(base['messages'][:2],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 if args.expected_input_sha256 and source_fingerprint!=args.expected_input_sha256:raise RuntimeError('saved_input_hash_mismatch')
 run_id='2026-10-21-'+time.strftime('%H%M%S')+'-'+uuid.uuid4().hex[:6];out=ROOT/'.local/qa/batched-course-map'/run_id;out.mkdir(parents=True)
 report={'task':args.task,'filename':row[0],'startedAtUtc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'durationSeconds':max(s['endMs'] for s in saved['segments'])/1000,'transcriptSegments':len(saved['segments']),'representativeImages':len(images),'originalInputSha256':source_fingerprint,'model':settings['model'],'credentialSource':'existing_project_test_configuration','productionModeChanged':False,'databaseWritten':False,'paidCallsAllowed':args.allow_real_api,'calls':[],'state':'prepared','outputDirectory':str(out)}
 def save():
  report['elapsedSeconds']=round(time.monotonic()-started,3);(out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  (ROOT/'.local/qa/batched-course-map/latest.json').write_text(json.dumps({'directory':str(out)},indent=2)+'\n',encoding='utf8')
 save();print(json.dumps({'stage':'prepared','task':args.task,'durationSeconds':report['durationSeconds'],'segments':report['transcriptSegments'],'images':len(images),'keyAvailable':True,'outputDirectory':str(out)}),flush=True)
 if args.dry_run:return
 diagnostics._OPERATIONS.add('course_map_batch_experiment')
 current=None;phase='baseline';batch_index=0;original_event=diagnostics.record_event
 def observe(event,task='unbound',**fields):
  original_event(event,task,**fields)
  nonlocal current
  if event=='request_started':
   if len(report['calls'])>=32:raise RuntimeError('experiment_call_budget_exceeded')
   current={'phase':phase,'batch':batch_index,'requestId':fields.get('request_id'),'imageCount':fields.get('image_count'),'inputCharacters':fields.get('input_characters'),'maxOutputTokens':fields.get('max_output_tokens'),'state':'started'};report['calls'].append(current);save();print(json.dumps({'stage':'request_started','phase':phase,'batch':batch_index,'call':len(report['calls'])}),flush=True)
  if current is not None and event in ('response_received','request_failed','request_completed'):
   for name in ['elapsed_ms','finish_reason','response_characters','prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens','http_status','error_type','reason','json_position']:
    if name in fields:current[name]=fields[name]
   current['state']=event;save()
   if event in ('request_completed','request_failed'):print(json.dumps({'stage':event,'phase':phase,'batch':batch_index,'seconds':round(fields.get('elapsed_ms',0)/1000,3),'errorType':fields.get('error_type')}),flush=True)
 opener=build_opener(ProxyHandler({}))
 def transport(request,timeout=300):
  response=opener.open(request,timeout=timeout)
  if current is not None:current['http_status']=response.status
  return response
 def finalize(raw,label):
  final=course.finalize_course_reply(raw,payload,'experimental-batches-v1' if label=='batched' else course.PROMPT_VERSION,diagnostic_root=out/label)
  # Transformed user-facing result, never the raw provider envelope or prompt.
  (out/(label+'-map.json')).write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  return metrics(raw,final)
 diagnostics.record_event=observe
 try:
  report['state']='baseline_running';save();before=time.monotonic()
  baseline_titles=[]
  if args.baseline_report:
   reference=args.baseline_report.resolve()
   if not reference.is_relative_to((ROOT/'.local/qa/batched-course-map').resolve()):raise RuntimeError('invalid_baseline_reference')
   previous=json.loads(reference.read_text(encoding='utf8'))
   if previous['originalInputSha256']!=source_fingerprint or previous['model']!=settings['model'] or previous['baseline']['status']!='completed':raise RuntimeError('baseline_input_mismatch')
   report['baseline']=copy.deepcopy(previous['baseline']);report['baselineReference']=str(reference);report['baselineReferenceCalls']=[c for c in previous['calls'] if c['phase']=='baseline']
   old_map=json.loads((reference.parent/'baseline-map.json').read_text());baseline_titles=[n['title'] for n in old_map['root']['children']]
  else:
   try:
    with patch.object(course,'urlopen',transport):raw=course._deepseek_course_json(payload,images)
    report['baseline']=finalize(raw,'baseline');baseline_titles=[n['title'] for n in raw['children']]
   except Exception as e:report['baseline']={'status':'failed','errorType':type(e).__name__,'errorCode':getattr(e,'code',None)}
   report['baseline']['elapsedSeconds']=round(time.monotonic()-before,3)
  save();print(json.dumps({'stage':'baseline_finished','result':report['baseline']}),flush=True)
  if args.baseline_only:
   report['state']='completed';report['mode']='original_only';report['paidCalls']=len(report['calls'])
   report['tokenTotals']={key:sum(c.get(key,0) for c in report['calls']) if all(key in c for c in report['calls']) else None for key in ['prompt_tokens','completion_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens']}
   save();print(json.dumps({'stage':'original_only_finished','result':report['baseline'],'calls':report['paidCalls'],'outputDirectory':str(out)},ensure_ascii=False),flush=True);return
  phase='plan';report['state']='batched_running';save();before=time.monotonic()
  def send_json(body,stage,index):
   nonlocal phase,batch_index
   phase=stage;batch_index=index
   if body['messages'][:2]!=base['messages'][:2]:raise RuntimeError('original_materials_changed')
   active=copy.deepcopy(body);network_retries=0;format_retries=0
   for attempt in range(4):
    def parse(text):
     value=parse_course_json(text,task=args.task)
     if stage=='plan':validate_plan(value)
     else:
      contract=json.loads(body['messages'][-1]['content'])
      if not isinstance(value,dict) or value.get('batchId')!=contract['batchId'] or not isinstance(value.get('items'),list) or [n.get('id') for n in value['items'] if isinstance(n,dict)]!=contract['requestedIds']:raise ValueError('wrong_batch_or_missing_ids')
     return value
    request=Request(settings['baseUrl'].rstrip('/')+'/chat/completions',data=json.dumps(active,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
     return diagnostics.request_model_json(request,300,args.task,'course_map_batch_experiment',transport=transport,image_count=len(images),input_characters=sum(len(m['content']) if isinstance(m['content'],str) else sum(len(p.get('text','')) for p in m['content']) for m in active['messages']),model=settings['model'],output_limit=active['max_tokens'],content_parser=parse)
    except Exception as error:
     network_failure=isinstance(error,(URLError,TimeoutError,ConnectionError)) and (not isinstance(error,HTTPError) or error.code in (408,429,500,502,503,504))
     if network_failure and network_retries<2 and attempt<3:
      network_retries+=1
      print(json.dumps({'stage':'network_retry','phase':stage,'batch':index,'retry':network_retries,'reasonType':type(getattr(error,'reason',error)).__name__}),flush=True);time.sleep(network_retries);continue
     if format_retries or attempt>=3 or not hasattr(error,'doc'):raise
     format_retries+=1
     active['messages']+=[{'role':'assistant','content':error.doc},{'role':'user','content':json.dumps({'task':'Repair ONLY this independent JSON response to the preceding turn. Keep every requested ID, all formulas, references and details; never change the frozen plan or drop suffix content. Return exactly one complete JSON object using the required phase schema.','error':getattr(error,'code','invalid_json'),'position':getattr(error,'pos',None)})}]
  try:
   raw,protocol=run_batched(base,send_json,batch_size=6,allowed_sources=allowed_sources,allowed_images=allowed_images,max_batches=24)
   canonical=translate_references(raw,aliases);report['batched']=finalize(canonical,'batched');report['batched'].update(protocol)
   from course_outline import _key
   report['comparison']={'identicalOriginalMaterialContext':True,'originalImagesRetained':len(images),'baselineTopLevelTitlesAlsoPresent':sum(any(_key(t)==_key(n['title']) for n in canonical['children']) for t in baseline_titles),'baselineTopLevelModules':len(baseline_titles),'semanticCorrectness':'requires_manual_review; citation existence and structural checks do not prove all claims correct'}
  except Exception as e:
   report['batched']={'status':'failed','errorType':type(e).__name__,'errorCode':getattr(e,'code',None),'diagnosticCode':str(e) if str(e).replace('_','').isalnum() and len(str(e))<90 else None}
  report['batched']['elapsedSeconds']=round(time.monotonic()-before,3)
  report['state']='completed';report['paidCalls']=len(report['calls']);report['tokenTotals']={key:sum(c.get(key,0) for c in report['calls']) if all(key in c for c in report['calls']) else None for key in ['prompt_tokens','completion_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens']};save()
  print(json.dumps({'stage':'experiment_finished','baseline':report['baseline'],'batched':report['batched'],'calls':report['paidCalls'],'outputDirectory':str(out)},ensure_ascii=False),flush=True)
 finally:diagnostics.record_event=original_event;diagnostics.close_logs()
if __name__=='__main__':main()
