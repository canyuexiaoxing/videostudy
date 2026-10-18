import sys,json,importlib.util,time
from pathlib import Path
R=Path('E:/workp/videostudy');O=R/'.local/qa/yolo-grouping-fix-20261018';sys.path.insert(0,str(R/'agent-python'))
import slide_grouping as g
spec=importlib.util.spec_from_file_location('baseline',O/'baseline_slide_grouping.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
meta=json.loads((R/'.local/qa/grouping-multi-20261017/metadata.json').read_text());report=[]
for ID in ['d517b4f7-58d3-483d-bd9f-a0966341461b','56ac6493-3085-45e2-b9c4-130b583b95d1','cbacd60e-c271-48b2-9353-2bc88d7c2aec','427ff2cd-8534-4f04-bc75-0a275c9e918b']:
 data=json.loads((R/'.local/qa/grouping-multi-20261017'/f'{ID}.json').read_text());region=json.loads(meta[ID]['region']) if meta[ID]['region'] else None
 kwargs=dict(ask_json=lambda _:{'samePage':False},ignore_region=region);frames=data['visualEvidence'];folder=R/'.local/keyframes'/ID
 old=b.group_pages(frames,folder,[],**kwargs);new=g.group_pages(frames,folder,[],person_selection_mode='off',**kwargs);assert old==new,ID
 report.append({'course':ID,'frames':len(frames),'groups':len(new[0]),'exact_off_match':True});print(report[-1],flush=True)
(O/'off-regression.json').write_text(json.dumps(report,indent=2))
