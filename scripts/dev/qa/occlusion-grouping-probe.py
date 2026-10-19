"""Offline-only person-aware post-group collection probe. Product grouping unchanged.
All comparisons are between two real source frames at matching coordinates;
no pixel mosaic and no claim of mathematical content completeness.
"""
import time,re
from pathlib import Path
import cv2,numpy as np
import slide_grouping as g
class Frame:
 def __init__(self,time_ms,gray,allowed,person,blocks,size,mask_known=True):
  self.time_ms=time_ms;self.gray=gray;self.allowed=allowed;self.person=person;self.blocks=blocks;self.size=size;self.mask_known=mask_known
 def visible(self):return self.allowed&~self.person

def visible_blocks(frame,common):
 w,h=frame.size;out=[]
 for b in frame.blocks:
  try:
   p=np.asarray(b.get('polygon'),float)
   if p.shape!=(4,2) or not np.isfinite(p).all():continue
   x=max(0,int(np.floor(p[:,0].min()*320/w)));z=min(320,int(np.ceil(p[:,0].max()*320/w)))
   y=max(0,int(np.floor(p[:,1].min()*180/h)));v=min(180,int(np.ceil(p[:,1].max()*180/h)))
   if z<=x or v<=y or float(common[y:v,x:z].mean())<.92:continue
   if b.get('score',1)<.35:continue
   out.append((b,(x,y,z,v)))
  except (ValueError,TypeError):continue
 return out

def stable_anchors(left,right):
 matches=[]
 for a,box in left:
  value=g._normalized(a.get('text',''))
  # Avoid accepting a common course title as problem identity.
  if len(value)<4 or not 180*.16<=(box[1]+box[3])/2<=180*.80 or a.get('score',1)<.75:continue
  for b,other in right:
   if b.get('score',1)<.75 or value!=g._normalized(b.get('text','')):continue
   x,y,z,v=box;xx,yy,zz,vv=other
   overlap=max(0,min(z,zz)-max(x,xx))*max(0,min(v,vv)-max(y,yy));union=(z-x)*(v-y)+(zz-xx)*(vv-yy)-overlap
   if overlap/max(union,1)>=.5:matches.append(value);break
 return len(set(matches)),sum(map(len,set(matches)))

def numbered_stems(blocks):
 result=[]
 for block,box in blocks:
  if block.get('score',1)<.75 or (box[1]+box[3])/2>180*.4 or box[0]>320*.65:continue
  match=re.match(r'^\s*(?:[【\[]?例\s*(\d{1,2})|(\d{1,2})\s*[.．、])',str(block.get('text','')))
  if match:result.append((int(match.group(1) or match.group(2)),box))
 return result

def numbered_conflict(left,right):
 for a,box in numbered_stems(left):
  for b,other in numbered_stems(right):
   if a!=b and abs((box[1]+box[3]-other[1]-other[3])/2)<180*.06 and abs(box[0]-other[0])<320*.12:return True
 return False
def compare(a,b):
 result={'relation':'unknown','reason':'insufficient_shared_evidence','reference_time_ms':a.time_ms,'query_time_ms':b.time_ms}
 if not a.mask_known or not b.mask_known:return dict(result,reason='mask_unknown')
 common=a.visible()&b.visible();allowed=a.allowed&b.allowed
 fraction=float(common.sum())/max(1,int(allowed.sum()));result['common_visible_fraction']=fraction
 if fraction<.2:return dict(result,reason='too_little_common_visible')
 left,right=visible_blocks(a,common),visible_blocks(b,common)
 if numbered_conflict(left,right):return dict(result,relation='new',reason='visible_question_number_changed')
 fa={'ocrBlocks':[x for x,_ in left]};fb={'ocrBlocks':[x for x,_ in right]}
 before,now=g._texts(fa),g._texts(fb);count,characters=stable_anchors(left,right)
 difference=g._difference(a.gray,b.gray,common);retained=g._retention(before,now)
 result.update(shared_anchors=count,shared_anchor_chars=characters,pixel_difference=difference,ocr_retention=retained)
 strong=count>=2 and characters>=20
 boundary=g._boundary(fa,fa,fb,a.gray,a.gray,b.gray,common)
 if strong and (boundary=='same' or difference<.48):return dict(result,relation='same',reason='same_position_body_anchors',content_state='version_or_occlusion_change')
 # Near-identical textured images may support pages with weak OCR, but never
 # use background equality in the presence of conflicting readable body text.
 conflict=bool(before and now and retained<.5)
 texture=int(((cv2.Canny(a.gray,50,120)>0)&common).sum())
 if not conflict and difference<.008 and texture>=150:
  return dict(result,relation='same',reason='near_identical_visible_texture',content_state='unknown')
 if len(before)>=2 and len(now)>=2 and retained<=.25 and not strong and difference>.04:
  return dict(result,relation='new',reason='visible_body_replaced')
 return result

def resolve(history,current,use_history=True):
 if not history:return {'relation':'unknown','reason':'no_reference','query_time_ms':current.time_ms}
 adjacent=compare(history[-1],current)
 if not use_history or adjacent['relation'] in ('same','new'):return adjacent
 refs=history[:-1];refs=refs if len(refs)<=7 else [refs[0],*refs[-6:]]
 outcomes=[compare(ref,current) for ref in reversed(refs)]
 same=[x for x in outcomes if x['relation']=='same'];different=[x for x in outcomes if x['relation']=='new']
 if same and different:return dict(adjacent,reason='history_conflicts')
 if same:return dict(same[0],reason='earlier_real_frame_'+same[0]['reason'])
 if different:return different[0]
 return adjacent

def collect(pages,frames,use_history=True):
 start=time.perf_counter();collections=[];decisions=[];history=[]
 for page in pages:
  times=page['memberFrameTimesMs'];queries=list(dict.fromkeys([times[0],*page['representativeFrameTimesMs'],times[-1]]))
  outcomes=[resolve(history,frames[t],use_history) for t in queries] if history else []
  same=[x for x in outcomes if x['relation']=='same'];different=[x for x in outcomes if x['relation']=='new']
  merge=bool(same) and not different
  if outcomes:
   evidence=(same[0] if merge else different[0] if different else outcomes[0]);decisions.append(dict(evidence,previous_page_index=pages[len(decisions)]['pageIndex'],current_page_index=page['pageIndex'],merged=merge))
  if merge and use_history:
   ref=same[0]['reference_time_ms']
   owner=next((i for i,c in enumerate(collections) if ref in c['memberFrameTimesMs']),len(collections)-1)
   if owner<len(collections)-1 and all(c.get('pending_only') for c in collections[owner+1:]):
    base=collections[owner]
    for tail in collections[owner+1:]:
     for field in ('sourcePageIndices','memberFrameTimesMs','representativeFrameTimesMs'):base[field].extend(tail[field])
    base['rejoined_occluded_fragments']=True;collections=collections[:owner+1]
  if not merge:
   pending=bool(outcomes) and all(x['reason'] in ('too_little_common_visible','mask_unknown') for x in outcomes)
   collections.append({'sourcePageIndices':[],'memberFrameTimesMs':[],'representativeFrameTimesMs':[],'supplementTimesMs':[],'visibility':'unknown','pending_only':pending})
   # Unknown splits remain separate; retain previous references for a later
   # query, but a confirmed new page resets the comparison history.
   if different:history=[]
  c=collections[-1];c['sourcePageIndices'].append(page['pageIndex']);c['memberFrameTimesMs'].extend(times);c['representativeFrameTimesMs'].extend(page['representativeFrameTimesMs'])
  history.extend(frames[t] for t in times)
  if len(history)>8:history=[history[0],*history[-7:]]
 # No baseline image is removed. Suggest additions only for source pixels that
 # every original representative actually masks, with visible edge evidence.
 for c in collections:
  reps=list(dict.fromkeys(c['representativeFrameTimesMs']));known=np.zeros((180,320),bool)
  for t in reps:known|=frames[t].visible()
  for t in c['memberFrameTimesMs']:
   if t in reps:continue
   f=frames[t];revealed=f.visible()&~known;edges=(cv2.Canny(f.gray,50,120)>0)&revealed
   if int(revealed.sum())>=50 and int(edges.sum())>=12:
    c['supplementTimesMs'].append(t);known|=f.visible()
  c['representativeFrameTimesMs']=reps
  c['uncovered_person_pixels']=int((np.logical_or.reduce([frames[t].allowed for t in c['memberFrameTimesMs']])&~known).sum())
 return {'collections':collections,'decisions':decisions,'compare_s':time.perf_counter()-start,'selected':sorted({t for c in collections for t in c['representativeFrameTimesMs']}),'supplements':sorted({t for c in collections for t in c['supplementTimesMs']})}
