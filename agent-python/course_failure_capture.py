"""Bounded LOCAL private failure artifacts, separate from metadata logs/exports.
User-authorized debugging material: never used as a model request or course result.
"""
from datetime import datetime,timezone
from pathlib import Path
import json,os,re,threading,time,uuid

MAX_FILES=12
MAX_FILE_BYTES=4*1024*1024
MAX_TOTAL_BYTES=32*1024*1024
MAX_AGE_SECONDS=7*24*3600
_lock=threading.RLock()

def _id(value):
 try:return str(uuid.UUID(str(value)))
 except (ValueError,TypeError,AttributeError):return 'unbound'

def _redact(text,secrets=()):
 original=text
 for secret in secrets:
  if isinstance(secret,str) and secret:text=text.replace(secret,'[REDACTED]')
 for name,value in os.environ.items():
  if re.search(r'(?:API_KEY|TOKEN|SECRET|PASSWORD)$',name,re.I) and len(value)>=8:
   text=text.replace(value,'[REDACTED]')
 text=re.sub(r'(?i)Bearer[ \t]+[^\s"\\,}]+','Bearer [REDACTED]',text)
 text=re.sub(r'(?i)\bsk-[A-Za-z0-9_-]{8,}','[REDACTED]',text)
 text=re.sub(r'data:image/[^;,\s]+;base64,[A-Za-z0-9+/=\r\n]+','[IMAGE_REDACTED]',text)
 return text,text!=original

def save_failure(error,*,task,request_id,stage,finish_reason,secrets=()):
 """Best effort, whole-artifact-or-skip; never mask the original exception."""
 if os.environ.get('MODEL_FAILURE_CAPTURE','1')=='0':return None
 text=getattr(error,'doc',None)
 if not isinstance(text,str) or len(text)>MAX_FILE_BYTES:return None
 try:
  from model_diagnostics import record_event
  response,redacted=_redact(text,secrets)
  issues=[]
  for issue in getattr(error,'issues',[])[:128]:
   safe={k:v for k,v in issue.items() if k in {'position','line','column'} and type(v) is int}
   for field,allowed in [('code',{'parse_error','duplicate_field','missing_field','invalid_type','inspection_incomplete'}),('syntaxReason',{'syntax_expected_comma','syntax_expected_colon','syntax_expected_property','syntax_expected_value','syntax_unterminated_string','syntax_invalid_control','syntax_invalid_escape','syntax_invalid_unicode','syntax_invalid_json','syntax_trailing_content','syntax_root_not_object'})]:
    if issue.get(field) in allowed:safe[field]=issue[field]
   issues.append(safe)
  artifact={'format':'framewise-private-model-failure','version':1,'createdAt':datetime.now(timezone.utc).isoformat(),'task':_id(task),'requestId':_id(request_id),'stage':stage if stage in {'model_json','finish_check','content_preservation'} else 'model_json','finishReason':finish_reason if finish_reason in {'stop','length','content_filter','missing'} else 'unknown','responseCharacters':len(text),'redacted':redacted,'position':getattr(error,'pos',None),'errorCode':getattr(error,'code',None) if getattr(error,'code',None) in {'json_structure_invalid','json_invalid_syntax','json_content_changed','json_repair_unchanged','json_trailing_content','json_duplicate_key'} else 'invalid_json','issues':issues,'response':response}
  data=(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n').encode('utf8')
  if len(data)>MAX_FILE_BYTES:
   record_event('diagnostic_check',task,operation='course_map',stage='failure_capture',request_id=request_id,status='failed',reason='failure_capture_too_large');return None
  folder=Path(os.environ.get('MODEL_LOG_DIR',str(Path(__file__).resolve().parent.parent/'.local/logs')))/'private-model-failures'
  # Reject symlink/junction components; never follow a redirected artifact store.
  for part in (folder,*folder.parents):
   if part.is_symlink() or part.exists() and getattr(part.lstat(),'st_file_attributes',0)&0x400:raise OSError('linked_failure_store')
  with _lock:
   folder.mkdir(parents=True,exist_ok=True,mode=0o700)
   files=[];now=time.time()
   for file in folder.glob('*.json'):
    if file.is_symlink() or not file.is_file():continue
    stat=file.stat()
    if now-stat.st_mtime>MAX_AGE_SECONDS:file.unlink()
    else:files.append((stat.st_mtime,file,stat.st_size))
   files.sort();size=sum(x[2] for x in files)
   while files and (len(files)>=MAX_FILES or size+len(data)>MAX_TOTAL_BYTES):
    _,old,n=files.pop(0);old.unlink();size-=n
   if len(data)>MAX_TOTAL_BYTES or MAX_FILES<1:return None
   target=folder/(str(uuid.uuid4())+'.json')
   try:
    with target.open('xb') as output:os.chmod(target,0o600);output.write(data)
   except OSError:
    target.unlink(missing_ok=True);raise
  record_event('diagnostic_check',task,operation='course_map',stage='failure_capture',request_id=request_id,status='completed',reason='failure_capture_saved')
  return target
 except (OSError,ValueError,TypeError,RecursionError):
  from model_diagnostics import record_event
  record_event('diagnostic_check',task,operation='course_map',stage='failure_capture',request_id=request_id,status='failed',reason='failure_capture_unavailable')
  return None
