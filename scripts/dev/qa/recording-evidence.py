"""Read-only, reproducible recording metrics for the five selected history rows."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,os,sqlite3,re,subprocess
ROOT=Path(__file__).resolve().parents[3]
IDS=['87b5ab2e-9508-491f-bcc8-aa61bc76941d','41d4c269-b84c-49c4-8d22-fde07c468b25','5d844c81-4ce7-4e68-bb59-13b6bda33a0b','feda6396-6b68-4eb0-911c-4dfc2cdcc7c5','eb940a63-7f37-4c6b-9707-2949c732572c']
TZ=timezone(timedelta(hours=8))
def instant(value):
 d=datetime.fromisoformat(value.replace('Z','+00:00'))
 return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d

def walk(nodes,depth=1):
 for n in nodes:
  yield n,depth
  yield from walk(n.get('children',[]),depth+1)

def flat(nodes):
 for n in nodes:
  yield n
  yield from flat(n.get('details',[]));yield from flat(n.get('children',[]))

def main():
 data=Path(os.environ['APPDATA'])/'Framewise/data';events=[]
 for f in (data/'logs').glob('model-events.jsonl*'):
  if not f.is_file():continue
  for line in f.read_text(encoding='utf8').splitlines():
   try:e=json.loads(line)
   except ValueError:continue
   if e.get('task') in IDS:events.append(e)
 events.sort(key=lambda e:e['timestamp'])
 con=sqlite3.connect((data/'database/framewise.db').as_uri()+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
 results=[];duration_cache={}
 for id in IDS:
  row=con.execute('SELECT id,original_filename,status,result_json,created_at,updated_at,mind_map_mode,person_selection_mode,ignored_region_json,coarse_change_percent,coarse_sample_seconds,media_size FROM transcription_jobs WHERE id=?',(id,)).fetchone()
  if row is None:raise RuntimeError('selected_record_missing')
  d=json.loads(row['result_json']);m=d['mindMap'];nodes=list(walk(m['root'].get('children',[])));details=[x for n,_ in nodes for x in n.get('details',[])];all_nodes=list(flat(m['root'].get('children',[])))+list(flat(m.get('examples',[])))
  speech_end=max(s['endMs'] for s in d['segments']);video=ROOT/row['original_filename'];duration_source='saved_evidence_lower_bound'
  if row['original_filename'] not in duration_cache and video.is_file() and video.stat().st_size==row['media_size']:
   probe=ROOT/'.local/tools/ffmpeg-9.0.2-full_build/bin/ffprobe.exe'
   result=subprocess.run([str(probe),'-v','error','-show_entries','format=duration','-of','json',str(video)],capture_output=True,text=True,check=True)
   duration_cache[row['original_filename']]=round(float(json.loads(result.stdout)['format']['duration'])*1000)
  duration=duration_cache.get(row['original_filename'],max(speech_end,max(v['frameTimeMs'] for v in d['visualEvidence'])))
  if row['original_filename'] in duration_cache:duration_source='ffprobe_original_filename_and_size_match'
  known={s['id'] for s in d['segments']}|{'frame_'+str(v['frameTimeMs']) for v in d['visualEvidence']};refs=[ref for n in all_nodes for ref in n.get('evidenceRefs',[])]
  selected=[e for e in events if e.get('task')==id];created=instant(m['createdAt'])
  validations=[e for e in selected if e.get('stage')=='validation' and e.get('status')=='completed' and abs((instant(e['timestamp'])-created).total_seconds())<3]
  validation=min(validations,key=lambda e:abs((instant(e['timestamp'])-created).total_seconds())) if validations else None
  completed=[e for e in selected if e.get('event')=='request_completed' and e.get('operation')=='course_map' and -1<=(created-instant(e['timestamp'])).total_seconds()<8]
  completed=max(completed,key=lambda e:e['timestamp']) if completed else None
  request=next((e for e in selected if completed and e.get('event')=='request_started' and e.get('request_id')==completed['request_id']),None)
  timing=d.get('stageTimingsMs',{})
  success_only=id in IDS[:2]
  elapsed=(instant(validation['timestamp'])-instant(request['timestamp'])).total_seconds() if success_only and validation and request else None if success_only else timing.get('total',0)/1000
  record={'id':id,'filename':row['original_filename'],'historyCreatedLocal':instant(row['created_at']).astimezone(TZ).isoformat(),'successfulMapCreatedLocal':created.astimezone(TZ).isoformat(),'videoDurationSeconds':duration/1000,'durationSource':duration_source,'effectiveSpeechEndSeconds':speech_end/1000,'selectedElapsedSeconds':round(elapsed,3) if elapsed is not None else None,'timeScope':'successful_map_request_to_validation_only' if success_only else 'pipeline_start_to_mind_map_completion','timeSource':'matched_request_id_and_completed_validation' if success_only and elapsed is not None else 'stageTimingsMs.total' if not success_only else 'not_available','successfulRequestId':completed.get('request_id') if completed else None,'successfulModelRequestSeconds':completed.get('elapsed_ms',0)/1000 if completed and 'elapsed_ms' in completed else None,'jobStatus':row['status'],'mapStatus':m.get('status'),'promptVersion':m.get('promptVersion'),'mode':row['mind_map_mode'],'personSelection':row['person_selection_mode'],'regionConfigured':bool(row['ignored_region_json']),'sampleSeconds':row['coarse_sample_seconds'],'coarseChangePercent':row['coarse_change_percent'],'transcriptSegments':len(d['segments']),'candidateImages':len(d['visualEvidence']),'pageGroups':len(d['pageGroups']),'representativeImages':len({t for g in d['pageGroups'] for t in g.get('representativeFrameTimesMs',[])}),'topLevelModules':len(m['root'].get('children',[])),'knowledgeNodes':len(nodes),'details':len(details),'examples':len(m.get('examples',[])),'maximumKnowledgeDepth':max((depth for _,depth in nodes),default=0),'latexTextItems':sum(bool(re.search(r'\\[([]|\\(?:frac|sum|int|begin|theta)\b',n.get('title',''))) for n in all_nodes),'emptyTitles':sum(not isinstance(n.get('title'),str) or not n.get('title','').strip() for n in all_nodes),'unknownReferenceCount':sum(ref.get('sourceId') not in known for ref in refs),'invalidReferenceTimeCount':sum(type(ref.get('startMs')) is not int or type(ref.get('endMs')) is not int or not 0<=ref.get('startMs',-1)<=ref.get('endMs',-1)<=duration for ref in refs),'citedImages':len({x.get('sourceId') for x in refs if x.get('sourceType')=='image'}),'citedTranscriptSegments':len({x.get('sourceId') for x in refs if x.get('sourceType')=='transcript'}),'uncertainties':len(m.get('uncertainties',[])),'coverageReviewStatus':(d.get('review') or {}).get('status'),'coverageConcernCount':len((d.get('review') or {}).get('concerns',[])),'finalReferenceValidation':{k:validation[k] for k in ['invalid_ref_count','repaired_ref_count'] if validation and k in validation},'semanticQuality':'not_manually_verified','formulaCorrectness':'not_manually_verified','playbackClickAccuracy':'not_interactively_verified','mapSnapshotSha256':hashlib.sha256(json.dumps(m,ensure_ascii=False,sort_keys=True).encode()).hexdigest()}
  results.append(record)
 con.close();out=ROOT/'.local/qa/recording-evidence-2026-10-21';out.mkdir(parents=True,exist_ok=True)
 report={'recordedAtLocal':datetime.now(TZ).isoformat(),'databaseReadOnly':True,'newModelCalls':0,'records':results,'notes':['Selected retried records use successful map generation only; previous failures and waiting excluded.','Different timing scopes must not be compared as pipeline speedups.','Counts and reference checks are not semantic quality scores.']}
 (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 for r in results:print(json.dumps({k:r[k] for k in ['id','selectedElapsedSeconds','timeScope','successfulModelRequestSeconds','topLevelModules','knowledgeNodes','details','examples','maximumKnowledgeDepth','latexTextItems','unknownReferenceCount','invalidReferenceTimeCount','uncertainties']},ensure_ascii=False))
if __name__=='__main__':main()
