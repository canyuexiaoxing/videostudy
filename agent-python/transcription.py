"""Transcribe a server-owned temporary video with a locally stored Whisper model."""

import os
import subprocess
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

def speech_checkpoint_key():
    model,device,precision=transcription_config()
    legacy=f'faster-whisper-{model}:beam5:vad:{precision}'
    return legacy if (model,device,precision)==('base','cpu','int8') else legacy+':'+device

_model_lock=Lock()
@lru_cache(maxsize=1)
def _load_model(model_path,device,precision):
    from faster_whisper import WhisperModel
    return WhisperModel(model_path,device=device,compute_type=precision)

def _get_model(model_path,device,precision):
    # Serialize first load so simultaneous tasks do not allocate two copies.
    with _model_lock:return _load_model(model_path,device,precision)


def transcribe_file(file_id: str) -> dict:
    # UUID validation keeps the internal API from reading arbitrary filesystem paths.
    UUID(file_id)
    upload_root = Path(os.environ.get("MEDIA_TEMP_DIR", "../.local/uploads")).resolve()
    video_path = upload_root / file_id
    if not video_path.is_file():
        raise FileNotFoundError("uploaded media not found")

    model_root = Path(os.environ.get("MODEL_DIR", "../.local/models")).resolve()
    model_name,device,precision=transcription_config()
    model_path = model_root / ("faster-whisper-"+model_name)
    if not (model_path / "model.bin").is_file():
        raise FileNotFoundError("Whisper model is missing from the project model directory")

    # A screen recording can have no audio stream. Keep its visual analysis usable.
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True, check=True,
    )
    if not probe.stdout.strip():
        return {"language": "und", "segments": []}

    # Import only when a real transcription is requested; the demo API stays lightweight.
    # PyAV, bundled by faster-whisper, decodes the audio stream from the video.
    model = _get_model(str(model_path),device,precision)
    segments, info = model.transcribe(str(video_path), beam_size=5, vad_filter=True)
    result = [
        {"id": f"t_{index}", "startMs": round(segment.start * 1000),
         "endMs": round(segment.end * 1000), "text": segment.text.strip()}
        for index, segment in enumerate(segments, start=1)
    ]
    return {"language": info.language, "segments": result}
