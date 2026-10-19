"""Controlled occluders on real saved blackboard pixels. Not YOLO accuracy data."""
import sys,importlib.util,json,time,statistics
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'));OUT=ROOT/'.local/qa/occlusion-grouping-20261018';HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('occ',HERE/'occlusion-grouping-probe.py');p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
import slide_grouping as g
course='427ff2cd-8534-4f04-bc75-0a275c9e918b';data=json.loads((ROOT/'.local/qa/grouping-multi-20261017'/f'{course}.json').read_text(encoding='utf-8'));meta={f['frameTimeMs']:f for f in data['visualEvidence']}
def scene(source,t,rect=None):
 raw=cv2.imread(str(ROOT/'.local/keyframes'/course/f'{source}.jpg'),cv2.IMREAD_GRAYSCALE);h,w=raw.shape;gray=cv2.resize(raw,(320,180),interpolation=cv2.INTER_AREA);mask=np.zeros((180,320),bool)
 if rect:
  x,y,z,v=rect;mask[round(y*180):round(v*180),round(x*320):round(z*320)]=True
 gray[mask]=100;f=p.Frame(t,gray,np.ones_like(mask),mask,meta[source]['ocrBlocks'],(w,h),True);f.blocks=[b for b,_ in p.visible_blocks(f,f.visible())];return f
base=scene(490000,0);left=scene(490000,1,(0,0,.65,1));right=scene(490000,2,(.35,0,1,1));mildleft=scene(490000,3,(0,.35,.3,1));mildright=scene(490000,4,(.7,.35,1,1));allhidden=scene(490000,5,(0,0,1,1));final=scene(1452000,6);old=scene(1386000,7);different=scene(858000,8)
cases=[('teacher_moves_common_center',[mildleft],mildright,'same'),('disjoint_visibility_without_history',[left],right,'unknown'),('disjoint_visibility_with_earlier_clear',[base,left],right,'same'),('erased_derivation_final_answer_same_question',[old],final,'same'),('different_question_same_blackboard',[base],different,'new'),('hidden_content_cannot_be_inferred',[allhidden],final,'unknown')]
report={'scope':'Real background images and saved OCR with generated opaque rectangles + known masks; no claim about real-person segmentation accuracy. No OCR rerun; covered OCR blocks omitted mechanically.','cases':[]};tiles=[]
for label,history,current,expected in cases:
 a=history[-1];before={'ocrBlocks':a.blocks};now={'ocrBlocks':current.blocks};local=g._boundary(before,before,now,a.gray,a.gray,current.gray);baseline='same' if local=='same' else 'new' # direct mode conservatively splits uncertain
 samples=[]
 for _ in range(50):
  start=time.perf_counter();value=p.resolve(history,current,use_history=True);samples.append(time.perf_counter()-start)
 adjacent=p.resolve(history,current,use_history=False)
 row={'label':label,'expected_evidence_decision':expected,'original_local_boundary':local,'original_direct_effect':baseline,'mask_adjacent':adjacent,'mask_history':value,'decision_matches_expected':value['relation']==expected,'history_compare_median_ms':statistics.median(samples)*1000,'history_compare_p95_ms':float(np.percentile(samples,95))*1000};report['cases'].append(row)
 for f,caption in ((a,'previous'),(current,'current')):
  im=cv2.cvtColor(cv2.resize(f.gray,(640,360)),cv2.COLOR_GRAY2BGR);cv2.putText(im,label,(5,18),cv2.FONT_HERSHEY_SIMPLEX,.35,(0,0,255),1);cv2.putText(im,caption+' expected='+expected+' history='+value['relation'],(5,37),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,255),1);tiles.append(im)
(OUT/'controlled-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');cv2.imwrite(str(OUT/'controlled-contact.jpg'),np.vstack([np.hstack(tiles[i:i+2]) for i in range(0,len(tiles),2)]))
print(json.dumps([{'case':r['label'],'expected':r['expected_evidence_decision'],'actual':r['mask_history']['relation'],'baseline':r['original_direct_effect']} for r in report['cases']],indent=2),flush=True)
