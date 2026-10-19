"""Repeatable offline comparison; snapshots required, network forbidden."""
import argparse,copy,hashlib,html,importlib.util,json,os,socket,statistics,sys,time
from pathlib import Path
import cv2,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(ROOT/'agent-python'))
def module(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=module('coverage','grouping-coverage-probe.py');r=module('dedup','representative-dedup-probe.py');v=module('versions','page-versions-probe.py')
INPUT=ROOT/'.local/qa/grouping-multi-20261017'
COURSES=[('d517b4f7-58d3-483d-bd9f-a0966341461b','增长量新'),('56ac6493-3085-45e2-b9c4-130b583b95d1','极限题'),('cbacd60e-c271-48b2-9353-2bc88d7c2aec','增长量旧'),('427ff2cd-8534-4f04-bc75-0a275c9e918b','幂级数')]
CHECKS={COURSES[0][0]:{'red':[890000],'black_answer':[1064000,1076000]},COURSES[1][0]:{'substitution':[522000,549000,690000],'final_work':[2493000,2514000]},COURSES[2][0]:{'red':[860000],'black_answer':[1072000]},COURSES[3][0]:{'derivation_0810':[490000],'derivation_2306':[1386000],'final_sum_2412':[1452000],'revision_1832_1848':[1112000,1128000]}}
def selected(pages):return sorted({t for p in pages for t in p['representativeFrameTimesMs']})
def timed(fn):
 start=time.perf_counter();value=fn();return value,time.perf_counter()-start

def blocked(*a,**kw):raise RuntimeError('network_disabled_for_offline_evaluation')
socket.socket.connect=blocked;socket.create_connection=blocked

def run(out,runs):
 out.mkdir(parents=True,exist_ok=False)
 meta=json.loads((INPUT/'metadata.json').read_text(encoding='utf-8'));report={'runs':runs,'scope':'4 task records, 3 distinct videos; saved OCR/images/regions only; all networking blocked; no paid APIs or historical writes','prototype_limitations':['Prototype, not production implementation.','No semantic or person-visibility classifier. Unknown visibility stays unknown.','Only original representatives plus <=16 OCR-novel candidate images are examined; not all source-image content is verified.','Runtime budgets recorded, not enforced, for diagnostic measurement. No apply admission.','Checkpoints match exact known frame alternatives; they are not full-course semantic quality scores.','Disk/OS caches warm during runs; first observed runs and alternating order retained.','Cache counts only retained small image arrays, not whole-process peak RAM.'],'results':[]}
 for course,label in COURSES:
  path=INPUT/f'{course}.json';record=json.loads(path.read_text(encoding='utf-8'));frames=record['visualEvidence'];folder=ROOT/'.local/keyframes'/course
  region=json.loads(meta[course]['region']) if meta[course]['region'] else None
  for f in frames:
   if not (folder/f"{f['frameTimeMs']}.jpg").is_file():raise FileNotFoundError('snapshot_source_missing')
  before=hashlib.sha256(json.dumps(record,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
  results={};last={};baseline_matches=[]
  for trial in range(runs):
   grouped={};group_s={}
   thresholds=[.72,.65,.70] if trial%2==0 else [.70,.65,.72]
   for threshold in thresholds:
    pages,elapsed=timed(lambda:m.groups(frames,folder,record['segments'],threshold,region));grouped[threshold]=pages;group_s[threshold]=elapsed
   baseline=grouped[.72];baseline_matches.append([p['memberFrameTimesMs'] for p in baseline]==[p['memberFrameTimesMs'] for p in record['pageGroups']])
   for threshold,name in ((.72,'baseline72'),(.65,'threshold65'),(.70,'threshold70')):
    value={'selected':selected(grouped[threshold]),'entries':len(grouped[threshold]),'extra_s':0.,'total_s':group_s[threshold],'pages':grouped[threshold]}
    results.setdefault(name,[]).append(value);last[name]=value
   order=['coverage65','dedup93','dedup97','new_observe','new_protect']
   if trial%2:order.reverse()
   for name in order:
    if name=='coverage65':
     start=time.perf_counter();features=m.Features(frames,folder,region);chosen=[features.select(p['memberFrameTimesMs'],.93,.5) for p in grouped[.65]];extra=time.perf_counter()-start
     value={'selected':sorted({t for group in chosen for t in group}),'entries':len(grouped[.65]),'extra_s':extra,'total_s':group_s[.65]+extra}
    elif name.startswith('dedup'):
     ids=set(selected(baseline));source=[f for f in frames if f['frameTimeMs'] in ids];start=time.perf_counter();features=m.Features(source,folder,region)
     limit,worst=(.93,.5) if name=='dedup93' else (.97,.65)
     dedup=r.deduplicate(baseline,features,limit,worst);extra=time.perf_counter()-start
     value={'selected':dedup['selected'],'entries':len(baseline),'extra_s':extra,'total_s':group_s[.72]+extra,'clusters':dedup['clusters']}
    else:
     result,extra=timed(lambda:v.collect(baseline,frames,folder,region,protect=name=='new_protect'))
     value=dict(result,entries=len(result['collections']),extra_s=extra,total_s=group_s[.72]+extra)
    results.setdefault(name,[]).append(value);last[name]=value
   print(json.dumps({'course':label,'trial':trial+1,'baseline_groups':len(baseline),'new_entries':last['new_protect']['entries'],'new_images':len(last['new_protect']['selected'])},ensure_ascii=False),flush=True)
  after=hashlib.sha256(json.dumps(record,sort_keys=True,ensure_ascii=False).encode()).hexdigest();assert before==after
  row={'course':course,'label':label,'frames':len(frames),'mode':meta[course]['mode'],'region':region,'snapshot_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'baseline_matches_saved':all(baseline_matches),'input_unchanged':before==after,'schemes':{}}
  for name,samples in results.items():
   value=last[name];assert all(s['selected']==value['selected'] and s['entries']==value['entries'] for s in samples)
   checkpoints={key:bool(set(alts)&set(value['selected'])) for key,alts in CHECKS[course].items()}
   row['schemes'][name]={'entries':value['entries'],'image_count':len(value['selected']),'total_median_s':statistics.median(s['total_s'] for s in samples),'extra_median_s':statistics.median(s['extra_s'] for s in samples),'samples_s':[s['total_s'] for s in samples],'extra_samples_s':[s['extra_s'] for s in samples],'source_checkpoints':checkpoints,'selected':value['selected'],'removed_baseline':sorted(set(selected(record['pageGroups']))-set(value['selected'])),'added_baseline':sorted(set(value['selected'])-set(selected(record['pageGroups'])))}
   if name.startswith('new_'):row['schemes'][name].update({key:value[key] for key in ('collections','proofs','extra_read','unresolved_count','cache_bytes','over_budget')})
  report['results'].append(row);(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  make_review(out,row,last,folder)
 write_summary(out,report)
 print('REPORT '+str(out/'report.json'),flush=True)

def make_review(out,row,last,folder):
 label=row['label'];course=row['course'];blocks=[]
 for name,value in last.items():
  if name in ('baseline72','threshold70','new_observe'):continue
  blocks.append('<h2>'+html.escape(label+' / '+name)+'</h2>')
  changed=sorted(set(value['selected'])^set(last['baseline72']['selected']))
  for t in changed:
   status='ADDED' if t in value['selected'] else 'REMOVED'
   blocks.append(f'<figure><figcaption>{status} {t/1000:.1f}s</figcaption><img loading="lazy" src="../../keyframes/{course}/{t}.jpg"></figure>')
 for c in last['new_protect']['collections']:
  if len(c['sourcePageIndices'])>1:
   blocks.append('<h3>NEW MERGE '+str(c['sourcePageIndices'])+'</h3>')
   for t in c['representativeFrameTimesMs']:
    blocks.append(f'<figure><figcaption>{t/1000:.1f}s</figcaption><img loading="lazy" src="../../keyframes/{course}/{t}.jpg"></figure>')
 (out/f'{course}.html').write_text('<meta charset="utf-8"><style>body{background:#eee;font:16px sans-serif}figure{display:inline-block;width:46%;margin:1%}img{width:100%}</style>'+''.join(blocks),encoding='utf-8')
 # Contact sheet of original/known checkpoints + prototype extra images and merged reps.
 ids=set(t for alts in CHECKS[course].values() for t in alts)
 for c in last['new_protect']['collections']:
  if len(c['sourcePageIndices'])>1:ids.update(c['representativeFrameTimesMs'])
 ids.update(row['schemes']['new_protect']['added_baseline']);tiles=[]
 for t in sorted(ids):
  image=cv2.imread(str(folder/f'{t}.jpg'))
  if image is None:continue
  h,w=image.shape[:2];image=cv2.resize(image,(480,round(h*480/w)));tile=np.full((310,480,3),240,np.uint8);hh=min(280,image.shape[0]);tile[30:30+hh]=cv2.resize(image,(480,hh))
  marks=''.join(n+' ' for n in ('baseline72','threshold65','dedup93','dedup97','new_protect') if t in last[n]['selected'])
  cv2.putText(tile,f'{t/1000:.1f}s '+marks,(5,20),cv2.FONT_HERSHEY_SIMPLEX,.35,(0,0,0),1);tiles.append(tile)
 while len(tiles)%3:tiles.append(np.full((310,480,3),240,np.uint8))
 if tiles:cv2.imwrite(str(out/f'{course}.jpg'),np.vstack([np.hstack(tiles[i:i+3]) for i in range(0,len(tiles),3)]))

def write_summary(out,report):
 lines=['# Offline comparison 2026-10-18','','Fresh run; 4 records / 3 distinct videos. Local grouping + selection only. No model calls.','','|Course|Scheme|Entries|Images|Total median s|Extra median s|Known source checkpoints|','|---|---|---:|---:|---:|---:|---|']
 for row in report['results']:
  for name,s in row['schemes'].items():
   hits=s['source_checkpoints'];lines.append(f"|{row['label']}|{name}|{s['entries']}|{s['image_count']}|{s['total_median_s']:.3f}|{s['extra_median_s']:.3f}|{sum(hits.values())}/{len(hits)}|")
 lines+=['','Checkpoint counts refer to exact previously inspected frame alternatives, not complete semantic accuracy.','New prototype retains all baseline images unless exact duplicate; merging is still provisional.','New protect reviews <=16 extra images based on OCR novelty; unknown diagrams and low-confidence OCR remain unverified.','No runtime fallback, cancellation, history/UI/model integration implemented in this throwaway probe.','Reported cache is retained small arrays, not process peak RAM.','Full details and timing samples: report.json.']
 (out/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--runs',type=int,default=3);p.add_argument('--output',default='page-schemes-20261018');a=p.parse_args();run(ROOT/'.local/qa'/a.output,a.runs)
