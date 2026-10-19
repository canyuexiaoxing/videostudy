"""Offline timing of person-aware grouping; no model/network requests here."""
import sys,os,importlib.util,json,time,statistics,hashlib,socket
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'));HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('occ',HERE/'occlusion-grouping-probe.py');p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
import slide_grouping as g
from ignored_region import effective_mask
OUT=ROOT/'.local/qa/occlusion-grouping-20261018';INPUT=ROOT/'.local/qa/grouping-multi-20261017'
COURSES=[('d517b4f7-58d3-483d-bd9f-a0966341461b','增长量新'),('56ac6493-3085-45e2-b9c4-130b583b95d1','极限题'),('cbacd60e-c271-48b2-9353-2bc88d7c2aec','增长量旧'),('427ff2cd-8534-4f04-bc75-0a275c9e918b','幂级数')]
def blocked(*a,**k):raise RuntimeError('offline_network_forbidden')
socket.socket.connect=blocked;socket.create_connection=blocked

def load_frames(course,record,region,masking):
 start=time.perf_counter();index=json.loads((OUT/f'{course}-mask-index.json').read_text());meta={x['time_ms']:x for x in index['frames']};mask_file=OUT/f'{course}-masks.npz'
 masks={};read_masks=time.perf_counter()
 with np.load(mask_file) as packed:
  for t in meta:masks[t]=np.unpackbits(packed[str(t)])[:180*320].reshape(180,320).astype(bool)
 mask_load_s=time.perf_counter()-read_masks;frames={};image_read_s=0.;fingerprint_s=0.
 for item in record['visualEvidence']:
  t=item['frameTimeMs'];path=ROOT/'.local/keyframes'/course/f'{t}.jpg';begin=time.perf_counter();raw=path.read_bytes();im=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_GRAYSCALE)
  if im is None:raise ValueError('frame_unreadable')
  h,w=im.shape;gray=cv2.resize(im,(320,180),interpolation=cv2.INTER_AREA);image_read_s+=time.perf_counter()-begin
  begin=time.perf_counter();assert hashlib.sha256(raw).hexdigest()==meta[t]['sha256'];assert (w,h)==(meta[t]['width'],meta[t]['height']);fingerprint_s+=time.perf_counter()-begin
  allowed=effective_mask(320,180,region,t) if region else np.ones((180,320),bool)
  frames[t]=p.Frame(t,gray,allowed,masks[t] if masking else np.zeros((180,320),bool),item['ocrBlocks'],(w,h),True)
 return frames,{'prepare_s':time.perf_counter()-start,'mask_load_s':mask_load_s,'image_read_resize_s':image_read_s,'fingerprint_s':fingerprint_s,'retained_arrays_bytes':sum(f.gray.nbytes+f.allowed.nbytes+f.person.nbytes for f in frames.values())}

def run():
 meta=json.loads((INPUT/'metadata.json').read_text());report={'scope':'4 task snapshots, 3 distinct courses; existing screenshots/OCR only; 3 alternating runs; baseline unchanged; no production writes','runs':3,'results':[],'limitations':['Post-group candidate collections, not production group replacement.','All original representatives kept. Supplements are only proposals for exposed pixels, not proven missing mathematics.','Existing 72% groups are immutable; the probe never re-splits a potentially incorrect original group.','Baseline inference cost is zero only because existing segmentation would have run during coarse selection; persistence is not yet wired into production.','History refers to up to eight real frames, not a pixel mosaic; missed masks can still lead to wrong comparisons.','Cold startup measured separately; mask persistence write measured once, not three repeats.','3 runs are not enough to establish course-level p95.']}
 for course,label in COURSES:
  source=INPUT/f'{course}.json';record=json.loads(source.read_text(encoding='utf-8'));region=json.loads(meta[course]['region']) if meta[course]['region'] else None
  before=hashlib.sha256(source.read_bytes()).hexdigest();trials=[];last={}
  for repeat in range(3):
   # Baseline replay is separately timed and uses original local conservative stub.
   start=time.perf_counter();pages,_=g.group_pages(record['visualEvidence'],ROOT/'.local/keyframes'/course,record['segments'],ask_json=lambda _:{'samePage':False,'reason':'offline conservative split'},ignore_region=region);baseline_s=time.perf_counter()-start
   assert [x['memberFrameTimesMs'] for x in pages]==[x['memberFrameTimesMs'] for x in record['pageGroups']]
   values={};order=['no_mask_history','mask_adjacent','mask_history'];order=order if repeat%2==0 else order[::-1]
   for name in order:
    start=time.perf_counter();frames,prep=load_frames(course,record,region,masking=name!='no_mask_history');result=p.collect(pages,frames,use_history=name!='mask_adjacent');extra=time.perf_counter()-start
    value=dict(result,**prep,extra_s=extra,total_s=baseline_s+extra);values[name]=value;last[name]=value
    assert set(t for page in pages for t in page['representativeFrameTimesMs'])==set(value['selected'])
   trials.append({'baseline_s':baseline_s,'cases':values})
   print(json.dumps({'course':label,'run':repeat+1,'baseline':len(pages),'no_mask':len(values['no_mask_history']['collections']),'mask_adjacent':len(values['mask_adjacent']['collections']),'mask_history':len(values['mask_history']['collections']),'extra_s':round(values['mask_history']['extra_s'],3)},ensure_ascii=False),flush=True)
  row={'course':course,'label':label,'frames':len(record['visualEvidence']),'original_groups':len(record['pageGroups']),'original_images':len({t for page in pages for t in page['representativeFrameTimesMs']}),'snapshot_sha256':before,'baseline_median_s':statistics.median(t['baseline_s'] for t in trials),'baseline_samples_s':[t['baseline_s'] for t in trials],'cases':{}}
  assert before==hashlib.sha256(source.read_bytes()).hexdigest()
  for name,value in last.items():
   samples=[t['cases'][name] for t in trials];assert all(x['collections']==value['collections'] for x in samples)
   row['cases'][name]={'collections':value['collections'],'decisions':value['decisions'],'selected':value['selected'],'supplements':value['supplements'],'entries':len(value['collections']),'cache_mib':value['retained_arrays_bytes']/2**20,'samples':[{k:x[k] for k in ('prepare_s','mask_load_s','image_read_resize_s','fingerprint_s','compare_s','extra_s','total_s')} for x in samples],**{key+'_median':statistics.median(x[key] for x in samples) for key in ('prepare_s','mask_load_s','image_read_resize_s','fingerprint_s','compare_s','extra_s','total_s')}}
  report['results'].append(row);(OUT/'grouping-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  review(course,label,row,record)
 print('saved '+str(OUT/'grouping-report.json'),flush=True)

def review(course,label,row,record):
 # Shared endpoints for every mask-dependent decision, plus positive detections.
 import html
 index=json.loads((OUT/f'{course}-mask-index.json').read_text());positive=[x for x in index['frames'] if x['person_pixels']>0]
 original={f['frameTimeMs']:f for f in record['visualEvidence']};panels=[];seen=set();npz=np.load(OUT/f'{course}-masks.npz');blocks=[]
 for mode in ('no_mask_history','mask_adjacent','mask_history'):
  blocks.append('<h2>'+mode+'</h2>')
  for d in row['cases'][mode]['decisions']:
   blocks.append('<p>'+html.escape(json.dumps(d,ensure_ascii=False))+'</p>')
   if d['merged']:
    for t in (d.get('reference_time_ms'),d.get('query_time_ms')):
     if t is not None:blocks.append(f'<img loading="lazy" style="width:45%" src="../../keyframes/{course}/{t}.jpg">')
 for f in sorted(positive,key=lambda f:f['person_pixels'],reverse=True)[:8]:
  t=f['time_ms'];im=cv2.imread(str(ROOT/'.local/keyframes'/course/f'{t}.jpg'));h,w=im.shape[:2];im=cv2.resize(im,(640,360));mask=np.unpackbits(npz[str(t)])[:57600].reshape(180,320).astype(bool);mask=cv2.resize(mask.astype(np.uint8),(640,360),interpolation=cv2.INTER_NEAREST).astype(bool)
  im[mask]=(im[mask]*.5+np.array([0,180,255])*.5).astype(np.uint8)
  cv2.putText(im,f'{t/1000:.1f}s mask={f["person_pixels"]/57600:.3f}',(5,25),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,255),2);panels.append(im)
 if panels:
  while len(panels)%2:panels.append(np.full((360,640,3),255,np.uint8))
  cv2.imwrite(str(OUT/f'{course}-mask-review.jpg'),np.vstack([np.hstack(panels[i:i+2]) for i in range(0,len(panels),2)]))
 (OUT/f'{course}-review.html').write_text('<meta charset="utf-8"><h1>'+label+'</h1>'+''.join(blocks),encoding='utf-8')
 npz.close()
if __name__=='__main__':run()
