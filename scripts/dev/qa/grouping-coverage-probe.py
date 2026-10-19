"""Offline experiment only: grouping thresholds and spatial edge coverage.
No production changes, OCR, person inference or paid API requests.
"""
import argparse,inspect,json,sys,time,statistics,urllib.request,re
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
import slide_grouping as grouping

class Features:
 def __init__(self,frames,folder,region=None):
  self.data={};self.ocr={}
  for frame in frames:
   t=frame['frameTimeMs'];image=cv2.imread(str(folder/f'{t}.jpg'),cv2.IMREAD_GRAYSCALE)
   h,w=image.shape;small=cv2.resize(image,(640,360),interpolation=cv2.INTER_AREA)
   from ignored_region import effective_mask,filter_frame
   mask=effective_mask(640,360,region,t) if region else np.ones((360,640),dtype=bool)
   frame=filter_frame(frame,region,t,w,h) if region else frame
   edges=(cv2.Canny(small,50,120)>0)&mask;dilated=cv2.dilate(edges.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)
   boxes=[];texts=[];content=np.zeros_like(edges)
   for b in frame.get('ocrBlocks',[]):
    if b.get('score',1)<.35 or not str(b.get('text','')).strip():continue
    poly=np.asarray(b.get('polygon',[]),dtype=float)
    if poly.shape!=(4,2):continue
    x1=max(0,int(poly[:,0].min()*640/w)-1);x2=min(640,int(poly[:,0].max()*640/w)+2)
    y1=max(0,int(poly[:,1].min()*360/h)-1);y2=min(360,int(poly[:,1].max()*360/h)+2)
    if x2<=x1 or y2<=y1:continue
    n=int(edges[y1:y2,x1:x2].sum())
    if n<8:continue
    texts.append((x1,y1,x2,y2,str(b.get("text","")),b.get("score",1)))
    boxes.append((x1,y1,x2,y2,n));content[y1:y2,x1:x2]|=edges[y1:y2,x1:x2]
   self.data[t]=(edges,dilated,boxes,content);self.ocr[t]=texts
  self.cache={}
 def recall(self,source,target):
  key=source,target
  if key in self.cache:return self.cache[key]
  if source==target:return (1.,1.)
  a,_,boxes,content=self.data[source];_,b,_,_=self.data[target]
  if len(boxes)<3 or content.sum()<50:return (0.,0.)
  # Whole image fixed coordinates; large camera motion is conservatively retained.
  missing=content&~b
  overall=1-float(missing.sum())/int(content.sum())
  ratios=[1-float((a[y1:y2,x1:x2]&~b[y1:y2,x1:x2]).sum())/n for x1,y1,x2,y2,n in boxes]
  result=(overall,min(ratios));self.cache[key]=result;return result
 def conflict(self,source,target):
  pattern=r'[0-9+−–\-=<>≤≥×÷]'
  for x1,y1,x2,y2,text,confidence in self.ocr[source]:
   a=re.sub(r'\s+','',text);skeleton=re.sub(pattern,'',a)
   if confidence<.85 or len(skeleton)<2:continue
   for xx1,yy1,xx2,yy2,other,score in self.ocr[target]:
    if score<.85:continue
    overlap=max(0,min(x2,xx2)-max(x1,xx1))*max(0,min(y2,yy2)-max(y1,yy1))
    union=(x2-x1)*(y2-y1)+(xx2-xx1)*(yy2-yy1)-overlap
    if overlap/max(union,1)<.6:continue
    b=re.sub(r'\s+','',other)
    if skeleton==re.sub(pattern,'',b) and re.findall(pattern,a)!=re.findall(pattern,b):return True
  return False
 def covers(self,source,target,limit,worst_limit=.65):
  overall,worst=self.recall(source,target)
  return overall>=limit and worst>=worst_limit and not self.conflict(source,target)
 def select(self,times,limit,worst_limit=.65):
  # Cover actual member frames directly, never assume A->B->C is transitive.
  coverage={t:{source for source in times if self.covers(source,t,limit,worst_limit)} for t in times}
  remaining=set(times);selected=[]
  while remaining:
   best=max(times,key=lambda t:(len(coverage[t]&remaining),t))
   assert coverage[best]&remaining
   selected.append(best);remaining-=coverage[best]
  for t in selected[:]:
   others=[q for q in selected if q!=t]
   if others and set(times)<=set().union(*(coverage[q] for q in others)):selected.remove(t)
  assert all(any(self.covers(t,q,limit,worst_limit) for q in selected) for t in times)
  return sorted(selected)

def groups(frames,folder,speech,threshold,region=None):
 original=grouping._boundary;ns=dict(grouping.__dict__)
 exec(inspect.getsource(original).replace('previous_retained >= 0.72',f'previous_retained >= {threshold}'),ns)
 grouping._boundary=ns['_boundary']
 try:return grouping.group_pages(frames,folder,speech,ask_json=lambda _:dict(samePage=False,reason='offline conservative split'),ignore_region=region)[0]
 finally:grouping._boundary=original

def main():
 p=argparse.ArgumentParser();p.add_argument('--course',default='427ff2cd-8534-4f04-bc75-0a275c9e918b');p.add_argument('--runs',type=int,default=3);args=p.parse_args()
 out=ROOT/'.local/qa/grouping-coverage-20261017';out.mkdir(parents=True,exist_ok=True);snapshot=out/f'{args.course}.json'
 if not snapshot.exists():
  with urllib.request.urlopen(f'http://127.0.0.1:18080/api/transcriptions/{args.course}',timeout=10) as r:value=json.load(r)['result']
  snapshot.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
 value=json.loads(snapshot.read_text(encoding='utf-8'));frames=value['visualEvidence'];folder=ROOT/'.local/keyframes'/args.course
 start=time.perf_counter();features=Features(frames,folder);feature_s=time.perf_counter()-start
 report={'course':args.course,'scope':'existing images and OCR only; no ASR/OCR/model calls; experimental settings not deployed','frames':len(frames),'feature_s':feature_s,'runs':args.runs,'results':[]}
 for threshold in (.60,.62,.65,.68,.70,.72):
  timings=[]
  for _ in range(args.runs):
   start=time.perf_counter();pages=groups(frames,folder,value['segments'],threshold);timings.append(time.perf_counter()-start)
  row={'threshold':threshold,'groups':len(pages),'grouping_median_s':statistics.median(timings),'grouping_samples_s':timings,'old_representatives':sum(len(p['representativeFrameTimesMs']) for p in pages),'pages':pages,'coverage':[]}
  for limit,worst_limit in ((.88,.65),(.93,.50),(.93,.65),(.97,.65)):
   # Empty pair cache each time: account for all comparison work.
   features.cache={};start=time.perf_counter();selected=[features.select(p['memberFrameTimesMs'],limit,worst_limit) for p in pages];selection_s=time.perf_counter()-start
   retired=[]
   for page,reps in zip(pages,selected):
    for t in page['memberFrameTimesMs']:
     if t not in reps:retired.append(max(features.recall(t,q)[0] for q in reps))
   row['coverage'].append({'limit':limit,'worst_limit':worst_limit,'representatives':sum(map(len,selected)),'selection_s':selection_s,'incremental_s':feature_s+selection_s,'min_retired_edge_recall':min(retired,default=1),'selected':selected})
  report['results'].append(row)
  print(json.dumps({k:v for k,v in row.items() if k!='pages'}),flush=True)
 (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'report':str(out/'report.json'),'paidCalls':0,'productionChanged':False}))
if __name__=='__main__':main()
