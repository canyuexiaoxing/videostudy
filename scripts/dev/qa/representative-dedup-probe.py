"""Experimental representative-only post-group dedup. No product writes/model calls."""
import importlib.util,json,time,statistics
from pathlib import Path
spec=importlib.util.spec_from_file_location('coverage_probe',Path(__file__).with_name('grouping-coverage-probe.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ROOT=m.ROOT;INPUT=ROOT/'.local/qa/grouping-multi-20261017';OUT=ROOT/'.local/qa/representative-dedup-20261017'

def deduplicate(pages,features,limit=.93,worst=.5):
 clusters=[];pending=[];previous=[]
 def close():
  if pending:
   sources=list(dict.fromkeys(t for p in pending for t in p['representativeFrameTimesMs']))
   selected=features.select(sources,limit,worst) if len(pending)>1 else sources
   assert all(any(features.covers(t,q,limit,worst) for q in selected) for t in sources)
   clusters.append(dict(groups=[p['pageIndex'] for p in pending],original=sources,selected=selected))
 for page in pages:
  current=page['representativeFrameTimesMs']
  # Only adjacent groups start a candidate chain; never compare arbitrary distant pages.
  linked=previous and any(features.covers(a,b,limit,worst) or features.covers(b,a,limit,worst) for a in previous for b in current)
  if pending and not linked:close();pending=[]
  pending.append(page);previous=current
 close()
 selected=sorted({t for c in clusters for t in c['selected']})
 return dict(selected=selected,clusters=clusters)

def main():
 OUT.mkdir(parents=True,exist_ok=True);inputs=json.loads((INPUT/'report.json').read_text(encoding='utf-8'))['results'];report=[]
 for row in inputs:
  course=row['id'];value=json.loads((INPUT/f'{course}.json').read_text(encoding='utf-8'));pages=next(x['pages'] for x in row['thresholds'] if x['threshold']==.72)
  ids={t for p in pages for t in p['representativeFrameTimesMs']};frames=[f for f in value['visualEvidence'] if f['frameTimeMs'] in ids];folder=ROOT/'.local/keyframes'/course
  trials=[]
  for limit,worst in ((.88,.5),(.93,.5),(.97,.65)):
   samples=[]
   for _ in range(3):
    start=time.perf_counter();features=m.Features(frames,folder,row['region']);prepared=time.perf_counter()-start
    result=deduplicate(pages,features,limit,worst);samples.append(dict(prepare_s=prepared,total_s=time.perf_counter()-start))
   changes=[]
   for c in result['clusters']:
    if len(c['selected'])<len(c['original']):
     removed=[t for t in c['original'] if t not in c['selected']]
     changes.append(dict(c,removed=removed,weakest_removed_recall=min(max(features.recall(t,q)[0] for q in c['selected']) for t in removed)))
   trials.append(dict(limit=limit,worst=worst,original=len(ids),selected_count=len(result['selected']),median_s=statistics.median(t['total_s'] for t in samples),samples=samples,result=result,changes=changes))
   print(json.dumps(dict(label=row['label'],limit=limit,count=len(result['selected']),original=len(ids),median_s=trials[-1]['median_s']),ensure_ascii=False),flush=True)
  report.append(dict(id=course,label=row['label'],mode=row['mode'],region=row['region'],trials=trials))
  (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print('saved',OUT/'report.json')
if __name__=='__main__':main()
