"""Multi-course offline threshold study with persisted task region settings."""
import importlib.util,json,time,statistics,urllib.request,subprocess,argparse
from pathlib import Path
spec=importlib.util.spec_from_file_location('probe',Path(__file__).with_name('grouping-coverage-probe.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ROOT=m.ROOT;OUT=ROOT/'.local/qa/grouping-multi-20261017';OUT.mkdir(parents=True,exist_ok=True)
COURSES=[('d517b4f7-58d3-483d-bd9f-a0966341461b','增长量-新记录','off'),('56ac6493-3085-45e2-b9c4-130b583b95d1','极限题','legacy_off'),('cbacd60e-c271-48b2-9353-2bc88d7c2aec','增长量-旧记录','legacy_off'),('427ff2cd-8534-4f04-bc75-0a275c9e918b','幂级数-YOLO参照','adjacent')]
def fetch(course):
 snapshot=OUT/f'{course}.json'
 if not snapshot.exists():
  with urllib.request.urlopen(f'http://127.0.0.1:18080/api/transcriptions/{course}',timeout=10) as r:record=json.load(r)
  snapshot.write_text(json.dumps(record['result'],ensure_ascii=False),encoding='utf-8')
 return json.loads(snapshot.read_text(encoding='utf-8'))
def metadata():
 p=OUT/'metadata.json'
 if p.exists():return json.loads(p.read_text())
 sql="SELECT JSON_OBJECT('id',id,'mode',person_selection_mode,'region',ignored_region_json) FROM transcription_jobs"
 command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" --raw -Nse "'+sql+'"'
 result=subprocess.run(['D:/mytools/deskdocker/resources/bin/docker.exe','exec','videostudy-mysql-1','sh','-c',command],capture_output=True,text=True,check=True)
 values=[json.loads(line) for line in result.stdout.splitlines() if line.strip()];data={x['id']:x for x in values};p.write_text(json.dumps(data),encoding='utf-8');return data

def main():
 meta=metadata();all_results=[]
 for course,label,mode in COURSES:
  record=fetch(course);frames=record['visualEvidence'];folder=ROOT/'.local/keyframes'/course
  region=json.loads(meta[course]['region']) if meta[course]['region'] else None
  assert meta[course]['mode']==('off' if mode=='off' else 'adjacent' if mode=='adjacent' else None)
  row={'id':course,'label':label,'mode':mode,'frames':len(frames),'region':region,'recorded_groups':len(record['pageGroups']),'thresholds':[]}
  for threshold in (.60,.62,.65,.68,.70,.72):
   samples=[]
   for _ in range(3):
    start=time.perf_counter();pages=m.groups(frames,folder,record['segments'],threshold,region);samples.append(time.perf_counter()-start)
   row['thresholds'].append({'threshold':threshold,'groups':len(pages),'representatives':sum(len(x['representativeFrameTimesMs']) for x in pages),'median_s':statistics.median(samples),'samples_s':samples,'pages':pages})
   print(json.dumps({'label':label,'threshold':threshold,'groups':len(pages),'seconds':round(statistics.median(samples),3)},ensure_ascii=False),flush=True)
  # Prototype comparison uses unchanged source frames, OCR, and the exact task region.
  row['coverage_samples']=[]
  pages=next(x['pages'] for x in row['thresholds'] if x['threshold']==.65)
  for _ in range(3):
   start=time.perf_counter();features=m.Features(frames,folder,region);feature_s=time.perf_counter()-start
   selected=[features.select(p['memberFrameTimesMs'],.93,.5) for p in pages]
   row['coverage_samples'].append({'extra_s':time.perf_counter()-start,'feature_s':feature_s,'representatives':sum(map(len,selected))})
  row['coverage_selected']=selected
  # Exact baseline replay check distinguishes modern behavior from historical AI boundary decisions.
  baseline=next(x['pages'] for x in row['thresholds'] if x['threshold']==.72)
  row['baseline_matches_saved']=([p['memberFrameTimesMs'] for p in baseline]==[p['memberFrameTimesMs'] for p in record['pageGroups']])
  all_results.append(row);(OUT/'report.json').write_text(json.dumps({'scope':'4 task datasets, 3 distinct videos; two distinct no-YOLO videos and a repeated historical control. Existing images/OCR only. Three timing repeats per setting. No network model/OCR/ASR calls; no product changes.','results':all_results},ensure_ascii=False,indent=2),encoding='utf-8')
 print('saved',str(OUT/'report.json'),flush=True)
if __name__=='__main__':main()
