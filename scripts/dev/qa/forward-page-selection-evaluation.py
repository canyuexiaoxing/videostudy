"""Benchmark forward-only representative replacement with optional bounded lookup."""
import sys,os,socket,json,time,statistics,importlib.util,hashlib
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'));HERE=Path(__file__).resolve().parent

def load(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
p=load('forward','forward-page-selection-probe.py');occ=load('occ','occlusion-grouping-probe.py')
INPUT=ROOT/'.local/qa/grouping-multi-20261017';MASK=ROOT/'.local/qa/occlusion-grouping-20261018';POLICY=os.environ.get('FORWARD_QA_POLICY','strict');OUT=ROOT/'.local/qa'/('forward-selection-20261018' if POLICY=='strict' else 'forward-selection-20261018-tolerant')
COURSES=[('d517b4f7-58d3-483d-bd9f-a0966341461b','增长量新'),('56ac6493-3085-45e2-b9c4-130b583b95d1','极限题'),('cbacd60e-c271-48b2-9353-2bc88d7c2aec','增长量旧'),('427ff2cd-8534-4f04-bc75-0a275c9e918b','幂级数')]
def blocked(*a,**kw):raise RuntimeError('no_network_in_offline_qa')
socket.socket.connect=blocked;socket.create_connection=blocked

def evaluate():
 OUT.mkdir(parents=True,exist_ok=False);metadata=json.loads((INPUT/'metadata.json').read_text());report={'scope':'Representative-first forward replacement; existing JPG/OCR/masks only; 4 records/3 distinct videos; 3 alternating timing runs; no paid calls, OCR, ASR, YOLO or video decode.','rules':{'policy':POLICY,'global_visible_edge_recall':.995 if POLICY=='strict' else .97,'minimum_local_tile_recall':.98 if POLICY=='strict' else .75,'minimum_ocr_block_recall':.98 if POLICY=='strict' else .90,'critical_ocr_requires_exact_spatial_match':True,'candidate_reads_per_relation':2,'candidate_reads_per_course':16,'same_page_search_window':'previous/current/next original group, within candidate chain only','retirement_requires_direct_final_target_coverage':True},'limitations':['Visible-stroke coverage and OCR checks are local image heuristics, not mathematical completeness proof.','Mask absence does not prove no occlusion; missed arms remain a limitation.','Candidates are tentative same-page chains, not product grouping changes.','Unknown/erased/revised content is retained when coverage cannot be established.','Frame files are never deleted; only proposed model-input selection changes.','Timing includes prototype image rereads/feature recomputation under bounded LRU.','Mask cache already exists from previous run; inference acquisition cost is excluded and separately documented there.'],'results':[]}
 for course,label in COURSES:
  path=INPUT/f'{course}.json';record=json.loads(path.read_text(encoding='utf-8'));pages=record['pageGroups'];source_digest=hashlib.sha256(path.read_bytes()).hexdigest();region=json.loads(metadata[course]['region']) if metadata[course]['region'] else None
  folder=ROOT/'.local/keyframes'/course;original=sorted({t for page in pages for t in page['representativeFrameTimesMs']});trials={'representatives_only':[],'with_member_search':[]};last={}
  for repeat in range(3):
   names=['representatives_only','with_member_search'];names=names if repeat%2==0 else names[::-1]
   for name in names:
    start=time.perf_counter();init=time.perf_counter();store=p.Store(course,record['visualEvidence'],folder,region,MASK,policy=POLICY);init_s=time.perf_counter()-init
    stage=time.perf_counter();chains=p.collections(pages,store,occ);identity_s=time.perf_counter()-stage
    results=[];remaining=16;search_metadata_s=0.
    for c in chains:
     stage=time.perf_counter();candidates=p.search_candidates(c,store) if name=='with_member_search' else {};search_metadata_s+=time.perf_counter()-stage
     selected=p.forward(c['representatives'],store,candidates,remaining if name=='with_member_search' else 0);remaining-=selected['extra_reads']
     results.append({k:c[k] for k in ('groups','representatives','members')}|selected)
    elapsed=time.perf_counter()-start;chosen=sorted({t for c in results for t in c['selected']});proofs=[proof for c in results for proof in c['proofs']]
    assert set(original)-set(chosen)=={x['removed'] for x in proofs};assert all(x['retained'] in chosen for x in proofs);assert len(chosen)<=len(original)
    value={'total_s':elapsed,'mask_init_s':init_s,'same_page_s':identity_s,'search_metadata_s':search_metadata_s,'image_features_s':store.load_s,'coverage_compare_s':store.compare_s,'physical_image_loads':store.loads,'cache_peak_mib':store.cache_peak/2**20,'extra_reads':16-remaining,'selected':chosen,'proofs':proofs,'chains':results,'coverage_reasons':store.reasons,'pair_audit':{f'{a}->{b}':v for (a,b),v in store.proofs.items()}}
    trials[name].append({k:value[k] for k in ('total_s','mask_init_s','same_page_s','search_metadata_s','image_features_s','coverage_compare_s','physical_image_loads','cache_peak_mib','extra_reads')});last[name]=value
    print(json.dumps({'course':label,'run':repeat+1,'variant':name,'original':len(original),'selected':len(chosen),'chain_count':len(chains),'extra_reads':value['extra_reads'],'seconds':round(elapsed,3)},ensure_ascii=False),flush=True)
  row={'course':course,'label':label,'original_groups':len(pages),'original_representatives':original,'snapshot_sha256':source_digest,'cases':{}}
  for name,value in last.items():
   row['cases'][name]=value|{'samples':trials[name],'median_s':statistics.median(t['total_s'] for t in trials[name]),'max_s':max(t['total_s'] for t in trials[name]),'min_s':min(t['total_s'] for t in trials[name])}
  assert source_digest==hashlib.sha256(path.read_bytes()).hexdigest();report['results'].append(row);(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');review(row,folder)
 print('REPORT '+str(OUT/'report.json'),flush=True)

def review(row,folder):
 import html
 sections=[];tiles=[]
 for name,value in row['cases'].items():
  sections.append('<h2>'+name+'</h2>')
  for c in value['chains']:
   if not c['proofs'] and not c['search_attempts']:continue
   sections.append('<h3>Source groups '+str(c['groups'])+'</h3>')
   for proof in c['proofs']:
    audit=value['pair_audit'].get(f"{proof['removed']}->{proof['retained']}",{})
    sections.append('<p>'+html.escape(json.dumps(proof|audit,ensure_ascii=False))+'</p>')
    for t in (proof['removed'],proof['retained']):sections.append(f'<figure><figcaption>{t/1000:.1f}s</figcaption><img loading="lazy" src="../../keyframes/{row["course"]}/{t}.jpg"></figure>')
   sections.append('<pre>'+html.escape(json.dumps(c['search_attempts'],ensure_ascii=False,indent=2))+'</pre>')
 chosen=row['cases']['with_member_search'];pairs=[(x['removed'],x['retained']) for x in chosen['proofs']]
 pairs += [(attempt['source'],attempt['candidate']) for c in chosen['chains'] for attempt in c['search_attempts']]
 for a,b in list(dict.fromkeys(pairs)):
  for t,caption in ((a,'source'),(b,'target/candidate')):
   im=cv2.imread(str(folder/f'{t}.jpg'));h,w=im.shape[:2];im=cv2.resize(im,(640,360));cv2.putText(im,f'{caption}: {t/1000:.1f}s',(5,24),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,255),2);tiles.append(im)
 if tiles:cv2.imwrite(str(OUT/f'{row["course"]}-changes.jpg'),np.vstack([np.hstack(tiles[i:i+2]) for i in range(0,len(tiles),2)]))
 (OUT/f'{row["course"]}-review.html').write_text('<meta charset="utf-8"><style>figure{display:inline-block;width:46%;margin:1%}img{width:100%}pre{white-space:pre-wrap}</style><h1>'+row['label']+'</h1>'+''.join(sections),encoding='utf-8')
if __name__=='__main__':evaluate()
