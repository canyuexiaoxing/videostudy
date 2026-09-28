"""Select changed video frames before running OCR; keep timestamps in milliseconds."""

from functools import lru_cache
import multiprocessing
from pathlib import Path
import subprocess
from typing import Callable

import cv2
import numpy as np


SAMPLE_SECONDS = 2
PREVIEW_WIDTH = 320
PREVIEW_HEIGHT = 180
FRAME_BYTES = PREVIEW_WIDTH * PREVIEW_HEIGHT
OCR_MODEL_ID = "PP-OCRv6_medium"
PAGE_CHANGE_FRACTION = 0.005
PROGRESS_FRACTION = 0.001
MAX_PROGRESS_INTERVAL_MS = 30_000


def _has_video(path: Path) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True,
    )
    return bool(result.stdout.strip())


def _candidate_times(path: Path) -> list[int]:
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-vf", f"fps=1/{SAMPLE_SECONDS},scale={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:force_original_aspect_ratio=decrease,"
               f"pad={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None and process.stderr is not None
    previous = None
    previous_ms = 0
    chosen: list[int] = []
    last_chosen_frame = None
    last_chosen_ms = 0
    first_frame = None
    index = 0
    try:
        while frame_bytes := process.stdout.read(FRAME_BYTES):
            if len(frame_bytes) != FRAME_BYTES:
                raise RuntimeError("FFmpeg returned an incomplete preview frame")
            frame = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(PREVIEW_HEIGHT, PREVIEW_WIDTH)
            time_ms = index * SAMPLE_SECONDS * 1000
            if first_frame is None:
                first_frame = frame.copy()
            if previous is not None:
                changed_fraction = float(np.mean(cv2.absdiff(previous, frame) > 25))
                if changed_fraction > PAGE_CHANGE_FRACTION:
                    if not chosen or chosen[-1] != previous_ms:
                        chosen.append(previous_ms)
                    last_chosen_frame = previous.copy()
                    last_chosen_ms = previous_ms
                elif time_ms - last_chosen_ms >= MAX_PROGRESS_INTERVAL_MS:
                    baseline = last_chosen_frame if last_chosen_frame is not None else first_frame
                    progress = float(np.mean(cv2.absdiff(baseline, previous) > 25))
                    if progress > PROGRESS_FRACTION:
                        chosen.append(previous_ms)
                        last_chosen_frame = previous.copy()
                        last_chosen_ms = previous_ms
            previous = frame.copy()
            previous_ms = time_ms
            index += 1
        error = process.stderr.read().decode(errors="replace")
        if process.wait() != 0:
            raise RuntimeError(f"FFmpeg frame sampling failed: {error.strip()}")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()
    if previous is not None and (not chosen or chosen[-1] != previous_ms):
        chosen.append(previous_ms)
    return chosen


def _frame_at(path: Path, time_ms: int) -> np.ndarray:
    image = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{time_ms / 1000:.3f}",
         "-i", str(path), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"],
        capture_output=True, check=True,
    ).stdout
    frame = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError(f"Could not decode video frame at {time_ms} ms")
    return frame


@lru_cache(maxsize=1)
def _ocr_model():
    from paddleocr import PaddleOCR
    import os

    root = Path(os.environ.get("MODEL_DIR", "../.local/models")) / "paddleocr"
    detection = root / "PP-OCRv6_medium_det_infer"
    recognition = root / "PP-OCRv6_medium_rec_infer"
    if not detection.is_dir() or not recognition.is_dir():
        raise FileNotFoundError("PP-OCRv6 medium models are missing from the project model directory")
    return PaddleOCR(
        text_detection_model_name="PP-OCRv6_medium_det",
        text_detection_model_dir=str(detection),
        text_recognition_model_name="PP-OCRv6_medium_rec",
        text_recognition_model_dir=str(recognition),
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        device="cpu",
    )


def _recognize(frame: np.ndarray) -> list[dict]:
    result = _ocr_model().predict(frame)[0].json["res"]
    texts = result.get("rec_texts", [])
    scores = result.get("rec_scores", [])
    polygons = result.get("rec_polys", [])
    return [
        {"text": text, "score": float(score),
         "polygon": polygon.tolist() if hasattr(polygon, "tolist") else polygon}
        for text, score, polygon in zip(texts, scores, polygons)
    ]


def _save_keyframe(frame: np.ndarray, keyframe_dir: Path, time_ms: int) -> None:
    keyframe_dir.mkdir(parents=True, exist_ok=True)
    encoded, image = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not encoded:
        raise RuntimeError(f"Could not encode video frame at {time_ms} ms")
    temporary = keyframe_dir / f"{time_ms}.jpg.tmp"
    temporary.write_bytes(image.tobytes())
    temporary.replace(keyframe_dir / f"{time_ms}.jpg")


def analyze_visuals(path: Path, recognize: Callable[[np.ndarray], list[dict]] | None = None,
                    keyframe_dir: Path | None = None) -> list[dict]:
    """Return OCR from representative frames; audio-only input returns no visual evidence."""
    if not _has_video(path):
        return []
    recognize = recognize or _recognize
    evidence = []
    for time_ms in _candidate_times(path):
        frame = _frame_at(path, time_ms)
        if keyframe_dir is not None:
            _save_keyframe(frame, keyframe_dir, time_ms)
        evidence.append({"frameTimeMs": time_ms, "ocrBlocks": recognize(frame)})
    return evidence


def _serve_visual_requests(connection, media_path: str, keyframe_path: str | None) -> None:
    path = Path(media_path)
    keyframe_dir = Path(keyframe_path) if keyframe_path else None
    try:
        while request := connection.recv():
            try:
                if request["op"] == "analyze":
                    response = analyze_visuals(path, keyframe_dir=keyframe_dir)
                elif request["op"] == "capture":
                    frame = _frame_at(path, request["timeMs"])
                    if keyframe_dir is not None:
                        _save_keyframe(frame, keyframe_dir, request["timeMs"])
                    response = _recognize(frame)
                else:
                    raise ValueError("Unknown visual worker operation")
                connection.send({"ok": True, "value": response})
            except Exception as error:
                connection.send({"ok": False, "error": f"{type(error).__name__}: {error}"})
    except EOFError:
        pass
    finally:
        connection.close()


class VisualOcrWorker:
    """Keep PaddleOCR outside the process that runs faster-whisper."""

    def __init__(self, path: Path, keyframe_dir: Path | None = None):
        context = multiprocessing.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_serve_visual_requests,
                                       args=(child, str(path), str(keyframe_dir) if keyframe_dir else None))
        self.process.start()
        child.close()

    def _request(self, operation: str, **kwargs):
        self.connection.send({"op": operation, **kwargs})
        if not self.connection.poll(30 * 60):
            raise TimeoutError("Visual OCR worker timed out")
        answer = self.connection.recv()
        if not answer["ok"]:
            raise RuntimeError(answer["error"])
        return answer["value"]

    def analyze(self) -> list[dict]:
        return self._request("analyze")

    def capture(self, time_ms: int) -> list[dict]:
        return self._request("capture", timeMs=time_ms)

    def close(self) -> None:
        self.connection.close()
        self.process.join(timeout=5)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
