"""Instrumentation only: all responses come from the real configured DeepSeek endpoint."""
from pathlib import Path
import io,json,os,time,threading,importlib,uuid,sys
sys.path.insert(0,"/app")
from urllib.request import urlopen as real_urlopen
from urllib.error import HTTPError
LIMIT=int(os.environ.get('FRAMEWISE_LIVE_LIMIT','20'))
OUT=Path('/qa');lock=threading.Lock();count=len((OUT/'requests.jsonl').read_text().splitlines()) if (OUT/'requests.jsonl').exists() else 0
class Response(io.BytesIO):
 status=200
 def getcode(self):return 200

def transport(operation):
 def call(request,timeout=180,**kwargs):
  global count
  with lock:
   if count>=LIMIT:raise RuntimeError('live_qa_request_budget_exhausted')
   count+=1;index=count
  start=time.monotonic();case=json.loads((OUT/'current-case.json').read_text()).get('name','background');body=json.loads(request.data or b'{}');entry={'index':index,'operation':operation,'case':case,'requestId':str(uuid.uuid4()),'imageCount':sum(1 for message in body.get('messages',[]) if isinstance(message.get('content'),list) for item in message['content'] if item.get('type')=='image_url')}
  try:
   with real_urlopen(request,timeout=timeout,**kwargs) as response:raw=response.read();entry['httpStatus']=response.status
   envelope=json.loads(raw);choice=(envelope.get('choices') or [{}])[0];
   content=(choice.get('message') or {}).get('content','')
   try:json.loads(content);entry['contentJsonValid']=True
   except json.JSONDecodeError as problem:
    entry.update(contentJsonValid=False,jsonError=problem.msg,jsonPosition=problem.pos,contentCharacters=len(content))
    try:json.loads(content+'}');entry['missingFinalObjectBrace']=True
    except (ValueError,TypeError):pass
   entry['finishReason']=choice.get('finish_reason');usage=envelope.get('usage',{});entry['usage']={k:v for k,v in usage.items() if k in ['prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens'] and type(v) is int};return Response(raw)
  except Exception as error:
   entry['errorType']=type(error).__name__
   if isinstance(error,HTTPError):entry['httpStatus']=error.code
   raise
  finally:
   entry['elapsedMs']=round((time.monotonic()-start)*1000)
   with lock:
    with (OUT/'requests.jsonl').open('a') as file:file.write(json.dumps(entry)+'\n')
 return call
for name in ['course_mind_map','overview','overview_chat','practice','question_chat','chapters','subtitle_calibration','image_understanding','page_understanding','agent_review','auto_region','mind_map']:
 module=importlib.import_module(name)
 if hasattr(module,'urlopen'):module.urlopen=transport(name)
import uvicorn
uvicorn.run('app:app',host='0.0.0.0',port=8000,log_level='warning')
