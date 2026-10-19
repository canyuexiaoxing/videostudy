"""Offline representative-first forward selection; never used by product code."""
import re,sys,time,json,hashlib,importlib.util
from collections import OrderedDict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
import cv2,numpy as np
HERE=Path(__file__).resolve().parent

def forward(sources,store,candidates=None,budget=0):
 candidates=candidates or {};active={};extra_seen=set();attempts=[]
 def insert(t,own):
  if t in active:active[t]|=own;return
  replaced=[q for q,known in active.items() if all(store.covers(source,t) for source in known)]
  if replaced:
   known=set(own)
   for q in replaced:known|=active.pop(q)
   active[t]=known;return
  if own:
   target=next((q for q in reversed(active) if all(store.covers(source,q) for source in own)),None)
   if target is not None:active[target]|=own
   else:active[t]=set(own)
 for t in sorted(set(sources)):
  insert(t,{t})
  if not store.blocked(t):continue
  for candidate in candidates.get(t,[])[:2]:
   if candidate in sources or candidate in extra_seen:continue
   if len(extra_seen)>=budget:break
   extra_seen.add(candidate);before=sorted(active);insert(candidate,set())
   attempts.append({'source':t,'candidate':candidate,'before':before,'after':sorted(active),'adopted':candidate in active})
 proofs=[]
 for target,known in active.items():
  for source in known:
   assert store.covers(source,target)
   if source!=target:proofs.append({'removed':source,'retained':target})
 assert set().union(*active.values())==set(sources) if active else not sources
 return {'selected':sorted(active),'proofs':proofs,'extra_reads':len(extra_seen),'search_attempts':attempts}

def canon(value):return re.sub(r'\s+','',str(value)).casefold().replace('−','-')
class Store:
 def __init__(self,course,visuals,folder,region,mask_root,max_cache=16,policy="strict"):
  self.policy=policy
  from ignored_region import effective_mask
  self.effective_mask=effective_mask;self.course=course;self.visuals={f['frameTimeMs']:f for f in visuals};self.folder=folder;self.region=region
  self.index={x['time_ms']:x for x in json.loads((mask_root/f'{course}-mask-index.json').read_text())['frames']}
  with np.load(mask_root/f'{course}-masks.npz') as value:self.masks={int(k):value[k].copy() for k in value.files}
  self.cache=OrderedDict();self.max_cache=max_cache;self.proofs={};self.load_s=0.;self.compare_s=0.;self.loads=0;self.cache_peak=0;self.reasons={}
 def get(self,t):
  if t in self.cache:self.cache.move_to_end(t);return self.cache[t]
  start=time.perf_counter();raw=(self.folder/f'{t}.jpg').read_bytes();meta=self.index[t]
  if hashlib.sha256(raw).hexdigest()!=meta['sha256']:raise ValueError('source_changed_since_mask')
  image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_GRAYSCALE)
  if image is None:raise ValueError('source_unreadable')
  h,w=image.shape
  if (w,h)!=(meta['width'],meta['height']):raise ValueError('mask_size_mismatch')
  gray=cv2.resize(image,(640,360),interpolation=cv2.INTER_AREA)
  person=np.unpackbits(self.masks[t])[:57600].reshape(180,320).astype(np.uint8);person=cv2.resize(person,(640,360),interpolation=cv2.INTER_NEAREST).astype(bool)
  allowed=self.effective_mask(640,360,self.region,t) if self.region else np.ones((360,640),bool)
  visible=allowed&~person;edges=(cv2.Canny(gray,50,120)>0)&visible;dilated=cv2.dilate(edges.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)&visible
  boxes=[];content=np.zeros_like(edges)
  for b in self.visuals[t].get('ocrBlocks',[]):
   poly=np.asarray(b.get('polygon',[]),float)
   if poly.shape!=(4,2) or not np.isfinite(poly).all():continue
   x=max(0,int(np.floor(poly[:,0].min()*640/w))-1);z=min(640,int(np.ceil(poly[:,0].max()*640/w))+1)
   y=max(0,int(np.floor(poly[:,1].min()*360/h))-1);v=min(360,int(np.ceil(poly[:,1].max()*360/h))+1)
   if x>=z or y>=v or allowed[y:v,x:z].mean()<.9:continue
   if visible[y:v,x:z].mean()<.92:continue
   count=int(edges[y:v,x:z].sum())
   if count<8:continue
   boxes.append((x,y,z,v,b,count));content[y:v,x:z]|=edges[y:v,x:z]
  # Full visible edges protect non-OCR figures as well as OCR regions.
  item={'gray':gray,'person':person,'allowed':allowed,'edges':edges,'dilated':dilated,'content':content,'boxes':boxes,'width':w,'height':h}
  self.cache[t]=item
  while len(self.cache)>self.max_cache:self.cache.popitem(last=False)
  self.cache_peak=max(self.cache_peak,sum(sum(v.nbytes for v in f.values() if isinstance(v,np.ndarray)) for f in self.cache.values())+sum(x.nbytes for x in self.masks.values()))
  self.loads+=1;self.load_s+=time.perf_counter()-start;return item
 def blocked(self,t):
  f=self.get(t);return int((f['person']&f['allowed']).sum())>=50
 def covers(self,a,b):
  if a==b:return True
  if (a,b) in self.proofs:return self.proofs[(a,b)]['covers']
  left,right=self.get(a),self.get(b);start=time.perf_counter();edges=left['edges'];count=int(edges.sum());reason='covered';ok=True
  recall=worst=0.
  if count<100:ok=False;reason='insufficient_source_detail'
  else:
   missing=edges&~right['dilated'];recall=1-float(missing.sum())/count
   if recall<(.995 if self.policy=="strict" else .97):ok=False;reason='visible_strokes_not_covered'
   ratios=[]
   for y in range(0,360,30):
    for x in range(0,640,40):
     n=int(edges[y:y+30,x:x+40].sum())
     if n>=12:ratios.append(1-float(missing[y:y+30,x:x+40].sum())/n)
   worst=min(ratios,default=0.)
   if ok and worst<(.98 if self.policy=="strict" else .75):ok=False;reason='local_detail_not_covered'
   if ok:
    for x,y,z,v,block,n in left['boxes']:
     if float(missing[y:v,x:z].sum())/n>(.02 if self.policy=="strict" else .10):ok=False;reason='ocr_block_strokes_not_covered';break
     value=canon(block.get('text',''));critical=bool(re.search(r'[0-9=+\-×÷∑∫<>≤≥]',value)) and block.get('score',1)>=.75
     if critical:
      matched=False
      for xx,yy,zz,vv,other,_ in right['boxes']:
       overlap=max(0,min(z,zz)-max(x,xx))*max(0,min(v,vv)-max(y,yy));union=(z-x)*(v-y)+(zz-xx)*(vv-yy)-overlap
       if overlap/max(union,1)>=.25 and canon(other.get('text',''))==value:matched=True;break
      if not matched:ok=False;reason='critical_ocr_not_confirmed';break
  self.compare_s+=time.perf_counter()-start;self.reasons[reason]=self.reasons.get(reason,0)+1;self.proofs[(a,b)]={'covers':ok,'reason':reason,'edge_recall':recall,'weakest_tile_recall':worst};return ok
 def numbered(self,t):
  f=self.get(t);result=set()
  for _,y,_,v,b,_ in f['boxes']:
   value=str(b.get('text',''));m=re.match(r'^\s*[【\[]?例\s*(\d{1,2})',value)
   if m and (y+v)/2<360*.85:result.add(int(m.group(1)))
  return result
 def same_page(self,a,b,occ):
  fa,fb=self.get(a),self.get(b);na,nb=self.numbered(a),self.numbered(b)
  if na and nb and (na.isdisjoint(nb) or (len(na)>1)!=(len(nb)>1)):return False
  def frame(t,f):
   return occ.Frame(t,cv2.resize(f['gray'],(320,180)),cv2.resize(f['allowed'].astype(np.uint8),(320,180),interpolation=cv2.INTER_NEAREST).astype(bool),cv2.resize(f['person'].astype(np.uint8),(320,180),interpolation=cv2.INTER_NEAREST).astype(bool),self.visuals[t]['ocrBlocks'],(f['width'],f['height']),True)
  result=occ.compare(frame(a,fa),frame(b,fb))
  if result['relation']=='new':return False
  return result['relation']=='same' or self.covers(a,b) or self.covers(b,a)

def collections(pages,store,occ):
 result=[]
 for page in pages:
  current=page['representativeFrameTimesMs'][-1];linked=False
  if result:
   chain=result[-1];prev=chain['representatives'][-1];anchor=chain['representatives'][0]
   linked=store.same_page(prev,current,occ) and store.same_page(anchor,current,occ)
  if not linked:result.append({'groups':[],'representatives':[],'members':[],'pages':[]})
  c=result[-1];c['groups'].append(page['pageIndex']);c['representatives']+=page['representativeFrameTimesMs'];c['members']+=page['memberFrameTimesMs'];c['pages'].append(page)
 return result

def search_candidates(chain,store):
 result={};original=set(chain['representatives']);pages=chain['pages']
 for i,page in enumerate(pages):
  pool=sorted({t for p in pages[max(0,i-1):i+2] for t in p['memberFrameTimesMs']} - original)
  for source in page['representativeFrameTimesMs']:
   if not store.blocked(source):continue
   source_text={canon(b.get('text','')) for b in store.visuals[source]['ocrBlocks'] if b.get('score',1)>=.75}
   def rank(t):
    texts={canon(b.get('text','')) for b in store.visuals[t]['ocrBlocks'] if b.get('score',1)>=.75};shared=sum(len(x) for x in source_text&texts)
    return (store.index[t]['person_pixels']>0,-shared,-t)
   result[source]=sorted(pool,key=rank)[:2]
 return result
