"""Replay a saved provider reply locally; never call a model or alter history."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'agent-python'))
from course_outline import normalize_reply
p=argparse.ArgumentParser();p.add_argument('--context',type=Path,required=True);a=p.parse_args()
ctx=json.loads(a.context.read_text(encoding='utf-8'));raw=json.loads(ctx['assistantText'])
def nodes(value):
 out=[]
 def visit(n):
  out.append(n)
  for c in n.get('children',[]):visit(c)
 for c in value.get('children',[]):visit(c)
 return out
def refs(value):
 found=set()
 def visit(v):
  if isinstance(v,dict):
   for field in ('sourceIds','imageIds'):
    for sid in v.get(field,[]):found.add((field,sid))
   for v2 in v.values():visit(v2)
  elif isinstance(v,list):
   for v2 in v:visit(v2)
 visit(value);return found
value=normalize_reply(raw)
assert refs(value)==refs(raw),'source identities changed'
assert value.get('examples')==raw.get('examples'),'example identities changed'
assert normalize_reply(value)==value,'not idempotent'
result=dict(rawNodes=len(nodes(raw)),normalizedNodes=len(nodes(value)),maxTitleBefore=max(len(n['title']) for n in nodes(raw)),maxTitleAfter=max(len(n['title']) for n in nodes(value)),allReferencesPreserved=True,examplesPreserved=True,idempotent=True,paidModelCalls=0)
folder=ROOT/'.local/qa/map-outline-quality';folder.mkdir(parents=True,exist_ok=True)
(folder/'offline-summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
