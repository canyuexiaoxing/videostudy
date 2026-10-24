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
_NUMBERS={'issue_count','duplicate_key_count','missing_ref_count','json_document_count','requested_time_ms','actual_time_ms','queue_peak','promoted_count','deferred_count','shortened_count','invalid_ref_count','repaired_ref_count','person_frames','uncertain_frames','reveal_frames','inference_ms','json_line','json_column','json_position','history_rounds','history_questions','history_summarized','history_characters','note_nodes','batch_size','segments','characters','audio_duration_ms','image_count','input_characters','request_bytes','response_bytes','response_characters','elapsed_ms','http_status','prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens','reasoning_tokens','topics','examples','attempt','accepted_count','rejected_count','requested_count','max_output_tokens','timeout_seconds'}
_FINISH={'stop','length','tool_calls','function_call','content_filter','insufficient_system_resource','insufficient_balance','unknown','missing'}
_OPERATIONS={'person_grouping','frame_pipeline','person_selection','transcription','course_map','grouped_map','direct_map','overview','practice'}
_STAGES={'reply_repair','mask_persistence','page_grouping','json_recovery','json_repair','decode','citation_repair','capture','normalization','selection','fallback','history','config','probe','audio_decode','model_load','recognition','request','response_json','response_structure','finish_check','model_json','provider','validation','completed','cancelled','provider_request','response_schema','notes_validation','section_summary','section_objectives','section_keyPoints','section_pitfalls','section_highlights'}
_SAFE_REASONS={'reply_issue_limit','reply_visit_limit','reply_unreadable','reply_ambiguous_documents','reply_inspection_failed','reply_inspection_incomplete','json_structure_invalid','person_mask_write_failed','person_mask_unavailable','json_identical_key','reference_missing','json_duplicate_key','json_nonfinite','json_trailing_content','json_root_invalid','json_multiple_fragments','json_invalid_syntax','json_ambiguous_documents','json_many_documents','json_empty','json_identical_repeat','json_wrapper_removed','json_content_changed','json_repair_failed','repair_budget_exhausted','video_frame_sampling_failed','video_input_unavailable','video_input_invalid','video_decode_failed','video_filter_or_encoder_failed','video_output_unavailable','video_output_io_failed','reference_repair_rejected','reference_repair_failed','video_display_rotation_unsupported','video_frame_timestamp_missing','video_frame_timestamp_regressed','frame_time_outside_video','analysis_cancelled','reference_unknown','reference_wrong_type','reference_disallowed','reference_format_invalid','reference_repaired','citation_report_unavailable','person_model_invalid','person_cuda_unavailable','person_model_load_failed','person_runtime_unavailable','person_inference_failed','out_of_memory','timeout','invalid_json','Missing headline','Missing section','Missing evidence','Unknown evidence','Invalid note sources','Unknown note evidence','Invalid note tree','Invalid note node','Invalid note point','Unsourced note point','Unsourced note title','Invalid note anchor','Invalid notes','Missing course notes','Missing note content','Duplicate source IDs','Incomplete overview','Overview provider is not configured'}
_EVENTS={'stage_started','request_started','response_received','request_completed','request_failed','stage_completed','stage_failed','diagnostic_check'}

_SAFE_REASONS.update({'diagram_answer_mismatch', 'invalid_diagram_edge', 'degenerate_triangle', 'invalid_number', 'invalid_diagram_points', 'wrong_calculation', 'overlapping_circuit_edges', 'circuit_answer_mismatch', 'invalid_diagram_number', 'invalid_geometry_check', 'invalid_circuit_check', 'invalid_chart_check', 'invalid_options', 'duplicate_or_large_point', 'undefined_chart_check', 'outside_random_plan', 'shorted_battery', 'previous_question_repeated', 'function_sampling_too_coarse', 'invalid_geometry_angle', 'unsupported_chart_check', 'invalid_switch_state', 'function_not_visible', 'invalid_chart_values', 'invalid_function_curves', 'chart_answer_mismatch', 'circuit_underdetermined', 'unknown_node', 'invalid_function_range', 'invalid_circuit_component', 'missing_or_long_text', 'unsupported_circuit_topology', 'function_undefined', 'unsupported_diagram', 'invalid_diagram_text', 'invalid_diagram_id', 'nonunique_answer', 'invalid_circle', 'invalid_question', 'invalid_diagram_point', 'invalid_function_curve', 'empty_geometry', 'geometry_label_mismatch', 'missing_calculation', 'option_text_value_mismatch', 'ungrounded_question', 'invalid_option_values', 'invalid_function_check', 'geometry_too_complex', 'unsupported_circuit_calculation', 'invalid_answer', 'invalid_task', 'invalid_practice_response', 'invalid_circuit_components', 'unsupported_question_kind', 'exponent_too_large', 'unsupported_function_expression', 'function_expression_too_complex', 'missing_option_reasons', 'outside_view', 'duplicate_chart_label', 'invalid_circuit_value', 'invalid_circuit_parameter', 'duplicate_question', 'ambiguous_circuit_crossing', 'unsupported_geometry_check', 'invalid_practice_request', 'invalid_diagram', 'invalid_calculation', 'invalid_function_expression', 'floating_circuit_target', 'duplicate_options', 'invalid_practice_question', 'invalid_practice_mode', 'unsupported_chart_question', 'circuit_component_too_short', 'invalid_pie_values'})
_SAFE_REASONS.update({'syntax_expected_comma','syntax_expected_colon','syntax_expected_property','syntax_expected_value','syntax_unterminated_string','syntax_invalid_control','syntax_invalid_escape','syntax_invalid_unicode','syntax_invalid_json','syntax_trailing_content','syntax_root_not_object'})
_SAFE_REASONS.update({'invalid_chat_reply','unknown_chat_evidence'})
_SAFE_REASONS.update({'practice_format_normalized','practice_format_invalid','practice_original_questions_retained'})
_OPERATIONS.update({'question_chat','overview_chat','compatibility'})
_STAGES.update({'diagram_validation','reply_validation','course_materials'})
_NUMBERS.update({'question_index','returned_count','missing_count'})
_STAGES.add('quantity_fill')
_STAGES.add('outline_validation')
_STAGES.add('failure_capture')
_SAFE_REASONS.update({'failure_capture_saved','failure_capture_unavailable','failure_capture_too_large','json_repair_unchanged'})
_NUMBERS.update({'outline_missing_count','outline_review_count','outline_ignored_count'})
_SAFE_REASONS.update({'practice_fill_failed','practice_calculation_unchecked'})

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
        elif key=='exit_code' and type(value) is int and -255<=value<=255:item[key]=value
        elif key=='notes_present' and type(value) is bool:item[key]=value
        elif key=='device' and value in {'cpu','cuda'}:item[key]=value
        elif key=='strategy' and value in {'history','adjacent'}:item[key]=value
        elif key=='node_path' and isinstance(value,str) and len(value)<=256 and re.fullmatch(r'root|(?:children|examples|candidateDecisions)\[\d+\](?:\.(?:(?:children|details|examples|candidateDecisions)\[\d+\]|mergeEvidence))*',value):item[key]=value
        elif key=='json_path' and isinstance(value,str) and len(value)<=256 and re.fullmatch(r'root(?:\.(?:topic|children|details|examples|uncertainties|title|sourceIds|imageIds|mergeEvidence|candidateDecisions|reason|startMs|endMs|id|type|quote|field)|\[\d+\])*',value):item[key]=value
        elif key=='reference_field' and value in {'sourceIds','imageIds'}:item[key]=value
        elif key=='reference_id' and isinstance(value,str) and len(value)<=80 and re.fullmatch(r'(?:t_\d+|frame_\d+|page_\d+_(?:knowledge|example)_\d+)',value):item[key]=value
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

def request_model_json(request,timeout,task,operation,*,transport=urlopen,image_count=0,input_characters=0,model=None,output_limit=None,error_prefix='Incomplete model response',content_parser=None):
    started=time.monotonic();request_id=str(uuid.uuid4());stage='request';content=None;reason='missing'
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
        result=content_parser(content) if content_parser is not None else json.loads(content)
        record_event('request_completed',task,**common,stage='completed',elapsed_ms=int((time.monotonic()-started)*1000))
        return result
    except Exception as error:
        extra={'http_status':error.code} if isinstance(error,HTTPError) else {}
        if isinstance(error,json.JSONDecodeError):extra.update(reason='invalid_json',json_line=error.lineno,json_column=error.colno,json_position=error.pos)
        if operation=='course_map' and isinstance(content,str) and (isinstance(error,json.JSONDecodeError) and stage=='model_json' or stage=='finish_check'):
            from course_failure_capture import save_failure
            authorization=request.get_header('Authorization','')
            secret=authorization[7:] if authorization.lower().startswith('bearer ') else ''
            failure=error if isinstance(error,json.JSONDecodeError) else json.JSONDecodeError('incomplete_response',content,len(content))
            save_failure(failure,task=task,request_id=request_id,stage=stage,finish_reason=reason,secrets=(secret,))
        record_event('request_failed',task,**common,stage=stage,error_type=type(error).__name__,elapsed_ms=int((time.monotonic()-started)*1000),**extra)
        raise

_SAFE_REASONS.update({'question_answer_conflict','practice_partial_questions_retained'})
