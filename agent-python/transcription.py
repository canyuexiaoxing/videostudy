"""Transcribe a server-owned temporary video with a locally stored Whisper model."""

import os
import subprocess
from pathlib import Path
from uuid import UUID


def transcribe_file(file_id: str) -> dict:
    # UUID validation keeps the internal API from reading arbitrary filesystem paths.
    UUID(file_id)
    upload_root = Path(os.environ.get("MEDIA_TEMP_DIR", "../.local/uploads")).resolve()
    video_path = upload_root / file_id
    if not video_path.is_file():
        raise FileNotFoundError("uploaded media not found")

    model_root = Path(os.environ.get("MODEL_DIR", "../.local/models")).resolve()
    model_path = model_root / "faster-whisper-base"
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
    from faster_whisper import WhisperModel

    # PyAV, bundled by faster-whisper, decodes the audio stream from the video.
    model = WhisperModel(str(model_path), device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(video_path), beam_size=5, vad_filter=True)
    result = [
        {"id": f"t_{index}", "startMs": round(segment.start * 1000),
         "endMs": round(segment.end * 1000), "text": segment.text.strip()}
        for index, segment in enumerate(segments, start=1)
    ]
    return {"language": info.language, "segments": result}
