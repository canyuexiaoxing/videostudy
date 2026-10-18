import sys,json,time,statistics
from pathlib import Path
R=Path('E:/workp/videostudy');O=R/'.local/qa/yolo-grouping-fix-20261018';ID='427ff2cd-8534-4f04-bc75-0a275c9e918b';sys.path.insert(0,str(R/'agent-python'))
from person_visibility import grouping_context
from slide_grouping import group_pages
frames=json.loads((R/'.local/qa/grouping-multi-20261017'/f'{ID}.json').read_text())['visualEvidence'];folder=O/ID
meta=json.loads((R/'.local/qa/grouping-multi-20261017/metadata.json').read_text());region=json.loads(meta[ID]['region']) if meta[ID]['region'] else None
report=json.loads((O/'real-report.json').read_text());report['trials']={};report['benchmark_environment']='Windows host; final code, saved-JPG replay, five repetitions'
results={}
for mode in ['off','adjacent']:
 durations=[];contexts=[]
 for _ in range(5):
  start=time.perf_counter();context=grouping_context(folder,frames,mode);contexts.append(time.perf_counter()-start)
  start=time.perf_counter();pages,trans=group_pages(frames,folder,[],ask_json=lambda _:{'samePage':False},ignore_region=region,person_selection_mode=mode);durations.append(time.perf_counter()-start)
 results[mode]=pages;report['trials'][mode]={'group_s':durations,'group_median_s':statistics.median(durations),'cache_context_s':contexts,'groups':len(pages),'representatives':len(set(t for p in pages for t in p['representativeFrameTimesMs']))}
 (O/f'{mode}-pages.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2))
old={t:i for i,p in enumerate(results['off']) for t in p['memberFrameTimesMs']};changes=[]
for p in results['adjacent']:
 sources=sorted(set(old[t]+1 for t in p['memberFrameTimesMs']))
 if len(sources)>1:changes.append({'original_groups':sources,'members':p['memberFrameTimesMs'],'representatives':p['representativeFrameTimesMs']})
report['merged']=changes;report['all_original_representatives_preserved']=set(t for p in results['off'] for t in p['representativeFrameTimesMs'])<=set(t for p in results['adjacent'] for t in p['representativeFrameTimesMs'])
(O/'real-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False),flush=True)
