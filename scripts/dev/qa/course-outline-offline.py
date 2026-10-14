"""Inspect real saved evidence without model calls or history writes."""
from pathlib import Path
import sys,json,urllib.request
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'agent-python'))
from course_outline import normalize_reply,outline_hints,audit_outline
course_id='58e10c5e-266f-4e11-a17e-e81eb077c3aa'
record=json.load(urllib.request.urlopen('http://127.0.0.1:18080/api/transcriptions/'+course_id))
folder=ROOT/'.local/keyframes'/course_id
snapshot=next((folder/'.map-context').glob('*.json'))
context=json.loads(snapshot.read_text(encoding='utf-8'))
raw=json.loads(context['assistantText'])
normalized=normalize_reply(raw)
reps={ms for page in record['result']['pageGroups'] for ms in page.get('representativeFrameTimesMs',[])}
visuals=[v for v in record['result']['visualEvidence'] if v['frameTimeMs'] in reps]
hints=outline_hints(visuals,folder,{})
issues=audit_outline(normalized,hints)
assert len(raw['children'])==3
assert len(normalized['children'][0]['children'])==3
assert any('增长量计算' in item for item in issues)
output={'savedTopics':len(raw['children']),'recoveredIndependentFormulaEntries':len(normalized['children'][0]['children']),'missingClassificationDetected':True,'paidModelCalls':0,'historyWrites':0}
print(json.dumps(output,ensure_ascii=False))
