"""Read real course evidence, inject one response, never write course history."""
from pathlib import Path
import json,sys,copy
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'agent-python'))
from direct_course_map import build_direct_course_map
identity='df93f2d9-d1f4-4e6c-b6f4-f2716c8bb0dd'
url=f'http://127.0.0.1:18080/api/transcriptions/{identity}'
with urlopen(url) as response: original=json.load(response)
course=original['result'];calls=[]
expected=sorted({ms for p in course['pageGroups'] for ms in p['representativeFrameTimesMs']})
def provider(payload,images):
 calls.append(len(images));assert [ms for ms,_,_ in images]==expected
 assert all(path.is_file() for _,path,_ in images)
 return dict(topic='整课图文离线模拟',children=[dict(title='模拟核心方法',sourceIds=[],imageIds=[f'frame_{expected[0]}'],candidateIds=[],children=[],details=[])],examples=[],uncertainties=['离线模拟，仅用于验证传输和来源链路'])
result=build_direct_course_map(course['segments'],course['pageGroups'],course['visualEvidence'],ROOT/'.local/keyframes'/identity,ask_json=provider)
assert result['status']=='completed',result
assert calls==[len(expected)]
mock=copy.deepcopy(original);mock['result']['mindMap']=result
(ROOT/'.local/qa/direct-course-mock.json').write_text(json.dumps(mock,ensure_ascii=False),encoding='utf-8')
with urlopen(url) as response:assert json.load(response)==original
print(json.dumps(dict(representatives=len(expected),speechSegments=len(course['segments']),requests=len(calls),historyUnchanged=True,paidModelCalls=0)))
