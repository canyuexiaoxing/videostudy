"""Lossless JSON-envelope recovery and format-only repair verification."""
import json,math,re
from model_diagnostics import record_event

class CourseJsonFormatError(json.JSONDecodeError):
 def __init__(self,code,doc,pos=0,*,path=None):
  self.code=code
  self.path=path
  super().__init__(code,doc,pos)
 def __str__(self):
  if self.code=='json_duplicate_key' and self.path:
   return f'json_duplicate_key（重复字段的值冲突：{self.path}；为避免丢失内容未自动覆盖）'
  return super().__str__()

class _PolicyError(ValueError):pass

class _ObjectPairs(list):
 """Keep object entries until location-aware duplicate validation."""

class _JsonFloat(float):
 def __new__(cls,token):
  value=super().__new__(cls,token);value.token=token;return value

def _plain_numbers(value):
 if isinstance(value,_JsonFloat):return float(value)
 if isinstance(value,dict):return {key:_plain_numbers(item) for key,item in value.items()}
 if isinstance(value,list):return [_plain_numbers(item) for item in value]
 return value

_PATH_FIELDS={'topic','children','details','examples','uncertainties','title','sourceIds','imageIds','mergeEvidence','candidateDecisions','reason','startMs','endMs','id','type','quote'}

def _same_value(a,b):
 # Python equality alone treats true == 1 == 1.0, and ignores object order.
 if type(a) is not type(b):return False
 if isinstance(a,_JsonFloat):return a.token==b.token
 if isinstance(a,dict):return list(a)==list(b) and all(_same_value(a[k],b[k]) for k in a)
 if isinstance(a,list):return len(a)==len(b) and all(_same_value(x,y) for x,y in zip(a,b))
 return a==b

def _materialize(value,path,stats,text):
 if isinstance(value,_ObjectPairs):
  result={}
  for key,item in value:
   location=path+'.'+(key if key in _PATH_FIELDS else 'field')
   item=_materialize(item,location,stats,text)
   if key in result:
    if not _same_value(result[key],item):raise CourseJsonFormatError('json_duplicate_key',text,path=location)
    stats[0]+=1
   else:result[key]=item
  return result
 if isinstance(value,list):return [_materialize(item,f'{path}[{i}]',stats,text) for i,item in enumerate(value)]
 if isinstance(value,_JsonFloat):stats[1]=True
 return value

def _float(value):
 result=_JsonFloat(value)
 if not math.isfinite(result):raise _PolicyError('json_nonfinite')
 return result

def _constant(value):raise _PolicyError('json_nonfinite')

def _unwrap(text):
 value=text.lstrip('\ufeff').strip()
 for prefix in ('以下是JSON结果：','以下是 JSON 结果：','以下是JSON：','JSON结果：','Here is the JSON:','Here is the requested JSON:'):
  if value.startswith(prefix):value=value[len(prefix):].lstrip();break
 for suffix in ('以上为JSON结果。','以上是完整JSON。'):
  if value.endswith('\n'+suffix):value=value[:-len(suffix)].rstrip();break
 opened=re.match(r'```(?:json)?[ \t]*\r?\n',value,re.I)
 if opened:value=value[opened.end():]
 if value.rstrip().endswith('```'):value=value.rstrip()[:-3].rstrip()
 return value

def parse_course_json(text,*,task=None):
 if not isinstance(text,str):raise ValueError('course_reply_not_text')
 source=_unwrap(text);offset=max(0,text.find(source));decoder=json.JSONDecoder(object_pairs_hook=_ObjectPairs,parse_float=_float,parse_constant=_constant)
 cursor=0;count=0;first=None;duplicates=[0,False]
 try:
  while cursor<len(source):
   while cursor<len(source) and source[cursor].isspace():cursor+=1
   if cursor==len(source):break
   if source[cursor]!='{':raise CourseJsonFormatError('json_trailing_content' if count else 'json_root_invalid',text,cursor+offset)
   try:value,end=decoder.raw_decode(source,cursor)
   except json.JSONDecodeError as error:
    raise CourseJsonFormatError('json_multiple_fragments' if count else 'json_invalid_syntax',text,error.pos+offset) from None
   value=_materialize(value,'root',duplicates,text)
   if count and not _same_value(first,value):raise CourseJsonFormatError('json_ambiguous_documents',text,cursor+offset)
   if not count:first=value
   count+=1;cursor=end
   if count>8:raise CourseJsonFormatError('json_many_documents',text,cursor+offset)
  if not count:raise CourseJsonFormatError('json_empty',text,0)
 except _PolicyError as error:
  record_event('stage_failed',task,operation='course_map',stage='json_recovery',reason=str(error))
  raise CourseJsonFormatError(str(error),text,0) from None
 except CourseJsonFormatError as error:
  record_event('stage_failed',task,operation='course_map',stage='json_recovery',reason=error.code,json_position=error.pos,json_path=error.path)
  raise
 if duplicates[0]:
  record_event('stage_completed',task,operation='course_map',stage='json_recovery',status='completed',reason='json_identical_key',duplicate_key_count=duplicates[0])
 if source!=text.strip() or count>1:
  record_event('stage_completed',task,operation='course_map',stage='json_recovery',status='completed',reason='json_identical_repeat' if count>1 else 'json_wrapper_removed',json_document_count=count)
 return _plain_numbers(first) if duplicates[1] else first

_number=re.compile(r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?')

def _tokens(text):
 """Retain strings/scalars and ALL container delimiters; ignore only separators."""
 text=_unwrap(text);tokens=[];stack=[];i=0
 while i<len(text):
  c=text[i]
  if c.isspace() or c in ',:':i+=1;continue
  if c=='"':
   try:value,end=json.decoder.scanstring(text,i+1,True)
   except (ValueError,json.JSONDecodeError):return None
   tokens.append(('string',value));i=end;continue
  if c in '{[':stack.append(c);tokens.append(c);i+=1;continue
  if c in '}]':
   if not stack or stack.pop()!=('{' if c=='}' else '['):return None
   tokens.append(c);i+=1;continue
  match=_number.match(text,i)
  if match:tokens.append(('number',match.group()));i=match.end();continue
  literal=next((s for s in ('true','false','null') if text.startswith(s,i)),None)
  if literal:tokens.append(('literal',literal));i+=len(literal);continue
  return None
 return tokens if tokens and not stack else None

def can_repair_format(error):
 return isinstance(error,CourseJsonFormatError) and error.code=='json_invalid_syntax' and _tokens(error.doc) is not None

def same_format_content(before,after):
 first=_tokens(before);return first is not None and first==_tokens(after)
