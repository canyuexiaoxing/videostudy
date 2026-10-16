"""Check the restored renderer contract against the actual saved reference reply."""
import argparse,copy,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
from course_outline import normalize_reply
from course_mind_map import finalize_course_reply
p=argparse.ArgumentParser();p.add_argument('--context',type=Path,required=True);a=p.parse_args()
ctx=json.loads(a.context.read_text(encoding='utf-8'));raw=json.loads(ctx['assistantText']);payload=json.loads(ctx['userText'])
code=subprocess.check_output(['git','-c',f'safe.directory={ROOT.as_posix()}','show','f88ddc5:agent-python/course_outline.py'],cwd=ROOT).decode()
baseline={};exec(compile(code,'reference-outline','exec'),baseline)
assert normalize_reply(raw)==baseline['normalize_reply'](raw),'not the known-good outline policy'
snapshot=copy.deepcopy(raw);value=finalize_course_reply(raw,payload,'reference-restore-offline');assert value['status']=='completed';assert raw==snapshot
folder=ROOT/'.local/qa/map-reference-restore';folder.mkdir(parents=True,exist_ok=True)
(folder/'reference-result.json').write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
def count(node):return 1+sum(count(c) for c in node['children'])
summary=dict(matchesKnownGoodPolicy=True,topics=len(value['root']['children']),nodes=count(value['root']),sourcesValidated=True,paidCalls=0)
(folder/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
