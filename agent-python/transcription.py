"""Transcribe a server-owned temporary video with a locally stored Whisper model."""

import os
import subprocess
import time
from model_diagnostics import record_event
from pathlib import Path
from uuid import UUID
from functools import lru_cache
from threading import Lock


def transcription_config():
    model=os.environ.get('WHISPER_MODEL','base').strip()
    device=os.environ.get('WHISPER_DEVICE','cpu').strip()
    precision=os.environ.get('WHISPER_COMPUTE_TYPE','float16' if device=='cuda' else 'int8').strip()
    if model not in {'tiny','base','small','medium','large-v3','large-v3-turbo'}:raise ValueError('Unsupported Whisper model')
    if device not in {'cpu','cuda'}:raise ValueError('Unsupported Whisper device')
    if precision not in {'int8','float16','float32','int8_float16'}:raise ValueError('Unsupported Whisper precision')
    if device=='cpu' and precision in {'float16','int8_float16'}:raise ValueError('CPU Whisper needs int8 or float32')
    return model,device,precision

def transcription_batch_size(device):
    value=os.environ.get('WHISPER_BATCH_SIZE','4' if device=='cuda' else '0').strip()
    if value not in {'0','1','2','4','8'}:raise ValueError('Unsupported Whisper batch size')
    return int(value)


def speech_checkpoint_key():
    model,device,precision=transcription_config()
    legacy=f'faster-whisper-{model}:beam5:vad:{precision}'
    key=legacy if (model,device,precision)==('base','cpu','int8') else legacy+':'+device
    batch=transcription_batch_size(device)
    return key+f':batch{batch}:segment-timestamps:vad-minsilence2000' if batch else key

_model_lock=Lock()
@lru_cache(maxsize=1)
def _load_model(model_path,device,precision):
    from faster_whisper import WhisperModel
    return WhisperModel(model_path,device=device,compute_type=precision)

def _get_model(model_path,device,precision):
    # Serialize first load so simultaneous tasks do not allocate two copies.
    with _model_lock:return _load_model(model_path,device,precision)


def _get_batch_pipeline(model):
    from faster_whisper import BatchedInferencePipeline
    # Pipeline has mutable per-transcription state; only model weights are shared.
    return BatchedInferencePipeline(model=model)


def _decode_audio(path):
    from faster_whisper.audio import decode_audio
    return decode_audio(str(path),sampling_rate=16000)


def _transcribe_file_once(file_id: str, on_segment=None, *, _runtime_override=None) -> dict:
    UUID(file_id)
    upload_root=Path(os.environ.get('MEDIA_TEMP_DIR','../.local/uploads')).resolve()
    video_path=upload_root/file_id
    if not video_path.is_file():raise FileNotFoundError('uploaded media not found')
    started=time.monotonic();stage='config';common={'operation':'transcription'}
    def begin(name):
        nonlocal stage
        stage=name
        record_event('stage_started',file_id,**common,stage=stage)
        return time.monotonic()
    def done(since,**counts):
        record_event('stage_completed',file_id,**common,stage=stage,elapsed_ms=round((time.monotonic()-since)*1000),**counts)
    try:
        model_name,device,precision=transcription_config()
        batch=transcription_batch_size(device)
        if _runtime_override is not None:model_name,device,precision,batch=_runtime_override
        common.update(model=model_name,device=device,compute_type=precision,engine='batch' if batch else 'standard',batch_size=batch)
        mark=begin('probe')
        probe=subprocess.run(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=index','-of','csv=p=0',str(video_path)],capture_output=True,text=True,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        done(mark)
        if not probe.stdout.strip():
            record_event('stage_completed',file_id,**common,stage='completed',status='empty',segments=0,elapsed_ms=round((time.monotonic()-started)*1000))
            return {'language':'und','segments':[]}
        model_path=Path(os.environ.get('MODEL_DIR','../.local/models')).resolve()/('faster-whisper-'+model_name)
        stage='model_load'
        if not (model_path/'model.bin').is_file():raise FileNotFoundError('Whisper model is missing from the project model directory')
        mark=begin('model_load');model=_get_model(str(model_path),device,precision);done(mark)
        audio=None
        if batch:
            mark=begin('audio_decode');audio=_decode_audio(video_path)
            done(mark,audio_duration_ms=round(len(audio)/16000*1000))
        mark=begin('recognition')
        if batch:
            segments,info=_get_batch_pipeline(model).transcribe(audio,beam_size=5,vad_filter=True,batch_size=batch,without_timestamps=False,vad_parameters={'min_silence_duration_ms':2000})
        else:
            segments,info=model.transcribe(str(video_path),beam_size=5,vad_filter=True)
        result=[]
        for index,segment in enumerate(segments,start=1):
            stage='validation'
            item={'id':f't_{index}','startMs':round(segment.start*1000),'endMs':round(segment.end*1000),'text':segment.text.strip()}
            if item['startMs']<0 or item['endMs']<item['startMs']:
                raise ValueError('Invalid transcription segment timestamps')
            result.append(item)
            if on_segment is not None:on_segment(dict(item))
            stage='recognition'
        done(mark,segments=len(result),characters=sum(len(item['text']) for item in result))
        record_event('stage_completed',file_id,**common,stage='completed',status='completed',segments=len(result),elapsed_ms=round((time.monotonic()-started)*1000))
        return {'language':info.language,'segments':result}
    except Exception as error:
        reason='out_of_memory' if 'out of memory' in str(error).lower() else None
        record_event('stage_failed',file_id,**common,stage=stage,status='cancelled' if type(error).__name__=='CancelledError' else 'failed',error_type=type(error).__name__,reason=reason,elapsed_ms=round((time.monotonic()-started)*1000))
        raise


def transcribe_file(file_id: str, on_segment=None) -> dict:
    """Retry only before streaming output; callbacks already published cannot be replayed."""
    from native_devices import allow_cpu_fallback,record_fallback
    emitted=False
    def deliver(item):
        nonlocal emitted
        emitted=True
        if on_segment is not None:on_segment(item)
    override=None
    while True:
        try:
            return _transcribe_file_once(file_id,deliver,_runtime_override=override)
        except Exception as error:
            model,device,precision=transcription_config() if override is None else override[:3]
            batch=transcription_batch_size(device) if override is None else override[3]
            if emitted or not allow_cpu_fallback(error,device):raise
            if batch>1:
                smaller=batch//2
                record_event('stage_failed',file_id,operation='transcription',stage='fallback',device='cuda',reason='out_of_memory',batch_size=smaller,error_type=type(error).__name__,status='failed')
                override=(model,device,precision,smaller)
            else:
                record_fallback('whisper',error,file_id)
                _load_model.cache_clear()
                override=(model,'cpu','int8',0)

