"""Persistent, bounded model diagnostics; never log request/response bodies."""
from datetime import datetime,timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
import json,logging,os,re,threading,time,uuid
from urllib.error import HTTPError
from urllib.request import urlopen

log=logging.getLogger('uvicorn.error.model_diagnostics')
log.setLevel(logging.INFO)
_lock=threading.RLock()
_file=None
_folder=None
_NUMBERS={'json_line','json_column','json_position','history_rounds','history_questions','history_summarized','history_characters','note_nodes','batch_size','segments','characters','audio_duration_ms','image_count','input_characters','request_bytes','response_bytes','response_characters','elapsed_ms','http_status','prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens','reasoning_tokens','topics','examples','attempt','accepted_count','rejected_count','requested_count','max_output_tokens','timeout_seconds'}
_FINISH={'stop','length','tool_calls','function_call','content_filter','insufficient_system_resource','insufficient_balance','unknown','missing'}
_OPERATIONS={'transcription','course_map','grouped_map','direct_map','overview','practice'}
_STAGES={'history','config','probe','audio_decode','model_load','recognition','request','response_json','response_structure','finish_check','model_json','provider','validation','completed','cancelled','provider_request','response_schema','notes_validation','section_summary','section_objectives','section_keyPoints','section_pitfalls','section_highlights'}
_SAFE_REASONS={'out_of_memory','timeout','invalid_json','Missing headline','Missing section','Missing evidence','Unknown evidence','Invalid note sources','Unknown note evidence','Invalid note tree','Invalid note node','Invalid note point','Unsourced note point','Unsourced note title','Invalid note anchor','Invalid notes','Missing course notes','Missing note content','Duplicate source IDs','Incomplete overview','Overview provider is not configured'}
_EVENTS={'stage_started','request_started','response_received','request_completed','request_failed','stage_completed','stage_failed','diagnostic_check'}

def close_logs():
    global _file,_folder
    with _lock:
        if _file is not None:_file.close()
        _file=None;_folder=None


def record_event(event,task='unbound',**fields):
    if event not in _EVENTS:return
    task=task if isinstance(task,str) and re.fullmatch(r'[0-9a-fA-F-]{36}',task) else 'unbound'
    item={'timestamp':datetime.now(timezone.utc).isoformat(),'event':event,'task':task}
    for key,value in fields.items():
        if key in _NUMBERS and type(value) is int and value>=0:item[key]=value
        elif key=='notes_present' and type(value) is bool:item[key]=value
        elif key=='device' and value in {'cpu','cuda'}:item[key]=value
        elif key=='compute_type' and value in {'int8','float16','float32','int8_float16'}:item[key]=value
        elif key=='engine' and value in {'standard','batch'}:item[key]=value
        elif key=='operation' and value in _OPERATIONS:item[key]=value
        elif key=='stage' and value in _STAGES:item[key]=value
        elif key=='finish_reason':item[key]=value if value in _FINISH else 'unknown'
        elif key=='status' and value in ('completed','failed','empty','cancelled'):item[key]=value
        elif key=='request_id' and isinstance(value,str) and re.fullmatch(r'[0-9a-f-]{36}',value):item[key]=value
        elif key=='reason' and isinstance(value,str) and (value in _SAFE_REASONS or re.fullmatch(r'http_[1-5][0-9]{2}',value)):item[key]=value
        elif key=='error_type' and isinstance(value,str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,60}',value):item[key]=value
        elif key=='model' and isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',value):item[key]=value
    text=json.dumps(item,ensure_ascii=False,separators=(',',':'))
    global _file,_folder
    with _lock:
        try:
            folder=Path(os.environ.get('MODEL_LOG_DIR',str(Path(__file__).resolve().parent.parent/'.local/logs'))).resolve()
            if _file is None or folder!=_folder:
                if _file is not None:_file.close()
                folder.mkdir(parents=True,exist_ok=True)
                _file=RotatingFileHandler(folder/'model-events.jsonl',maxBytes=5*1024*1024,backupCount=3,encoding='utf-8')
                _file.setFormatter(logging.Formatter('%(message)s'));_folder=folder
            _file.handle(logging.LogRecord(log.name,logging.INFO,'',0,text,(),None))
        except OSError:
            log.warning('model_diagnostics_file_unavailable')
    log.info(text)

def request_model_json(request,timeout,task,operation,*,transport=urlopen,image_count=0,input_characters=0,model=None,output_limit=None,error_prefix='Incomplete model response'):
    started=time.monotonic();request_id=str(uuid.uuid4());stage='request'
    common={'request_id':request_id,'operation':operation,'model':model}
    record_event('request_started',task,**common,image_count=image_count,input_characters=input_characters,request_bytes=len(request.data or b''),max_output_tokens=output_limit,timeout_seconds=timeout)
    try:
        with transport(request,timeout=timeout) as response:
            raw=response.read()
        stage='response_json';envelope=json.loads(raw)
        stage='response_structure'
        if not isinstance(envelope,dict) or not isinstance(envelope.get('choices'),list) or not envelope['choices'] or not isinstance(envelope['choices'][0],dict):raise ValueError('Invalid model response structure')
        choice=envelope['choices'][0];reason=choice.get('finish_reason')
        reason=reason if isinstance(reason,str) and reason in _FINISH else 'missing' if reason is None else 'unknown'
        message=choice.get('message') or {};content=message.get('content') if isinstance(message,dict) else None
        usage=envelope.get('usage') or {};usage=usage if isinstance(usage,dict) else {}
        counts={key:value for key,value in usage.items() if key in _NUMBERS and type(value) is int and value>=0}
        details=usage.get('completion_tokens_details') or {}
        if isinstance(details,dict) and type(details.get('reasoning_tokens')) is int:counts['reasoning_tokens']=details['reasoning_tokens']
        record_event('response_received',task,**common,finish_reason=reason,response_bytes=len(raw),response_characters=len(content) if isinstance(content,str) else 0,elapsed_ms=int((time.monotonic()-started)*1000),**counts)
        stage='finish_check'
        if reason!='stop':raise ValueError(f'{error_prefix} (finish_reason={reason})')
        stage='model_json'
        if not isinstance(content,str):raise ValueError('Invalid model content')
        result=json.loads(content)
        record_event('request_completed',task,**common,stage='completed',elapsed_ms=int((time.monotonic()-started)*1000))
        return result
    except Exception as error:
        extra={'http_status':error.code} if isinstance(error,HTTPError) else {}
        if isinstance(error,json.JSONDecodeError):extra.update(reason='invalid_json',json_line=error.lineno,json_column=error.colno,json_position=error.pos)
        record_event('request_failed',task,**common,stage=stage,error_type=type(error).__name__,elapsed_ms=int((time.monotonic()-started)*1000),**extra)
        raise
