"""Format-only practice recovery. Semantic question/diagram validation stays in practice.py."""
import json,re,time,math
from model_diagnostics import record_event
MAX_REPLY=2_000_000
FIELDS=('nodeId','sourceIds','kind','task','title','prompt','options','answerIndex','explanation','distractorReasons','takeaway')
TEXT_FIELDS={'title','prompt','explanation','takeaway','label','unit'}
# JSON's b/f/n/r/t/u escapes overlap with these common LaTeX commands. Unknown overlaps remain ambiguous.
ESCAPE_COMMANDS=set('bar barwedge backslash beta beth big bigl bigm bigr bigg biggl biggm biggr binom boldsymbol bot bowtie boxed breve bullet begin bmod frac fbox flat forall footnotesize ne neq neg nabla natural ncong ni not notin nparallel nsubseteq nsupseteq nu newcommand newline rangle rbrace rceil Re ref renewcommand rfloor rho right rightarrow rightharpoondown rightharpoonup rightleftharpoons rightleftarrows rm roman rule relax raisebox tan tanh tau tbinom text textbf textcolor textit textnormal textrm textsf textstyle texttt tfrac therefore theta thickspace thinspace tilde times tiny to top triangle triangleleft triangleright'.split())
class PracticeReplyError(json.JSONDecodeError):
 def __init__(self,source,issues,position=0,*,normalized=None):
  self.issues=issues;self.source=source if normalized is None else normalized;self.code="practice_provider_invalid_json"
  super().__init__('practice_provider_invalid_json',source,position)
 def __str__(self):return 'practice_provider_invalid_json'

def _unwrap(source):
 source=source.strip().lstrip('\ufeff')
 if re.fullmatch(r'```(?:json)?\s*\n[\s\S]*\n```',source,re.I):source=re.sub(r'^```(?:json)?\s*\n|\n```$','',source,flags=re.I)
 return source

def normalize_latex(source):
 """Only single escapes inside explicit math delimiters; never rewrite valid escapes globally."""
 out=[];i=0;inside=False;closing=None
 while i<len(source):
  c=source[i]
  if not inside:
   out.append(c);inside=c=='"';closing=None;i+=1;continue
  if c=='"':inside=False;out.append(c);i+=1;continue
  if c=='$':
   marker='$$' if source.startswith('$$',i) else '$'
   if closing==marker:closing=None
   elif closing is None and source.find(marker,i+len(marker))>=0:closing=marker
   out.append(marker);i+=len(marker);continue
  if c!='\\':out.append(c);i+=1;continue
  end=i
  while end<len(source) and source[end]=='\\':end+=1
  n=end-i;next_char=source[end:end+1]
  if n in (1,2) and next_char in ('(','['):
   closing=')' if next_char=='(' else ']';out.append('\\\\'+next_char);i=end+1;continue
  if n in (1,2) and closing and next_char==closing:
   closing=None;out.append('\\\\'+next_char);i=end+1;continue
  if n%4==2 and next_char=='$':out.append(source[i:end]+'$');i=end+1;continue
  if n%2==0:out.append(source[i:end]);i=end;continue
  # Preserve literal quotes, slashes, Unicode escapes, and legitimate short JSON whitespace escapes.
  command=re.match(r'[A-Za-z]+',source[end:])
  unicode_escape=next_char=='u' and re.match(r'u[0-9a-fA-F]{4}',source[end:])
  invalid=next_char not in ('"','\\','/','b','f','n','r','t','u') or next_char=='u' and not unicode_escape
  latex_command=command is not None and command[0] in ESCAPE_COMMANDS and not unicode_escape
  if n==1 and closing and (invalid or latex_command):out.append('\\\\'+next_char)
  else:out.append(source[i:end]+next_char)
  i=end+bool(next_char)
 return ''.join(out)

def _pairs(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise ValueError('duplicate_field')
  result[key]=value
 return result

def _strict(source):
 def nonfinite(_):raise ValueError('json_nonfinite')
 def finite(token):
  value=float(token)
  if not math.isfinite(value):raise ValueError('json_nonfinite')
  return value
 return json.loads(source,object_pairs_hook=_pairs,parse_constant=nonfinite,parse_float=finite)

def shape_issues(value):
 issues=[]
 if not isinstance(value,dict) or not isinstance(value.get('questions'),list):return ['questions:list_required']
 if len(value['questions'])>20:return ['questions:too_many']
 for i,q in enumerate(value['questions']):
  prefix=f'questions[{i}]'
  if not isinstance(q,dict):issues.append(prefix+':object_required');continue
  for field in FIELDS:
   if field not in q:issues.append(prefix+'.'+field+':missing')
  # Values and diagram references are checked by the existing semantic validators.
  visits=0
  def controls(item,path,depth=0):
   nonlocal visits
   visits+=1
   if depth>40 or visits>20000 or len(issues)>=64:
    if len(issues)<64:issues.append(prefix+':structure_limit')
    return
   if isinstance(item,str) and any(ord(c)<32 and c not in '\n\r\t' for c in item):issues.append(path+':invalid_control')
   elif isinstance(item,dict):
    for k,v in item.items():controls(v,path+'.'+(k if k in set(FIELDS)|TEXT_FIELDS else 'field'),depth+1)
   elif isinstance(item,list):
    for j,v in enumerate(item):controls(v,f'{path}[{j}]',depth+1)
  controls(q,prefix)
 return issues[:64]

def parse_practice_reply(source,*,task=None):
 started=time.monotonic()
 if not isinstance(source,str) or len(source)>MAX_REPLY:raise PracticeReplyError('', ['reply:invalid_size'])
 normalized=normalize_latex(_unwrap(source))
 try:value=_strict(normalized)
 except (ValueError,RecursionError) as error:
  position=error.pos if isinstance(error,json.JSONDecodeError) else 0
  code=str(error) if str(error) in ('duplicate_field','json_nonfinite') else 'invalid_json'
  raise PracticeReplyError(source,[code],position,normalized=normalized) from None
 issues=shape_issues(value)
 if issues:raise PracticeReplyError(source,issues,normalized=normalized)
 if normalized!=source:record_event('stage_completed',task,operation='practice',stage='json_recovery',reason='practice_format_normalized',elapsed_ms=round((time.monotonic()-started)*1000))
 return value

def preserves_existing(source,after):
 """Do not accept model changes to existing scalars, options, answers, evidence, or diagram data."""
 try:before=_strict(source)
 except (ValueError,RecursionError):
  from course_json import _tokens
  # Missing final braces can be verified, but missing strings/values cannot be invented.
  candidate=source;stack=[];i=0
  try:
   while i<len(source):
    c=source[i]
    if c=='"':_,i=json.decoder.scanstring(source,i+1,True);continue
    if c in '[{':stack.append(c)
    elif c in ']}':
     if not stack or stack.pop()!=('[' if c==']' else '{'):return False
    i+=1
  except ValueError:return False
  candidate+=''.join(']' if c=='[' else '}' for c in reversed(stack))
  tokens=_tokens(candidate)
  return tokens is not None and tokens==_tokens(json.dumps(after,ensure_ascii=False))
 def same(old,new):
  if isinstance(old,dict):return isinstance(new,dict) and all(k in new and same(v,new[k]) for k,v in old.items())
  if isinstance(old,list):return isinstance(new,list) and len(old)==len(new) and all(same(a,b) for a,b in zip(old,new))
  return type(old) is type(new) and old==new
 return same(before,after)

def readable_original_questions(error):
 """On failed correction, only salvage a readable batch with missing fields, never malformed JSON/control text."""
 if not error.issues or not all(issue.endswith(':missing') for issue in error.issues):return None
 try:value=_strict(error.source)
 except (ValueError,RecursionError):return None
 if isinstance(value,dict) and isinstance(value.get('questions'),list):return value
 return None

def repair_instruction(error):
 return ('上一条出题回复未通过 JSON 格式检查。只修复格式，不重新出题，不增删题目，不改已有题干、公式、数字、选项顺序、answerIndex、sourceIds、算式和图结构。'
         '保留全部原请求材料与范围；一次处理以下全部格式问题：'+json.dumps(error.issues,ensure_ascii=False)+
         '。返回完整的单个 JSON 对象，顶层 questions 数组；所有字符串按 JSON 标准转义，LaTeX 反斜杠双写。缺少格式字段时补全，已有字段不得重复，不加代码块和解释。')
