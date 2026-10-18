"""Compare saved evidence with the deployed algorithm and mask-first grouping."""
from pathlib import Path
import importlib,json,statistics,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'.local/qa/mask-first-grouping-20261018';OUT.mkdir(parents=True,exist_ok=True)
SOURCE=ROOT/'.local/qa/grouping-repair-20261018'
before=OUT/'before';before.mkdir(exist_ok=True)
for name in ('slide_grouping.py','person_grouping.py'):
 data=subprocess.check_output(['git','-c','safe.directory='+ROOT.as_posix(),'-C',str(ROOT),'show','HEAD:agent-python/'+name])
 (before/name).write_bytes(data)
metadata=json.loads((SOURCE/'metadata.json').read_text(encoding='utf-8'))
ids=['abe91625-6846-4756-b209-09dcf1216c5a','0d345651-92fe-4a62-8abf-d7a81195f139','427ff2cd-8534-4f04-bc75-0a275c9e918b']
report=[]
for task in ids:
 record=json.loads((SOURCE/(task+'.json')).read_text(encoding='utf-8'))
 region=json.loads(metadata[task]['region']) if metadata[task]['region'] else None
 row={'id':task,'frames':len(record['visualEvidence']),'cases':{}};results={}
 for version in ('before','after'):
  sys.path[:]=[str(before if version=='before' else ROOT/'agent-python'),str(ROOT/'agent-python')]+[p for p in sys.path if p not in (str(before),str(ROOT/'agent-python'))]
  for name in ('slide_grouping','person_grouping'):sys.modules.pop(name,None)
  group=importlib.import_module('slide_grouping').group_pages
  for mode in ('off','adjacent'):
   durations=[]
   for iteration in range(3):
    start=time.perf_counter()
    pages,transitions=group(record['visualEvidence'],ROOT/'.local/keyframes'/task,record['segments'],ask_json=lambda _:{'samePage':False},ignore_region=region,person_selection_mode=mode)
    durations.append(time.perf_counter()-start)
   reps={t for p in pages for t in p['representativeFrameTimesMs']}
   members=[t for p in pages for t in p['memberFrameTimesMs']]
   result={'pages':pages,'transitions':transitions};results[version,mode]=result
   row['cases'][version+'_'+mode]={'groups':len(pages),'representatives':len(reps),'seconds_median':statistics.median(durations),'seconds_runs':durations,'members':len(members),'duplicate_members':len(members)-len(set(members))}
   (OUT/(task+'-'+version+'-'+mode+'.json')).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
 row['off_unchanged']=results['before','off']==results['after','off']
 old=results['before','adjacent']['pages'];new=results['after','adjacent']['pages']
 row['old_representatives_preserved']={t for p in old for t in p['representativeFrameTimesMs']}<={t for p in new for t in p['representativeFrameTimesMs']}
 row['conservative_representatives_preserved']={t for p in results['before','off']['pages'] for t in p['representativeFrameTimesMs']}<={t for p in new for t in p['representativeFrameTimesMs']}
 row['members_preserved']=sorted(t for p in old for t in p['memberFrameTimesMs'])==sorted(t for p in new for t in p['memberFrameTimesMs'])
 row['changed_groups']=[{'members':p['memberFrameTimesMs'],'reps':p['representativeFrameTimesMs']} for p in new if p['memberFrameTimesMs'] not in [q['memberFrameTimesMs'] for q in old]]
 report.append(row);(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in row.items() if k!='changed_groups'},ensure_ascii=False),flush=True)
