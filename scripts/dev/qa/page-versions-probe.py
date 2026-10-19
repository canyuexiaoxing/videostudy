"""Throwaway page collection/version probe, never imported by product code.
Conservative first slice: spatial anchors + gray-image consistency for collections;
keep original representatives, inspect at most 16 existing images for OCR novelty;
retire only byte-identical images with identical OCR and effective region.
No person classifier, semantic coverage claim, cloud requests, or historical writes.
"""
import hashlib,json,re,time
from pathlib import Path
import cv2,numpy as np
VERSION='offline-page-versions-v1'
def text(value):return re.sub(r'\s+','',str(value)).casefold()
def tokens(frame):
 return {text(b.get('text','')) for b in frame.get('ocrBlocks',[]) if b.get('score',1)>=.85 and len(text(b.get('text','')))>=2}
def ocr_signature(frame):
 return json.dumps(frame.get('ocrBlocks',[]),sort_keys=True,ensure_ascii=False)
def anchor_match(left,right):
 matches=[]
 for a,box in left:
  if len(a)<4:continue
  for b,other in right:
   if a!=b:continue
   x,y,z,w=box;xx,yy,zz,ww=other
   area=max(0,min(z,zz)-max(x,xx))*max(0,min(w,ww)-max(y,yy))
   union=(z-x)*(w-y)+(zz-xx)*(ww-yy)-area
   if area/max(union,1e-9)>=.5:matches.append(a);break
 return len(set(matches))>=2 and sum(map(len,set(matches)))>=20

def add_candidates(originals,extras,limit):
 added=[t for _,t in sorted(extras,reverse=True) if t not in originals][:limit]
 return sorted(set(originals)|set(added))

def exact_duplicates(times,folder,frames,regions):
 seen={};proofs=[]
 for t in sorted(set(times),reverse=True):
  path=folder/f'{t}.jpg'
  # Exact file equality is intentionally stronger than heuristic edge coverage.
  key=(hashlib.sha256(path.read_bytes()).hexdigest(),ocr_signature(frames[t]),json.dumps(regions.get(t),sort_keys=True))
  if key in seen:proofs.append({'removed':t,'retained':seen[key]})
  else:seen[key]=t
 return sorted(seen.values()),proofs

def collect(pages,visuals,folder,region=None,protect=False):
 from ignored_region import filter_frame,effective_mask,region_at
 import slide_grouping as g
 start=time.perf_counter();frames={f['frameTimeMs']:f for f in visuals};filtered={};previews={};masks={};anchors={};regions={}
 originals=sorted({t for page in pages for t in page['representativeFrameTimesMs']})
 # Cache only small grayscale previews; no full-HD image cache.
 def load(t):
  if t not in previews:
   raw=cv2.imread(str(folder/f'{t}.jpg'),cv2.IMREAD_GRAYSCALE)
   if raw is None:raise FileNotFoundError('prototype_frame_missing')
   h,w=raw.shape;previews[t]=cv2.resize(raw,(320,180),interpolation=cv2.INTER_AREA)
   masks[t]=effective_mask(320,180,region,t) if region else np.ones((180,320),bool)
   f=filter_frame(frames[t],region,t,w,h) if region else frames[t];filtered[t]=f
   anchors[t]=[]
   for b in f.get('ocrBlocks',[]):
    poly=np.asarray(b.get('polygon',[]),float)
    if poly.shape!=(4,2) or b.get('score',1)<.85:continue
    anchors[t].append((text(b.get('text','')),(float(poly[:,0].min()/w),float(poly[:,1].min()/h),float(poly[:,0].max()/w),float(poly[:,1].max()/h))))
   regions[t]=region_at(region,t) if region else None
   if sum(a.nbytes for a in previews.values())+sum(a.nbytes for a in masks.values())>32*1024*1024:raise MemoryError('prototype_cache_budget')
 for t in originals:load(t)
 collections=[]
 for page in pages:
  t=page['representativeFrameTimesMs'][-1];linked=False
  if collections:
   c=collections[-1];a=c['representativeFrameTimesMs'][0];b=c['representativeFrameTimesMs'][-1]
   common=masks[a]&masks[b]&masks[t]
   linked=(common.any() and anchor_match(anchors[b],anchors[t]) and anchor_match(anchors[a],anchors[t])
           and g._retention(g._texts(filtered[b]),g._texts(filtered[t]))>=.65
           and g._difference(previews[a],previews[t],common)<.48)
  if not linked:
   collections.append({'sourcePageIndices':[],'memberFrameTimesMs':[],'representativeFrameTimesMs':[],'relation':'uncertain','visibility':'unknown'})
  c=collections[-1];c['sourcePageIndices'].append(page['pageIndex']);c['memberFrameTimesMs']+=page['memberFrameTimesMs'];c['representativeFrameTimesMs']+=page['representativeFrameTimesMs']
 base_time=time.perf_counter()-start;extra_read=0;extras=[];unresolved=[]
 if protect:
  # Use metadata to rank possible unseen versions. OCR novelty is a review signal,
  # never proof of semantic completeness or erased content.
  for c in collections:
   known=set().union(*(tokens(filtered[t]) for t in c['representativeFrameTimesMs']))
   for t in c['memberFrameTimesMs']:
    if t in c['representativeFrameTimesMs']:continue
    # Filter with representative dimensions only when dimensions are available by
    # loading this candidate; metadata ranking below is deliberately preliminary.
    novelty=tokens(frames[t])-known
    if novelty:extras.append((sum(map(len,novelty)),t))
  chosen=add_candidates(originals,extras,16)
  for t in chosen:
   if t not in originals:load(t);extra_read+=1
  for c in collections:
   reps=c['representativeFrameTimesMs'];known=set().union(*(tokens(filtered[t]) for t in reps))
   for t in chosen:
    if t not in reps and t in c['memberFrameTimesMs'] and tokens(filtered[t])-known:
     reps.append(t);known|=tokens(filtered[t])
   unresolved += [t for _,t in extras if t in c['memberFrameTimesMs'] and t not in reps]
 proofs=[]
 for c in collections:
  kept,proof=exact_duplicates(c['representativeFrameTimesMs'],folder,frames,regions)
  c['representativeFrameTimesMs']=kept;proofs+=proof
  c['collectionId']=hashlib.sha256(json.dumps([VERSION,c['sourcePageIndices'],c['memberFrameTimesMs']],sort_keys=True).encode()).hexdigest()[:16]
 total=time.perf_counter()-start
 return {'collections':collections,'selected':sorted({t for c in collections for t in c['representativeFrameTimesMs']}),'proofs':proofs,'extra_read':extra_read,'unresolved_count':len(set(unresolved)),'base_s':base_time,'extra_s':total,'cache_bytes':sum(a.nbytes for a in previews.values())+sum(a.nbytes for a in masks.values()),'over_budget':total>(1.5 if protect else .5),'status':'experimental_unvalidated','version':VERSION}
