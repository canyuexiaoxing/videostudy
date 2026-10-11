"""Select changed video frames before running OCR; keep timestamps in milliseconds."""

from functools import lru_cache
import atexit
import multiprocessing
import tempfile
import threading
from pathlib import Path
import subprocess
from typing import Callable

import cv2
import numpy as np
import os
from checkpoints import Checkpoints
from ignored_region import normalize_setting as normalize_region,prepare_image,active_regions


SAMPLE_SECONDS = 2
PREVIEW_WIDTH = 320
PREVIEW_HEIGHT = 180
FRAME_BYTES = PREVIEW_WIDTH * PREVIEW_HEIGHT
OCR_MODEL_ID = "PP-OCRv6_medium"
PAGE_CHANGE_FRACTION = 0.02
PROGRESS_FRACTION = 0.001
MAX_PROGRESS_INTERVAL_MS = 30_000


def _has_video(path: Path) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True,
    )
    return bool(result.stdout.strip())


def _candidate_times(path: Path, page_change_fraction: float = PAGE_CHANGE_FRACTION,
                     sample_seconds: int = SAMPLE_SECONDS, ignore_region: dict | None = None) -> list[int]:
    if sample_seconds not in (2, 3, 4):
        raise ValueError("sample_seconds must be 2, 3 or 4")
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-vf", f"fps=1/{sample_seconds},scale={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:force_original_aspect_ratio=decrease,"
               f"pad={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
    ]
    ignore_region = normalize_region(ignore_region)
    read_bytes = FRAME_BYTES
    mask = None
    if ignore_region:
        included = ignore_region.get('analysisRegion') if 'analysisRegion' in ignore_region else None
        excluded = ignore_region.get('ignoredRegion') if 'analysisRegion' in ignore_region else ignore_region
        def timed_nodes(value):return value['nodes'] if value and 'nodes' in value else [{'timeMs':0,'region':value}]
        groups=[(timed_nodes(included),True),(timed_nodes(excluded),False)]
        geometry = f"scale={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:force_original_aspect_ratio=decrease,pad={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=gray"
        boxes = []
        for nodes,is_include in groups:
            for index,node in enumerate(nodes):
                r=node['region']
                if r is None:continue
                enabled=f"gte(t,{node['timeMs']/1000})"
                if index+1<len(nodes):enabled+=f"*lt(t,{nodes[index+1]['timeMs']/1000})"
                if is_include:boxes.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='{enabled}'")
                color='white' if is_include else 'black'
                boxes.append(f"drawbox=x=iw*{r['x']}:y=ih*{r['y']}:w=iw*{r['width']}:h=ih*{r['height']}:color={color}:t=fill:enable='{enabled}'")
        mask_filters = 'format=gray,lut=y=255,' + (','.join(boxes) + ',' if boxes else '') + geometry
        filters = (f"[0:v]fps=1/{sample_seconds},split=2[v][m];[v]{geometry}[p];"
                   f"[m]{mask_filters}[mask];[p][mask]vstack,format=gray[out]")
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                   "-filter_complex", filters, "-map", "[out]", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
        read_bytes = FRAME_BYTES * 2
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None and process.stderr is not None
    previous = None
    previous_ms = 0
    chosen: list[int] = []
    last_chosen_frame = None
    last_chosen_ms = 0
    first_frame = None
    previous_mask = first_mask = last_chosen_mask = None
    def visible_difference(left, right, left_mask, right_mask):
        difference = cv2.absdiff(left, right) > 25
        if left_mask is None: return float(np.mean(difference))
        visible = left_mask & right_mask
        # No common visible area is not proof of sameness: conservatively retain evidence.
        return float(np.mean(difference[visible])) if visible.any() else 1.0
    index = 0
    try:
        while frame_bytes := process.stdout.read(read_bytes):
            if len(frame_bytes) != read_bytes:
                raise RuntimeError("FFmpeg returned an incomplete preview frame")
            frame = np.frombuffer(frame_bytes[:FRAME_BYTES], dtype=np.uint8).reshape(PREVIEW_HEIGHT, PREVIEW_WIDTH)
            if ignore_region:
                mask = np.frombuffer(frame_bytes[FRAME_BYTES:], dtype=np.uint8).reshape(PREVIEW_HEIGHT, PREVIEW_WIDTH) >= 254
                if not mask.any():
                    raise ValueError("ignored_region_leaves_no_visible_pixels")
            time_ms = index * sample_seconds * 1000
            if first_frame is None:
                first_frame = frame.copy()
                first_mask = mask.copy() if mask is not None else None
            if previous is not None:
                changed_fraction = visible_difference(previous, frame, previous_mask, mask)
                if changed_fraction > page_change_fraction:
                    if not chosen or chosen[-1] != previous_ms:
                        chosen.append(previous_ms)
                    last_chosen_frame = previous.copy()
                    last_chosen_mask = previous_mask.copy() if previous_mask is not None else None
                    last_chosen_ms = previous_ms
                elif time_ms - last_chosen_ms >= MAX_PROGRESS_INTERVAL_MS:
                    baseline = last_chosen_frame if last_chosen_frame is not None else first_frame
                    progress = visible_difference(baseline, previous, last_chosen_mask if last_chosen_frame is not None else first_mask, previous_mask)
                    if progress > PROGRESS_FRACTION:
                        chosen.append(previous_ms)
                        last_chosen_frame = previous.copy()
                        last_chosen_mask = previous_mask.copy() if previous_mask is not None else None
                        last_chosen_ms = previous_ms
            previous = frame.copy()
            previous_mask = mask.copy() if mask is not None else None
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


def _frames_at(path: Path, times_ms: list[int]):
    """Seek each requested time, batching up to eight outputs per FFmpeg process.

    Separate fast-seeking inputs avoid decoding the entire interval between distant times.
    Eight is a resource batch size, not a limit on how many frames may be requested.
    """
    times = list(dict.fromkeys(times_ms))
    with tempfile.TemporaryDirectory(prefix="videostudy-frames-") as directory:
        for start in range(0, len(times), 8):
            batch = times[start:start + 8]
            command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
            for t in batch:
                command.extend(["-threads", "1", "-ss", f"{t / 1000:.3f}", "-i", str(path)])
            outputs = [Path(directory) / f"{i}.jpg" for i in range(len(batch))]
            for i, output in enumerate(outputs):
                command.extend(["-map", f"{i}:v:0", "-frames:v", "1", "-threads", "1",
                                "-q:v", "2", str(output)])
            subprocess.run(command, capture_output=True, check=True)
            for t, output in zip(batch, outputs):
                frame = cv2.imread(str(output))
                if frame is None:
                    raise RuntimeError(f"Could not decode video frame at {t} ms")
                yield t, frame


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
        device=os.environ.get("OCR_DEVICE", "cpu"),
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


def _frame_checkpoint(path: Path, keyframe_dir: Path | None):
    if keyframe_dir is None:
        return None
    metadata = path.stat()
    return Checkpoints(keyframe_dir / '.analysis', {
        'media': str(path.resolve()), 'size': metadata.st_size, 'mtime': metadata.st_mtime_ns,
        'ocr': OCR_MODEL_ID, 'device': os.environ.get('OCR_DEVICE', 'cpu'),
    })


def _save_keyframe(frame: np.ndarray, keyframe_dir: Path, time_ms: int) -> None:
    keyframe_dir.mkdir(parents=True, exist_ok=True)
    encoded, image = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not encoded:
        raise RuntimeError(f"Could not encode video frame at {time_ms} ms")
    temporary = keyframe_dir / f"{time_ms}.jpg.tmp"
    temporary.write_bytes(image.tobytes())
    temporary.replace(keyframe_dir / f"{time_ms}.jpg")


def recognize_in_region(frame,setting,time_ms,recognize):
    # Keep legacy full-frame OCR unchanged; analysis regions opt into masked OCR.
    if setting and 'analysisRegion' in setting:
        return recognize(prepare_image(frame,setting,time_ms))
    return recognize(frame)


def analyze_visuals(path: Path, recognize: Callable[[np.ndarray], list[dict]] | None = None,
                    keyframe_dir: Path | None = None,
                    page_change_fraction: float = PAGE_CHANGE_FRACTION,
                    sample_seconds: int = SAMPLE_SECONDS, ignore_region: dict | None = None) -> list[dict]:
    """Return OCR from representative frames; audio-only input returns no visual evidence."""
    if not _has_video(path):
        return []
    recognize = recognize or _recognize
    evidence = []
    checkpoint = _frame_checkpoint(path, keyframe_dir)
    for time_ms, frame in _frames_at(path, _candidate_times(path, page_change_fraction, sample_seconds, ignore_region)):
        if keyframe_dir is not None:
            _save_keyframe(frame, keyframe_dir, time_ms)
        blocks = checkpoint.run(f'ocrFrame:{time_ms}', {'regions':ignore_region}, lambda: recognize_in_region(frame,ignore_region,time_ms,recognize)) if checkpoint else recognize_in_region(frame,ignore_region,time_ms,recognize)
        evidence.append({"frameTimeMs": time_ms, "ocrBlocks": blocks})
    return evidence


def _serve_visual_requests(connection) -> None:
    path = None
    keyframe_dir = None
    page_change_fraction = PAGE_CHANGE_FRACTION
    sample_seconds = SAMPLE_SECONDS
    ignore_region = None
    checkpoint = None
    try:
        while request := connection.recv():
            try:
                if request["op"] == "bind":
                    path = Path(request["mediaPath"])
                    keyframe_dir = Path(request["keyframePath"]) if request["keyframePath"] else None
                    page_change_fraction = request["pageChangeFraction"]
                    sample_seconds = request["sampleSeconds"]
                    ignore_region = normalize_region(request.get("ignoredRegion"))
                    checkpoint = _frame_checkpoint(path, keyframe_dir)
                    response = None
                elif request["op"] == "analyze":
                    response = analyze_visuals(path, keyframe_dir=keyframe_dir,
                                               page_change_fraction=page_change_fraction, sample_seconds=sample_seconds, ignore_region=ignore_region)
                elif request["op"] == "capture":
                    frame = _frame_at(path, request["timeMs"])
                    if keyframe_dir is not None:
                        _save_keyframe(frame, keyframe_dir, request["timeMs"])
                    response = checkpoint.run(f'ocrFrame:{request["timeMs"]}', {'regions':ignore_region}, lambda: recognize_in_region(frame,ignore_region,request['timeMs'],_recognize)) if checkpoint else recognize_in_region(frame,ignore_region,request['timeMs'],_recognize)
                elif request["op"] == "capture_batch":
                    response = []
                    for time_ms, frame in _frames_at(path, request["timesMs"]):
                        if keyframe_dir is not None:
                            _save_keyframe(frame, keyframe_dir, time_ms)
                        blocks = checkpoint.run(f'ocrFrame:{time_ms}', {'regions':ignore_region}, lambda: recognize_in_region(frame,ignore_region,time_ms,_recognize)) if checkpoint else recognize_in_region(frame,ignore_region,time_ms,_recognize)
                        response.append({"frameTimeMs": time_ms, "ocrBlocks": blocks})
                else:
                    raise ValueError("Unknown visual worker operation")
                connection.send({"ok": True, "value": response})
            except Exception as error:
                connection.send({"ok": False, "error": f"{type(error).__name__}: {error}"})
    except EOFError:
        pass
    finally:
        connection.close()


_worker_lock = threading.Lock()
_shared_connection = None
_shared_process = None


def _stop_shared_worker():
    global _shared_connection, _shared_process
    if _shared_connection is not None:
        _shared_connection.close()
    if _shared_process is not None:
        _shared_process.join(timeout=5)
        if _shared_process.is_alive():
            _shared_process.terminate()
            _shared_process.join(timeout=5)
    _shared_connection = _shared_process = None


def shutdown_visual_worker():
    """Release the service-owned OCR process on service shutdown."""
    with _worker_lock:
        _stop_shared_worker()


atexit.register(shutdown_visual_worker)


class VisualOcrWorker:
    """Lease one persistent OCR process; serialize media sessions and pipe requests."""

    def __init__(self, path: Path, keyframe_dir: Path | None = None,
                 page_change_fraction: float = PAGE_CHANGE_FRACTION, sample_seconds: int = SAMPLE_SECONDS,
                 ignore_region: dict | None = None):
        if sample_seconds not in (2, 3, 4):
            raise ValueError("sample_seconds must be 2, 3 or 4")
        ignore_region = normalize_region(ignore_region)
        global _shared_connection, _shared_process
        self._closed = False
        self._request_lock = threading.Lock()
        _worker_lock.acquire()
        try:
            if _shared_process is None or not _shared_process.is_alive():
                _stop_shared_worker()
                context = multiprocessing.get_context("spawn")
                _shared_connection, child = context.Pipe()
                _shared_process = context.Process(target=_serve_visual_requests, args=(child,), daemon=True)
                _shared_process.start()
                child.close()
            self.connection, self.process = _shared_connection, _shared_process
            self._request("bind", mediaPath=str(path),
                          keyframePath=str(keyframe_dir) if keyframe_dir else None,
                          pageChangeFraction=page_change_fraction, sampleSeconds=sample_seconds, ignoredRegion=ignore_region)
        except BaseException:
            _stop_shared_worker()
            self._closed = True
            _worker_lock.release()
            raise

    def _request(self, operation: str, **kwargs):
        with self._request_lock:
            if self._closed:
                raise RuntimeError("Visual worker lease is closed")
            try:
                self.connection.send({"op": operation, **kwargs})
                if not self.connection.poll(30 * 60):
                    raise TimeoutError("Visual OCR worker timed out")
                answer = self.connection.recv()
            except (EOFError, OSError, TimeoutError):
                _stop_shared_worker()
                raise
            if not answer["ok"]:
                raise RuntimeError(answer["error"])
            return answer["value"]

    def analyze(self) -> list[dict]:
        return self._request("analyze")

    def capture(self, time_ms: int) -> list[dict]:
        return self._request("capture", timeMs=time_ms)

    def capture_batch(self, times_ms: list[int]) -> list[dict]:
        if not times_ms:
            return []
        return self._request("capture_batch", timesMs=list(dict.fromkeys(times_ms)))

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            _worker_lock.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
