"""Offline history replay against real saved questions; never requests a provider."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json,subprocess,os
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
from map_conversation import load_map_conversation
from practice_history import _question
from practice import generate_practice,validate_question
from model_diagnostics import close_logs
TASK='cbacd60e-c271-48b2-9353-2bc88d7c2aec'
OUT=ROOT/'.local/qa'/('practice-history-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));OUT.mkdir(parents=True);os.environ['MODEL_LOG_DIR']=str(OUT/'logs')
query="SELECT JSON_OBJECT('id',id,'source',CAST(source_json AS JSON),'result',CAST(result_json AS JSON)) FROM practice_sets WHERE transcription_id='"+TASK+"' AND status='completed' ORDER BY created_at ASC"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql --default-character-set=utf8mb4 -u"$MYSQL_USER" "$MYSQL_DATABASE" -N -B --raw -e "'+query+'"'
rows=[json.loads(line) for line in subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',command]).decode('utf-8').splitlines()];assert rows
source=rows[-1]['source'];history=[{'id':r['id'],'request':{k:r['source'].get(k) for k in ('scopeTitle','count','difficulty','mode')},'questions':r['result']['questions']} for r in rows]
context=load_map_conversation(ROOT/'.local/keyframes'/TASK,source['mindMap']);context['_diagnosticTaskId']=TASK
old=[_question(q) for row in history for q in row['questions']]
for q in old:validate_question(q,source['nodes'])
requests=[]
result=generate_practice(source['nodes'],[],10,source['difficulty'],lambda p:requests.append(p) or {'questions':old},mode=source['mode'],context=context,history=history)
assert result['questions']==[] and result['rejectedCount']==len(old)
assert sum(m['role']=='assistant' for m in requests[0]['_messages'])>=2
log=(OUT/'logs/model-events.jsonl').read_text(encoding='utf-8')
assert all(row['event']!='request_started' for row in map(json.loads,log.splitlines()))
assert 'data:image/' not in log
report={'historyRounds':result['historyRounds'],'historyQuestions':result['historyQuestions'],'reconstructedQuestionsValid':len(old),'exactRepeatedQuestionsRejected':result['rejectedCount'],'historySummarized':result['historySummarized'],'paidModelCalls':0,'formalRecordsWritten':0}
close_logs();(OUT/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'output':str(OUT),**report}))
