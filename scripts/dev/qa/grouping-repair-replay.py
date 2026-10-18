"""Replay the exact saved OCR/JPG/masks; no provider or new inference calls."""
from pathlib import Path
import sys,json,time,urllib.request,subprocess,argparse,collections
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
from slide_grouping import group_pages
parser=argparse.ArgumentParser();parser.add_argument('--docker',default='D:/mytools/deskdocker/resources/bin/docker.exe');args=parser.parse_args()
OUT=ROOT/'.local/qa/grouping-repair-20261018';OUT.mkdir(exist_ok=True,parents=True)
ids=['abe91625-6846-4756-b209-09dcf1216c5a','0d345651-92fe-4a62-8abf-d7a81195f139','427ff2cd-8534-4f04-bc75-0a275c9e918b']
query="SELECT JSON_OBJECT('id',id,'mode',person_selection_mode,'region',ignored_region_json) FROM transcription_jobs"
cmd='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" --raw -Nse "'+query+'"'
r=subprocess.run([args.docker,'exec','videostudy-mysql-1','sh','-c',cmd],capture_output=True,text=True,check=True);meta={x['id']:x for x in map(json.loads,r.stdout.splitlines())};report=[]
for task in ids:
 snapshot=OUT/f'{task}.json'
 if not snapshot.exists():
  with urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions/'+task,timeout=10) as response:record=json.load(response)['result']
  snapshot.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8')
 record=json.loads(snapshot.read_text(encoding='utf-8'));region=json.loads(meta[task]['region']) if meta[task]['region'] else None
 row={'id':task,'mode':meta[task]['mode'],'region':region,'frames':len(record['visualEvidence']),'saved_groups':len(record['pageGroups']),'cases':{}}
 for mode in ['off','adjacent']:
  before=time.perf_counter();pages,transitions=group_pages(record['visualEvidence'],ROOT/'.local/keyframes'/task,record['segments'],ask_json=lambda _:{'samePage':False},ignore_region=region,person_selection_mode=mode)
  row['cases'][mode]={'seconds':time.perf_counter()-before,'groups':len(pages),'representatives':len(set(t for p in pages for t in p['representativeFrameTimesMs'])),'reasons':dict(collections.Counter(p['decisionReason'] for p in pages))}
  (OUT/f'{task}-{mode}.json').write_text(json.dumps({'pages':pages,'transitions':transitions},ensure_ascii=False,indent=2),encoding='utf-8')
 report.append(row);print(json.dumps(row,ensure_ascii=False),flush=True);(OUT/'baseline-replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False),encoding='utf-8')
