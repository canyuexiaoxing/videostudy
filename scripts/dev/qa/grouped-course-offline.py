"""Read existing course evidence; all AI replies are injected simulations."""
from pathlib import Path
import json,sys,copy,tempfile,shutil
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'agent-python'))
from group_scheduler import ReadyGroupScheduler
from group_understanding import analyze_group
from course_mind_map import build_course_mind_map
identity='df93f2d9-d1f4-4e6c-b6f4-f2716c8bb0dd'
url=f'http://127.0.0.1:18080/api/transcriptions/{identity}'
with urlopen(url) as r:original=json.load(r)
course=original['result'];pages=copy.deepcopy(course['pageGroups'][:6]);speech=course['segments'];visuals=course['visualEvidence'];calls=[]
for i,p in enumerate(pages):
 if i+1<len(pages):p['_closedAtMs']=pages[i+1]['firstFrameTimeMs']
def group_provider(payload,images):
 current=payload['current'];ms=current['images'][0]['frameTimeMs'];calls.append((payload['phase'],current['pageIndex'],len(images)))
 # Intentional partial response verifies that actual original images reach final.
 partial=current['pageIndex']==pages[-1]['pageIndex']
 return {'status':'partial' if partial else 'completed','knowledgeCandidates':[{'title':'模拟：整课共同方法','kind':'method','sourceIds':[], 'imageIds':[f'frame_{ms}'],'details':[{'title':'模拟条件详情','sourceIds':[], 'imageIds':[f'frame_{ms}']}]}], 'exampleCandidates':[], 'connections':{}, 'uncertainties':['模拟未看清：交整课核对'] if partial else []}
def understand(*args,**kw):return analyze_group(*args,ask_json=group_provider,**kw)
final_requests=[]
def final_provider(payload,images):
 final_requests.append((payload,images));assert images,'partial original must be sent'
 concepts=payload['concepts'];ids=[c['id'] for c in concepts];imageids=list(dict.fromkeys(i for c in concepts for i in c['imageIds']))
 return {'topic':'离线模拟整课汇总','children':[{'title':'模拟：一个完整方法','candidateIds':ids,'sourceIds':[], 'imageIds':imageids,'children':[], 'details':[{'title':'模拟：条件保留在详情','sourceIds':[], 'imageIds':[imageids[0]]}]}], 'examples':[], 'uncertainties':['离线模拟输出，不用于证明实际提炼准确率']}
with tempfile.TemporaryDirectory(dir=ROOT/'.local/qa',prefix='grouped-course-') as d:
 root=Path(d)
 for frame in visuals:
  src=ROOT/'.local/keyframes'/identity/f"{frame['frameTimeMs']}.jpg"
  if src.is_file():shutil.copyfile(src,root/src.name)
 with ReadyGroupScheduler(root,understand) as scheduler:
  scheduler.update(pages[:3],speech,visuals,speech_complete=True);assert not scheduler.started
  scheduler.update(pages[:4],speech,visuals,speech_complete=True);scheduler.drain();assert scheduler.started
  results=scheduler.finish(pages,speech,visuals)
 mind=build_course_mind_map(speech,results,visuals,root,ask_json=final_provider)
 assert len(mind['root']['children'])==1 and mind['root']['children'][0]['details']
 known={f['frameTimeMs'] for f in visuals}
 for ref in mind['root']['children'][0]['evidenceRefs']:
  assert ref['startMs'] in known and ref['sourceId']==f"frame_{ref['startMs']}" and ref['startMs']==ref['endMs']
 mocked=copy.deepcopy(original);mocked['result']['mindMap']=mind;mocked['result']['pageGroups']=results
 (ROOT/'.local/qa/grouped-course-mock.json').write_text(json.dumps(mocked,ensure_ascii=False),encoding='utf-8')
with urlopen(url) as r:assert json.load(r)==original,'Stored history must remain unchanged'
print(json.dumps({'actualGroups':len(pages),'actualSpeechSegments':len(speech),'simulatedGroupRequests':len(calls),'finalRequests':len(final_requests),'forwardedOriginalImages':len(final_requests[0][1]),'finalConcepts':len(mind['root']['children']),'storedHistoryUnchanged':True,'paidModelCalls':0},ensure_ascii=False))
