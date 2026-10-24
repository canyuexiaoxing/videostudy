"""Opt-in experiment: full-course context, frozen plan, independent short outputs.
Nothing imports this module from the production analysis path.
"""
from copy import deepcopy
import json,re
PLAN_INSTRUCTION = '''EXPERIMENT: paginate OUTPUT ONLY. All original course evidence, images, coverage, hierarchy, formula and example rules remain in effect. Do not partition, summarize or omit the INPUT. For this turn ONLY, replace the final-output serialization contract with a flat whole-course plan. Read the ENTIRE course before planning. Return exactly one JSON object {"topic":"course title","nodes":[{"id":"n1","parentId":null,"title":"knowledge heading","kind":"category"},{"id":"n2","parentId":"n1","title":"independent formula or method","kind":"formula"}],"examples":[{"id":"e1","title":"separate actual worked question"}],"uncertainties":[]}. Include ALL supported knowledge headings and ALL independent formulas/methods and distinct examples, not just a high-level outline. Use stable unique n1,n2,... and e1,e2,... IDs; parentId null means root, otherwise an earlier node ID. Keep original teaching hierarchy and order; no arbitrary node count quota. This is a frozen assembly manifest: later turns fill existing records, never move/delete/merge them. Reserve condition/step/symbol/pitfall/explanation details for the fill phase. Do not output details, derivations, citations or a nested children tree yet. Do not copy instructional placeholder headings into the real plan.'''
BATCH_RULES = '''Fill ONLY the requested frozen-plan IDs using ALL original course evidence still present in this conversation. This is output pagination, never a new course analysis or input-material partition. Return exactly one independent JSON object {"batchId":"requested ID","items":[{"id":"existing plan ID","sourceIds":[],"imageIds":[],"details":[{"title":"full condition/formula/step/explanation","kind":"condition","sourceIds":[],"imageIds":[]}]}],"uncertainties":[]}. Each requested ID occurs exactly once in the requested order; no other IDs. Do NOT repeat title, kind, parentId, children or examples fields: the frozen plan already owns those. Use exact supplied transcript IDs and image handles. Candidate IDs must not be invented. For knowledge entries retain all conditions, formulas, symbol explanations, worked method steps, pitfalls and corrections, citing the actual evidence for each detail. Independent formulas already have their own planned node; do not hide extra knowledge branches in details. For example entries cite the real question and its solution evidence; never merge different questions with similar formulas. Do not abbreviate or summarize to fill a size quota. End this complete JSON object before stopping, never emit a piece of a larger unfinished JSON string.'''
_ID=re.compile(r'^[ne][1-9][0-9]{0,4}$')
def validate_plan(plan):
 if not isinstance(plan,dict) or not isinstance(plan.get('topic'),str) or not plan['topic'].strip():raise ValueError('invalid_batch_plan')
 if set(plan)-{'topic','nodes','examples','uncertainties'}:raise ValueError('unexpected_plan_fields')
 if not isinstance(plan.get('nodes'),list) or not isinstance(plan.get('examples'),list) or not plan['nodes']:raise ValueError('empty_batch_plan')
 if len(plan['nodes'])+len(plan['examples'])>4096:raise ValueError('batch_plan_too_large')
 seen={};depths={}
 for kind,key in [('n','nodes'),('e','examples')]:
  for node in plan[key]:
   if not isinstance(node,dict) or not isinstance(node.get('id'),str) or not _ID.fullmatch(node['id']) or not node['id'].startswith(kind) or node['id'] in seen:raise ValueError('invalid_or_duplicate_plan_id')
   if not isinstance(node.get('title'),str) or not node['title'].strip():raise ValueError('empty_plan_title')
   allowed={'id','title','parentId','kind'} if kind=='n' else {'id','title'}
   if set(node)-allowed:raise ValueError('unexpected_plan_node_fields')
   if kind=='n':
    if 'parentId' not in node or node['parentId'] is not None and node['parentId'] not in seen:raise ValueError('invalid_plan_parent')
    if node.get('kind') not in {'formula','method','rule','concept','category','classification'}:raise ValueError('invalid_plan_kind')
    depths[node['id']]=1 if node['parentId'] is None else depths[node['parentId']]+1
    if depths[node['id']]>12:raise ValueError('plan_depth_exceeded')
   seen[node['id']]=node
 _strings(plan.get('uncertainties',[]))
 return plan

def _strings(value):
 if not isinstance(value,list) or any(not isinstance(x,str) or not x.strip() for x in value):raise ValueError('invalid_batch_string_list')
 return value

def assemble_batches(plan,batches,*,allowed_sources=None,allowed_images=None):
 validate_plan(plan);expected={n['id']:n for n in plan['nodes']+plan['examples']};filled={};uncertainties=list(plan.get('uncertainties',[]));batch_ids=set()
 for batch in batches:
  if not isinstance(batch,dict) or set(batch)-{'batchId','items','uncertainties'} or not isinstance(batch.get('batchId'),str) or batch['batchId'] in batch_ids or not isinstance(batch.get('items'),list):raise ValueError('invalid_batch_envelope')
  batch_ids.add(batch['batchId']);uncertainties+=_strings(batch.get('uncertainties',[]))
  for item in batch['items']:
   if not isinstance(item,dict) or item.get('id') not in expected or item['id'] in filled:raise ValueError('unknown_or_duplicate_batch_node')
   if set(item)-{'id','sourceIds','imageIds','details'}:raise ValueError('batch_changed_frozen_fields')
   for field,allowed in [('sourceIds',allowed_sources),('imageIds',allowed_images)]:
    refs=_strings(item.get(field,[]))
    if allowed is not None and any(ref not in allowed for ref in refs):raise ValueError('unknown_batch_reference')
   if not isinstance(item.get('details',[]),list):raise ValueError('invalid_batch_details')
   for detail in item.get('details',[]):
    if not isinstance(detail,dict) or not isinstance(detail.get('title'),str) or not detail['title'].strip() or set(detail)-{'title','kind','sourceIds','imageIds'}:raise ValueError('invalid_batch_detail')
    if detail.get('kind') not in {None,'condition','step','symbol','pitfall','explanation'}:raise ValueError('independent_knowledge_hidden_in_detail')
    for field,allowed in [('sourceIds',allowed_sources),('imageIds',allowed_images)]:
     refs=_strings(detail.get(field,[]))
     if allowed is not None and any(ref not in allowed for ref in refs):raise ValueError('unknown_batch_detail_reference')
    if not detail.get('sourceIds') and not detail.get('imageIds'):raise ValueError('unsupported_batch_detail')
   filled[item['id']]=deepcopy(item)
 if set(filled)!=set(expected):raise ValueError('incomplete_batch_coverage')
 output={n['id']:{'title':n['title'],'kind':n['kind'],'candidateIds':[],'sourceIds':filled[n['id']].get('sourceIds',[]),'imageIds':filled[n['id']].get('imageIds',[]),'details':filled[n['id']].get('details',[]),'children':[]} for n in plan['nodes']}
 roots=[]
 for n in plan['nodes']:
  node=output[n['id']]
  if n['parentId'] is None:roots.append(node)
  else:output[n['parentId']]['children'].append(node)
  if not node['children'] and not any(k['parentId']==n['id'] for k in plan['nodes']) and not node['sourceIds'] and not node['imageIds'] and not any(d.get('sourceIds') or d.get('imageIds') for d in node['details']):raise ValueError('unsupported_batch_leaf')
 examples=[]
 for n in plan['examples']:
  item=filled[n['id']]
  if not item.get('sourceIds') and not item.get('imageIds'):raise ValueError('unsupported_batch_example')
  examples.append({'title':n['title'],'candidateIds':[],'sourceIds':item.get('sourceIds',[]),'imageIds':item.get('imageIds',[]),'details':item.get('details',[])})
 return {'topic':plan['topic'],'children':roots,'examples':examples,'uncertainties':list(dict.fromkeys(uncertainties))}

def run_batched(base_body,send_json,*,batch_size=6,allowed_sources=None,allowed_images=None,max_batches=24):
 if type(batch_size) is not int or not 1<=batch_size<=12:raise ValueError('invalid_batch_size')
 body=deepcopy(base_body);messages=deepcopy(body['messages']);messages.append({'role':'user','content':PLAN_INSTRUCTION})
 body['messages']=deepcopy(messages);body['max_tokens']=16384
 plan=validate_plan(send_json(body,'plan',0));messages.append({'role':'assistant','content':json.dumps(plan,ensure_ascii=False)})
 ids=[n['id'] for n in plan['nodes']+plan['examples']];groups=[ids[i:i+batch_size] for i in range(0,len(ids),batch_size)]
 if len(groups)>max_batches:raise ValueError('batch_call_budget_exceeded')
 batches=[]
 for index,group in enumerate(groups,1):
  request={'task':BATCH_RULES,'batchId':'b'+str(index),'requestedIds':group,'remainingAfterThisBatch':len(ids)-min(index*batch_size,len(ids))}
  messages.append({'role':'user','content':json.dumps(request,ensure_ascii=False)});body['messages']=deepcopy(messages);body['max_tokens']=12288
  batch=send_json(body,'batch',index)
  if not isinstance(batch,dict) or batch.get('batchId')!='b'+str(index) or not isinstance(batch.get('items'),list) or [x.get('id') for x in batch['items'] if isinstance(x,dict)]!=group:raise ValueError('wrong_batch_or_missing_ids')
  batches.append(batch);messages.append({'role':'assistant','content':json.dumps(batch,ensure_ascii=False)})
 raw=assemble_batches(plan,batches,allowed_sources=allowed_sources,allowed_images=allowed_images)
 return raw,{'batches':len(groups),'knowledgeNodes':len(plan['nodes']),'examples':len(plan['examples']),'requestsWithoutRepairs':len(groups)+1,'allPlanIdsFilled':True,'hierarchyFrozen':True}
