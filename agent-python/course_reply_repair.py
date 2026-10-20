"""Collect reply-shape errors without discarding conflicting duplicate branches."""
import json
from collections import Counter
from course_json import CourseJsonFormatError,_ObjectPairs,_unwrap,_same_value,_float,_constant,parse_course_json,_tokens
MAX_ISSUES=128
MAX_VISITS=16384
class ReplyStructureError(CourseJsonFormatError):
 def __init__(self,text,issues):
  self.issues=issues
  super().__init__('json_structure_invalid',text,path=issues[0]['path'] if issues else 'root')
 def __str__(self):
  message='json_structure_invalid ('+'; '.join(i['code']+': '+i['path']+(f" [{i['syntaxReason']}, character {i['position']+1}]" if i.get('syntaxReason') else '') for i in self.issues[:8])+')'
  outcome=getattr(self,'repair_outcome',None)
  if outcome:message+='；已自动修复1次，'+('修复结果未通过原内容保留校验' if outcome=='content' else '修复请求或结果校验仍未通过')
  return message

def _read(text):
 return json.loads(_unwrap(text),object_pairs_hook=_ObjectPairs,parse_float=_float,parse_constant=_constant)
def _recover_tree(text):
 """Read only unambiguous complete containers while ignoring separators.
 No strings, scalar values or container boundaries are invented or removed.
 Used for comparison only; repaired provider output must still parse strictly.
 """
 try:return _read(text)
 except (ValueError,RecursionError):pass
 tokens=_tokens(text)
 if tokens is None or len(tokens)>500000:raise ValueError('reply_unreadable')
 cursor=0
 def value(depth=0):
  nonlocal cursor
  if cursor>=len(tokens) or depth>40:raise ValueError('reply_unreadable')
  token=tokens[cursor];cursor+=1
  if token=='{':
   pairs=_ObjectPairs()
   while cursor<len(tokens) and tokens[cursor]!='}':
    key=tokens[cursor];cursor+=1
    if not isinstance(key,tuple) or key[0]!='string':raise ValueError('reply_unreadable')
    pairs.append((key[1],value(depth+1)))
   if cursor>=len(tokens):raise ValueError('reply_unreadable')
   cursor+=1;return pairs
  if token=='[':
   items=[]
   while cursor<len(tokens) and tokens[cursor]!=']':items.append(value(depth+1))
   if cursor>=len(tokens):raise ValueError('reply_unreadable')
   cursor+=1;return items
  if not isinstance(token,tuple):raise ValueError('reply_unreadable')
  kind,raw=token
  if kind=='string':return raw
  if kind=='number':return _float(raw) if any(c in raw for c in '.eE') else int(raw)
  if kind=='literal':return {'true':True,'false':False,'null':None}[raw]
  raise ValueError('reply_unreadable')
 tree=value();first=tokens[:cursor];documents=1
 if not isinstance(tree,_ObjectPairs):raise ValueError('reply_unreadable')
 while cursor<len(tokens):
  start=cursor;value();documents+=1
  # Only an exactly repeated token sequence can be collapsed; numeric tokens
  # remain literal strings, avoiding float rounding or bool/int equality.
  if documents>8 or tokens[start:cursor]!=first:raise ValueError('reply_ambiguous_documents')
 return tree

def _object(value):return isinstance(value,(dict,_ObjectPairs))
def _entries(value):return list(value.items()) if isinstance(value,dict) else list(value) if isinstance(value,_ObjectPairs) else []
def _variants(value):
 """Ignore identical repeated entries, but retain every conflicting value."""
 result=[]
 for key,item in _entries(value):
  if not any(key==k and _same_value(item,v) for k,v in result):result.append((key,item))
 return result
def _safe(key):
 return key if key in {'topic','children','details','examples','uncertainties','title','sourceIds','imageIds','candidateIds','kind','mergeEvidence','candidateDecisions','reason','target'} else 'field'

def collect_issues(value):
 issues=[];visits=0
 class InspectionStopped(Exception):pass
 def add(code,path):
  issue={'code':code,'path':path}
  if issue not in issues:issues.append(issue)
  if len(issues)>=MAX_ISSUES:raise InspectionStopped('reply_issue_limit',path)
 def walk(node,path,kind,depth=0):
  nonlocal visits
  visits+=1
  if visits>MAX_VISITS or depth>40:raise InspectionStopped('reply_visit_limit',path)
  if not _object(node):add('invalid_type',path);return
  entries=_variants(node);seen=set()
  for key,item in entries:
   if key in seen:add('duplicate_field',path+'.'+_safe(key))
   seen.add(key)
  fields={}
  for key,item in entries:fields.setdefault(key,[]).append(item)
  required=('topic','children','examples') if kind=='root' else ('title',) if kind=='node' else ()
  for key in required:
   if key not in fields:add('missing_field',path+'.'+key)
  for key,items in fields.items():
   p=path+'.'+_safe(key)
   for item in items:
    if key in ('topic','title') and (not isinstance(item,str) or not item.strip()):add('invalid_type',p)
    elif key in ('children','details','examples'):
     if not isinstance(item,list) or isinstance(item,_ObjectPairs):
      add('invalid_type',p)
      if _object(item):walk(item,p,'node',depth+1)
     else:
      for i,child in enumerate(item):walk(child,f'{p}[{i}]','node',depth+1)
    elif key in ('sourceIds','imageIds','candidateIds','uncertainties'):
     if not isinstance(item,list) or isinstance(item,_ObjectPairs) or any(not isinstance(x,str) or not x.strip() for x in item):add('invalid_type',p)
    elif _object(item):walk(item,p,'aux',depth+1)
    elif isinstance(item,list):
     for i,child in enumerate(item):
      if _object(child):walk(child,f'{p}[{i}]','aux',depth+1)
 try:walk(value,'root','root')
 except InspectionStopped as stopped:issues.append({'code':'inspection_incomplete','path':stopped.args[1],'inspectionReason':stopped.args[0]})
 return issues

def parse_map_reply(text,*,task=None):
 try:value=parse_course_json(text,task=task)
 except CourseJsonFormatError as error:
  if error.code=='json_nonfinite':raise
  # Never make a second successful parse a prerequisite for entering repair.
  code='duplicate_field' if error.code=='json_duplicate_key' else 'parse_error'
  issues=[{'code':code,'path':error.path or 'root','parserCode':error.code,
           'line':error.lineno,'column':error.colno,'position':error.pos}]
  if error.syntax_reason:issues[0]['syntaxReason']=error.syntax_reason
  try:
   recovered=_recover_tree(text)
   for issue in collect_issues(recovered):
    if not any(i['code']==issue['code'] and i['path']==issue['path'] for i in issues):issues.append(issue)
  except (ValueError,RecursionError) as inspection_error:
   reason=str(inspection_error) if str(inspection_error) in ('reply_unreadable','reply_ambiguous_documents') else 'reply_inspection_failed'
   issues.append({'code':'inspection_incomplete','path':'root','inspectionReason':reason})
  raise ReplyStructureError(text,issues) from None
 issues=collect_issues(value)
 if issues:raise ReplyStructureError(text,issues)
 return value

def structure_error(value):
 issues=collect_issues(value)
 return ReplyStructureError(json.dumps(value,ensure_ascii=False),issues) if issues else None

def preserves_reply(before,after):
 """Accept format changes only; bind content to its original node and branch."""
 try:
  original=_recover_tree(before)
  def metadata(node,root=False):
   result=Counter()
   def leaves(value,trail=(),depth=0):
    if depth>40:raise ValueError('reply_inspection_limit')
    if _object(value):
     for key,item in _variants(value):leaves(item,trail+(key,),depth+1)
    elif isinstance(value,list):
     for index,item in enumerate(value):leaves(item,trail+(index,),depth+1)
    elif value is not None and value!='':result[(trail,type(value).__name__,str(value))]+=1
   for key,item in _variants(node):
    if key not in ('children','details','examples','topic' if root else 'title'):
     if key in ('sourceIds','imageIds','candidateIds') and isinstance(item,list) and not isinstance(item,_ObjectPairs):
      for entry in item:leaves(entry,(key,))
     else:leaves(item,(key,))
   return result
  def heading(node,root=False):
   key='topic' if root else 'title'
   values=[v for k,v in _variants(node) if k==key and v is not None and v!='']
   if len(values)>1:raise ValueError('ambiguous_heading')
   if not values:return None
   value=values[0]
   if isinstance(value,str):return value if value.strip() else None
   # Preserve an existing scalar even when its JSON type was invalid.
   if type(value) in (int,float,bool) or hasattr(value,'token'):
    return value.token if hasattr(value,'token') else json.dumps(value)
   raise ValueError('unverifiable_heading')
  def slots(value):
   result=[]
   def walk(node,path=('root',),depth=0):
    if depth>40 or len(result)>MAX_VISITS:raise ValueError('reply_inspection_limit')
    if isinstance(node,str) and node:node={'title':node}
    if not _object(node):raise ValueError('unrecoverable_node')
    if path!=('root',):result.append((path,heading(node),metadata(node)))
    entries=_variants(node)
    for field in ('children','details','examples'):
     index=0
     for key,item in entries:
      if key!=field:continue
      values=item if isinstance(item,list) and not isinstance(item,_ObjectPairs) else ([] if item is None else [item])
      for child in values:
       # Empty malformed containers have no course content to preserve.
       if _object(child) and not child:continue
       walk(child,path+((field,index),),depth+1);index+=1
   walk(value);return result
  old_topic=heading(original,True)
  if old_topic is not None and heading(after,True)!=old_topic:return False
  if metadata(original,True)!=metadata(after,True):return False
  old,new=slots(original),slots(after)
  if len(old)!=len(new):return False
  for (path,title,own),(target,new_title,meta) in zip(old,new):
   if path!=target or own!=meta or (title is not None and title!=new_title):return False
  return True
 except (ValueError,TypeError,RecursionError):return False
