"""Read-only reconstruction of complete effective processing time, excluding failed map runs."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,sqlite3,os,hashlib
ROOT=Path(__file__).resolve().parents[3]
archive=json.loads((ROOT/'.local/qa/recording-evidence-2026-10-21/summary.json').read_text(encoding='utf8'))
data=Path(os.environ['APPDATA'])/'Framewise/data'
con=sqlite3.connect((data/'database/framewise.db').as_uri()+'?mode=ro',uri=True)
records=[]
for old in archive['records']:
 row=con.execute('select result_json from transcription_jobs where id=?',(old['id'],)).fetchone()
 assert row is not None
 result=json.loads(row[0]);timings=result['stageTimingsMs']
 fingerprint=hashlib.sha256(json.dumps(result['mindMap'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 retry=old['timeScope']=='successful_map_request_to_validation_only'
 if retry:assert fingerprint==old['mapSnapshotSha256'],'historical_map_changed'
 else:assert result['stageTimingsMs']['total']==round(old['selectedElapsedSeconds']*1000),'historical_pipeline_timing_changed'
 total=timings['total'];map_stage=timings['mindMap'];pre=total-map_stage
 assert pre>=0
 success=round(old['selectedElapsedSeconds']*1000) if retry else map_stage
 elapsed=pre+success
 records.append(dict(id=old['id'],filename=old['filename'],historyCreatedLocal=old['historyCreatedLocal'],videoDurationSeconds=old['videoDurationSeconds'],originalPipelineTotalMs=total,originalMapStageMs=map_stage,preprocessingCriticalPathMs=pre,successfulMapMs=success,effectiveTotalMs=elapsed,effectiveTotalSeconds=elapsed/1000,reconstructed=retry,excludedFailedInitialMapStageMs=map_stage if retry else 0,successfulRequestId=old['successfulRequestId'],mapSnapshotSha256=old['mapSnapshotSha256'],currentSavedMapMatchesArchive=fingerprint==old['mapSnapshotSha256'],formula=f'{total} - {map_stage} + {success}' if retry else str(total),scope='original preprocessing critical path plus final successful map request through validation; excludes all failed map runs and retry waiting' if retry else 'observed pipeline start through successful map completion; successful automatic repair retained'))
con.close()
report=dict(recordedAtLocal=datetime.now(timezone(timedelta(hours=8))).isoformat(),databaseReadOnly=True,newModelCalls=0,records=records,notes=['Reconstructed totals are not an observed single uninterrupted successful run.','Use total minus mindMap for preprocessing because speech and visual work overlap.','Retry preparation lacks an independent timer and is not inferred; reconstructed successful-map interval starts at request_started.','Failed earlier runs and human retry waiting are excluded, while originals remain archived.'])
for path in [ROOT/'.local/qa/recording-evidence-2026-10-21/effective-timings-2026-10-25.json',ROOT/'docs/aic-review-2026-10-25/course-effective-timings.json']:
 path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for row in records:print(json.dumps({k:row[k] for k in ['id','effectiveTotalSeconds','reconstructed','formula']},ensure_ascii=False))
