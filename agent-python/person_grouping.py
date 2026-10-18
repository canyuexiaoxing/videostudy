"""Narrow opt-in grouping correction when real person masks explain lost OCR."""
import re,time
import cv2,numpy as np
from person_visibility import load_visibility
from frame_run_guard import FrameRunGuard
from model_diagnostics import record_event
MAX_PENDING_FRAMES=8
class PersonGrouping:
 def __init__(self,root,dimensions,masks):
  self.root=root;self.dimensions=dimensions;self.allowed=masks;self.cache={};self.accepted=0;self.missing=0;self.adjusted=0;self.pending=0;self.started=time.perf_counter();self.guard=FrameRunGuard(root/'.analysis')
 def mask(self,t):
  if t not in self.cache:
   self.guard.check();self.cache[t]=load_visibility(self.root,t,self.dimensions[t],_check=self.guard.check)
   if self.cache[t] is None:self.missing+=1
   else:self.accepted+=1
  return self.cache[t]
 def region(self,t):return self.allowed[t] if self.allowed is not None else np.ones((180,320),bool)
 def has_person(self,t):
  mask=self.mask(t);allowed=self.region(t)
  return mask is not None and int((mask&allowed).sum())>=max(50,round(int(allowed.sum())*.005))
 def boxes(self,frame):
  width,height=self.dimensions[frame['frameTimeMs']]
  for block in frame.get('ocrBlocks',[]):
   try:
    p=np.asarray(block.get('polygon'),float)
    if p.shape!=(4,2) or not np.isfinite(p).all():continue
    x=max(0,int(np.floor(p[:,0].min()*320/width)));z=min(320,int(np.ceil(p[:,0].max()*320/width)))
    y=max(0,int(np.floor(p[:,1].min()*180/height)));v=min(180,int(np.ceil(p[:,1].max()*180/height)))
    if x<z and y<v:yield block,(x,y,z,v)
   except (ValueError,TypeError):continue
 def filtered(self,frame,common):
  blocks=[b for b,(x,y,z,v) in self.boxes(frame) if float(common[y:v,x:z].mean())>=.9]
  return dict(frame,ocrBlocks=blocks)
 def anchors(self,left,right,normalized):
  result=[];targets=list(self.boxes(right))
  for a,(x,y,z,v) in self.boxes(left):
   text=normalized(str(a.get('text','')))
   if a.get('score',1)<.5 or len(text)<6 or not .15*180<=(y+v)/2<=.85*180:continue
   for b,(xx,yy,zz,vv) in targets:
    if b.get('score',1)<.5 or text!=normalized(str(b.get('text',''))):continue
    overlap=max(0,min(z,zz)-max(x,xx))*max(0,min(v,vv)-max(y,yy));union=(z-x)*(v-y)+(zz-xx)*(vv-yy)-overlap
    if overlap/max(1,union)>=.5:result.append(text);break
  return len(set(result))>=2 and sum(map(len,set(result)))>=20
 def question_conflict(self,left,right):
  def stems(frame):
   values=[]
   for b,box in self.boxes(frame):
    if (box[1]+box[3])/2>180*.4 or b.get('score',1)<.75:continue
    m=re.match(r'^\s*(?:[【\[]?例\s*(\d+)|(\d+)\s*[.．、]|(?:example|question)\s+(\d+))',str(b.get('text','')),re.I)
    if m:values.append((int(next(x for x in m.groups() if x is not None)),box))
   return values
  return any(a!=b and abs((box[1]+box[3]-other[1]-other[3])/2)<180*.06 for a,box in stems(left) for b,other in stems(right))
 def decide(self,anchor,previous,current,images,analysis_mask,baseline,boundary,texts,retention,normalized):
  frames=(anchor,previous,current);times=[f['frameTimeMs'] for f in frames];people=[self.mask(t) for t in times]
  if any(mask is None for mask in people):return None
  allowed=analysis_mask if analysis_mask is not None else np.ones((180,320),bool)
  common=allowed&~(people[0]|people[1]|people[2]);fraction=int(common.sum())/max(1,int(allowed.sum()))
  if self.question_conflict(self.filtered(anchor,common),self.filtered(current,common)):return {'boundary':'new','reason':'different visible question number'}
  if not any(self.has_person(t) for t in times):return None
  def lost_under_person(source):
   now=texts(current)
   occluders=people[2]|self.mask(source['frameTimeMs'])
   return any(retention([normalized(str(b.get('text','')))],now)<.72 and float(occluders[y:v,x:z].mean())>=.1 for b,(x,y,z,v) in self.boxes(source) if b.get('score',1)>=.35 and len(normalized(str(b.get('text',''))))>=2)
  explained=lost_under_person(anchor) or lost_under_person(previous)
  if fraction<.35 and explained:
   self.pending+=1;return {'boundary':'defer','reason':'person occlusion; insufficient common visible content'}
  if baseline=='same' or not explained:return None
  a,p,c=(self.filtered(f,common) for f in frames)
  sufficient=self.anchors(a,c,normalized) and self.anchors(p,c,normalized)
  masked=boundary(a,p,c,images[times[0]],images[times[1]],images[times[2]],common) if sufficient else 'uncertain'
  if sufficient and masked=='same':
   self.adjusted+=1;return {'boundary':'same','reason':'same visible body text; missing OCR lies under person mask'}
  self.pending+=1;return {'boundary':'defer','reason':'person occlusion; page identity pending'}
 def finish(self,pages):
  record_event('stage_completed',self.root.name,operation='person_grouping',stage='page_grouping',image_count=len(self.dimensions),accepted_count=self.accepted,rejected_count=self.missing,promoted_count=self.adjusted,uncertain_frames=self.pending,topics=len(pages),elapsed_ms=round((time.perf_counter()-self.started)*1000))
