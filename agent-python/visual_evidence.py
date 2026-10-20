"""Select changed video frames before running OCR; keep timestamps in milliseconds."""

from functools import lru_cache
import atexit
import multiprocessing
import tempfile
import threading
from pathlib import Path
import subprocess
from typing import Callable
from time import perf_counter
import sys
from uuid import uuid4
from frame_stream import FRAME_PIPELINE_VERSION
from concurrent.futures import CancelledError
from person_selection import settings as person_settings, PersonMaskProcess, VisibilitySelector, AdjacentPairSelector
from model_diagnostics import record_event

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
PAGE_CHANGE_FRACTION = 0.03
PROGRESS_FRACTION = 0.001
MAX_PROGRESS_INTERVAL_MS = 30_000


def _has_video(path: Path) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),
    )
    return bool(result.stdout.strip())


def _candidate_times(path: Path, page_change_fraction: float = PAGE_CHANGE_FRACTION,
                     sample_seconds: int = SAMPLE_SECONDS, ignore_region: dict | None = None,
                     person_selection_mode: str | None = None, *, _sample_source=None, _selected=None, _check=None, _mask_selected=None) -> list[int]:
    if sample_seconds not in (2, 3, 4):
        raise ValueError("sample_seconds must be 2, 3 or 4")
    person_config = person_settings(person_selection_mode)
    person_mode = person_config['mode']
    strategy = person_config.get('strategy','history')
    use_person = person_mode != 'off'
    cancel_root = Path(os.environ.get('KEYFRAME_DIR','../.local/keyframes')) / path.name / '.analysis'
    run_file = cancel_root / 'active-run.json'
    initial_run = run_file.read_bytes() if use_person and run_file.is_file() else None
    def check_cancel():
        if _check is not None:_check()
        if not use_person:return
        if (cancel_root/'cancel.json').exists():raise CancelledError('analysis_cancelled')
        if initial_run is not None:
            try:current=run_file.read_bytes()
            except OSError:raise CancelledError('analysis_cancelled')
            if current!=initial_run:raise CancelledError('analysis_cancelled')
    check_cancel()
    pixel_format = 'rgb24' if use_person else 'gray'
    preview_bytes = FRAME_BYTES * (3 if use_person else 1)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-vf", f"fps=1/{sample_seconds},scale={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:force_original_aspect_ratio=decrease,"
               f"pad={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format={pixel_format}",
        "-f", "rawvideo", "-pix_fmt", pixel_format, "pipe:1",
    ]
    ignore_region = normalize_region(ignore_region)
    read_bytes = preview_bytes
    mask = None
    if ignore_region:
        included = ignore_region.get('analysisRegion') if 'analysisRegion' in ignore_region else None
        excluded = ignore_region.get('ignoredRegion') if 'analysisRegion' in ignore_region else ignore_region
        def timed_nodes(value):return value['nodes'] if value and 'nodes' in value else [{'timeMs':0,'region':value}]
        groups=[(timed_nodes(included),True),(timed_nodes(excluded),False)]
        geometry = f"scale={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:force_original_aspect_ratio=decrease,pad={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format={pixel_format}"
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
                   f"[m]{mask_filters}[mask];[p][mask]vstack,format={pixel_format}[out]")
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                   "-filter_complex", filters, "-map", "[out]", "-f", "rawvideo", "-pix_fmt", pixel_format, "pipe:1"]
        read_bytes = preview_bytes * 2
    process = None
    previous = None
    previous_ms = 0
    chosen: list[int] = []
    originals = {}
    selected_masks = {}
    def choose(ms):
        if chosen and ms<=chosen[-1]:return
        if _mask_selected is not None:_mask_selected(ms, selected_masks.get(ms))
        if _selected is not None:_selected(ms, originals[ms])
        chosen.append(ms)
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
    person_worker = None
    selector = None
    person_started = perf_counter()
    model_elapsed = 0
    person_frames = 0
    fallback = False
    completed_sampling = False
    task = path.name
    if use_person:
        record_event('stage_started', task, operation='person_selection',strategy=strategy, stage='model_load', model='yolo26n-seg')
        try:
            # Resolve dynamically so tests can substitute deterministic masks without Torch.
            from person_selection import PersonMaskLease
            person_worker = (PersonMaskLease() if person_selection_mode is None else PersonMaskLease(person_selection_mode)).__enter__()
            selector = (AdjacentPairSelector if strategy=='adjacent' else VisibilitySelector)(page_change_fraction)
            record_event('stage_completed', task, operation='person_selection',strategy=strategy, stage='model_load', device=person_worker.device, elapsed_ms=round((perf_counter()-person_started)*1000))
        except Exception as error:
            fallback = True
            record_event('stage_failed', task, operation='person_selection',strategy=strategy, stage='fallback', reason=getattr(error,'reason','person_runtime_unavailable'), error_type=getattr(error,'error_type',type(error).__name__))
    def records():
        nonlocal process, mask
        if _sample_source is not None:
            from frame_stream import preview
            for ms,original in _sample_source:
                check_cancel()
                gray,rgb,allowed=preview(original,ignore_region,ms,use_person)
                yield ms,gray,rgb,allowed,original
            return
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        assert process.stdout is not None and process.stderr is not None
        while frame_bytes := process.stdout.read(read_bytes):
            if len(frame_bytes) != read_bytes:
                raise RuntimeError("FFmpeg returned an incomplete preview frame")
            preview = np.frombuffer(frame_bytes[:preview_bytes], dtype=np.uint8)
            if use_person:
                rgb = preview.reshape(PREVIEW_HEIGHT, PREVIEW_WIDTH, 3)
                frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            else:
                frame = preview.reshape(PREVIEW_HEIGHT, PREVIEW_WIDTH)
            if ignore_region:
                mask_pixels = np.frombuffer(frame_bytes[preview_bytes:], dtype=np.uint8)
                mask = (mask_pixels.reshape(PREVIEW_HEIGHT, PREVIEW_WIDTH, 3)[:,:,0] if use_person else mask_pixels.reshape(PREVIEW_HEIGHT, PREVIEW_WIDTH)) >= 254
                if not mask.any():
                    raise ValueError("ignored_region_leaves_no_visible_pixels")
            time_ms = index * sample_seconds * 1000
            yield time_ms,frame,rgb if use_person else None,mask,None
        error = process.stderr.read().decode(errors="replace")
        if process.wait() != 0:
            raise RuntimeError(f"FFmpeg frame sampling failed: {error.strip()}")
    try:
        for time_ms,frame,rgb,mask,original in records():
            if original is not None:
                keep_times={previous_ms, selector.pending_time if selector is not None else None}
                originals={t:f for t,f in originals.items() if t in keep_times}
                selected_masks={t:m for t,m in selected_masks.items() if t in keep_times}
                originals[time_ms]=original
            check_cancel()
            if person_worker is not None:
                try:
                    before = perf_counter()
                    person_mask = person_worker.predict(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
                    model_elapsed += round((perf_counter()-before)*1000)
                    person_frames += int(person_mask.any())
                    if _mask_selected is not None:selected_masks[time_ms]=person_mask.copy()
                    keep = selector.observe(frame, mask if mask is not None else np.ones_like(frame,dtype=bool), person_mask, time_ms)
                    if keep:
                        if selector.preserve_time is not None and (not chosen or selector.preserve_time>chosen[-1]):choose(selector.preserve_time)
                        choose(time_ms)
                    previous = frame.copy();previous_ms = time_ms;index += 1
                    continue
                except CancelledError:
                    raise
                except Exception as error:
                    person_worker.invalidate();person_worker = None;fallback = True
                    # Unknown frames are never silently discarded after a failed detector.
                    if not chosen or chosen[-1] != time_ms:choose(time_ms)
                    previous = first_frame = last_chosen_frame = None
                    previous_mask = first_mask = last_chosen_mask = None
                    record_event('stage_failed',task,operation='person_selection',strategy=strategy,stage='fallback',reason=getattr(error,'reason','person_inference_failed'),error_type=getattr(error,'error_type',type(error).__name__))
            if first_frame is None:
                first_frame = frame.copy()
                first_mask = mask.copy() if mask is not None else None
            if previous is not None:
                changed_fraction = visible_difference(previous, frame, previous_mask, mask)
                if changed_fraction > page_change_fraction:
                    if not chosen or chosen[-1] != previous_ms:
                        choose(previous_ms)
                    last_chosen_frame = previous.copy()
                    last_chosen_mask = previous_mask.copy() if previous_mask is not None else None
                    last_chosen_ms = previous_ms
                elif time_ms - last_chosen_ms >= MAX_PROGRESS_INTERVAL_MS:
                    baseline = last_chosen_frame if last_chosen_frame is not None else first_frame
                    progress = visible_difference(baseline, previous, last_chosen_mask if last_chosen_frame is not None else first_mask, previous_mask)
                    if progress > PROGRESS_FRACTION:
                        choose(previous_ms)
                        last_chosen_frame = previous.copy()
                        last_chosen_mask = previous_mask.copy() if previous_mask is not None else None
                        last_chosen_ms = previous_ms
            previous = frame.copy()
            previous_mask = mask.copy() if mask is not None else None
            previous_ms = time_ms
            index += 1
        if selector is not None and not fallback and selector.pending_time is not None and (not chosen or selector.pending_time>chosen[-1]):choose(selector.pending_time)
        completed_sampling = True
    finally:
        if person_worker is not None:
            if sys.exc_info()[0] is not None:person_worker.invalidate()
            else:person_worker.close()
        if use_person:
            record_event('stage_completed',task,operation='person_selection',strategy=strategy,stage='selection',status='cancelled' if isinstance(sys.exc_info()[1],CancelledError) else 'completed' if completed_sampling and not fallback else 'failed',image_count=index,accepted_count=len(chosen)+int(previous is not None and (not chosen or chosen[-1]!=previous_ms)),person_frames=person_frames,uncertain_frames=selector.uncertain_frames if selector else 0,reveal_frames=selector.reveal_frames if selector else 0,inference_ms=model_elapsed,elapsed_ms=round((perf_counter()-person_started)*1000))
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()
    if previous is not None and (not chosen or chosen[-1] != previous_ms):
        choose(previous_ms)
    return chosen


def _frame_at(path: Path, time_ms: int, *, _check=lambda:None, _with_time=False) -> np.ndarray:
    from contextlib import closing
    from frame_stream import accurate_frames
    with closing(accurate_frames(path,[time_ms],check=_check)) as frames:
        actual,frame=next(frames)
        return (actual,frame) if _with_time else frame


def _frames_at(path: Path, times_ms: list[int], *, _check=lambda:None, _with_request=False):
    from frame_stream import accurate_frames
    yield from accurate_frames(path,times_ms,check=_check,with_request=_with_request)


@lru_cache(maxsize=1)
def _ocr_model(device=None):
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
        device=device or os.environ.get("OCR_DEVICE", "cpu"),
    )


def _recognize(frame: np.ndarray) -> list[dict]:
    from native_devices import allow_cpu_fallback,record_fallback
    try:
        result = _ocr_model().predict(frame)[0].json["res"]
    except Exception as error:
        if not allow_cpu_fallback(error,os.environ.get('OCR_DEVICE','cpu')):raise
        record_fallback('ocr',error)
        _ocr_model.cache_clear()
        os.environ['OCR_DEVICE']='cpu'
        result = _ocr_model('cpu').predict(frame)[0].json["res"]
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
        'ocr': OCR_MODEL_ID, 'device': os.environ.get('OCR_DEVICE', 'cpu'), 'framePipeline': FRAME_PIPELINE_VERSION,
    })


def _save_keyframe(frame: np.ndarray, keyframe_dir: Path, time_ms: int, *, _check=lambda:None) -> None:
    keyframe_dir.mkdir(parents=True, exist_ok=True)
    encoded, image = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not encoded:
        raise RuntimeError(f"Could not encode video frame at {time_ms} ms")
    temporary = keyframe_dir / f"{time_ms}.{uuid4().hex}.jpg.tmp"
    try:
        _check()
        temporary.write_bytes(image.tobytes())
        _check()
        temporary.replace(keyframe_dir / f"{time_ms}.jpg")
    finally:temporary.unlink(missing_ok=True)


def recognize_in_region(frame,setting,time_ms,recognize):
    # Keep legacy full-frame OCR unchanged; analysis regions opt into masked OCR.
    if setting and 'analysisRegion' in setting:
        return recognize(prepare_image(frame,setting,time_ms))
    return recognize(frame)


def analyze_visuals(path: Path, recognize: Callable[[np.ndarray], list[dict]] | None = None,
                    keyframe_dir: Path | None = None,
                    page_change_fraction: float = PAGE_CHANGE_FRACTION,
                    sample_seconds: int = SAMPLE_SECONDS, ignore_region: dict | None = None,
                    on_frame: Callable[[dict], None] | None = None, person_selection_mode: str | None = None) -> list[dict]:
    """Return OCR from representative frames; audio-only input returns no visual evidence."""
    if not _has_video(path):
        return []
    recognize = recognize or _recognize
    evidence = []
    checkpoint = _frame_checkpoint(path, keyframe_dir)
    from frame_stream import SavedFramePipeline
    with SavedFramePipeline(path,keyframe_dir,threshold=page_change_fraction,sample_seconds=sample_seconds,
            regions=ignore_region,person_mode=person_selection_mode,save=_save_keyframe) as stream:
        for time_ms, frame in stream:
            blocks = checkpoint.run(f'ocrFrame:{time_ms}', {'regions':ignore_region}, lambda: recognize_in_region(frame,ignore_region,time_ms,recognize)) if checkpoint else recognize_in_region(frame,ignore_region,time_ms,recognize)
            stream.check(force=True)
            item = {"frameTimeMs": time_ms, "ocrBlocks": blocks}
            evidence.append(item)
            if on_frame is not None and keyframe_dir is not None:
                from copy import deepcopy
                on_frame(deepcopy(item))
    return evidence


def _serve_visual_requests(connection) -> None:
    path = None
    keyframe_dir = None
    page_change_fraction = PAGE_CHANGE_FRACTION
    sample_seconds = SAMPLE_SECONDS
    ignore_region = None
    person_selection_mode = None
    checkpoint = None
    from frame_stream import FrameRunGuard
    capture_guard = FrameRunGuard(None)
    try:
        while request := connection.recv():
            try:
                if request["op"] == "bind":
                    path = Path(request["mediaPath"])
                    keyframe_dir = Path(request["keyframePath"]) if request["keyframePath"] else None
                    page_change_fraction = request["pageChangeFraction"]
                    sample_seconds = request["sampleSeconds"]
                    ignore_region = normalize_region(request.get("ignoredRegion"))
                    person_selection_mode = request.get("personSelectionMode")
                    person_settings(person_selection_mode)
                    checkpoint = _frame_checkpoint(path, keyframe_dir)
                    capture_guard = FrameRunGuard(keyframe_dir / '.analysis' if keyframe_dir else None)
                    response = None
                elif request["op"] == "analyze":
                    response = analyze_visuals(path, keyframe_dir=keyframe_dir,
                                               page_change_fraction=page_change_fraction, sample_seconds=sample_seconds, ignore_region=ignore_region,
                                               person_selection_mode=person_selection_mode,
                                               on_frame=(lambda frame: connection.send({"event": "frame", "value": frame}))
                                               if request.get("streamFrames") else None)
                elif request["op"] == "capture":
                    actual_ms,frame = _frame_at(path, request["timeMs"], _check=capture_guard.poll, _with_time=True)
                    if keyframe_dir is not None:
                        _save_keyframe(frame, keyframe_dir, actual_ms, _check=capture_guard.check)
                    response = checkpoint.run(f'ocrFrame:{actual_ms}', {'regions':ignore_region}, lambda: recognize_in_region(frame,ignore_region,actual_ms,_recognize)) if checkpoint else recognize_in_region(frame,ignore_region,actual_ms,_recognize)
                elif request["op"] == "capture_batch":
                    response = []
                    for requested_ms,time_ms,frame in _frames_at(path, request["timesMs"], _check=capture_guard.poll, _with_request=True):
                        if keyframe_dir is not None:
                            _save_keyframe(frame, keyframe_dir, time_ms, _check=capture_guard.check)
                        blocks = checkpoint.run(f'ocrFrame:{time_ms}', {'regions':ignore_region}, lambda: recognize_in_region(frame,ignore_region,time_ms,_recognize)) if checkpoint else recognize_in_region(frame,ignore_region,time_ms,_recognize)
                        capture_guard.check()
                        response.append({"frameTimeMs": time_ms, "requestedTimeMs":requested_ms, "ocrBlocks": blocks})
                else:
                    raise ValueError("Unknown visual worker operation")
                if request['op'] in ('capture','capture_batch'):capture_guard.check()
                connection.send({"ok": True, "value": response})
            except Exception as error:
                if request.get('op') in ('capture','capture_batch'):
                    record_event('stage_failed',keyframe_dir.name if keyframe_dir else 'unbound',operation='frame_pipeline',stage='capture',error_type=type(error).__name__,reason=str(error))
                connection.send({"ok": False, "error": f"{type(error).__name__}: {error}"})
    except EOFError:
        pass
    finally:
        from person_selection import shutdown_person_worker
        shutdown_person_worker()
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
                 ignore_region: dict | None = None, person_selection_mode: str | None = None):
        if sample_seconds not in (2, 3, 4):
            raise ValueError("sample_seconds must be 2, 3 or 4")
        ignore_region = normalize_region(ignore_region)
        person_settings(person_selection_mode)
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
                          pageChangeFraction=page_change_fraction, sampleSeconds=sample_seconds, ignoredRegion=ignore_region, personSelectionMode=person_selection_mode)
        except BaseException:
            _stop_shared_worker()
            self._closed = True
            _worker_lock.release()
            raise

    def _request(self, operation: str, on_frame=None, **kwargs):
        with self._request_lock:
            if self._closed:
                raise RuntimeError("Visual worker lease is closed")
            try:
                self.connection.send({"op": operation, **kwargs})
                while True:
                    if not self.connection.poll(30 * 60):
                        raise TimeoutError("Visual OCR worker timed out")
                    answer = self.connection.recv()
                    if answer.get("event") == "frame":
                        if on_frame is not None:
                            on_frame(answer["value"])
                        continue
                    break
            except BaseException:
                # A callback failure or cancellation can leave frame/final messages
                # unread. Retire this pipe before any other media session uses it.
                _stop_shared_worker()
                raise
            if not answer["ok"]:
                raise RuntimeError(answer["error"])
            return answer["value"]

    def analyze(self, on_frame=None) -> list[dict]:
        return self._request("analyze", on_frame=on_frame, streamFrames=on_frame is not None)

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


