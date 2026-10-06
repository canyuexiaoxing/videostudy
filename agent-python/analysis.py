"""Run all media-analysis stages while the uploaded file is still available."""

import os
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from uuid import UUID

from agent_review import review_visual_coverage
from mind_map import build_mind_map
from page_understanding import analyze_page
from slide_grouping import GROUPING_VERSION, group_pages
from transcription import transcribe_file
from visual_evidence import OCR_MODEL_ID, VisualOcrWorker
from checkpoints import Checkpoints
from mind_map import PROMPT_VERSION as MAP_VERSION
from page_understanding import PAGE_PROMPT_VERSION
from agent_review import PROMPT_VERSION as REVIEW_VERSION
from subtitle_delivery import publish_subtitle_source
from overview import safe_overview
import logging


def media_duration_ms(path: Path) -> int:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return round(float(result.stdout.strip()) * 1000)


def analyze_file(file_id: str, visual_analysis_mode: str = "both",
                 coarse_change_percent: float = 2.0,
                 subtitle_callback_token: str | None = None) -> dict:
    UUID(file_id)
    if visual_analysis_mode not in ("ocr_only", "both"):
        raise ValueError("visualAnalysisMode must be ocr_only or both")
    if coarse_change_percent not in (0.5, 1.0, 2.0, 3.0):
        raise ValueError("coarseChangePercent must be 0.5, 1, 2 or 3")
    media_root = Path(os.environ.get("MEDIA_TEMP_DIR", "../.local/uploads")).resolve()
    media_path = media_root / file_id
    if not media_path.is_file():
        raise FileNotFoundError("uploaded media not found")

    keyframe_dir = Path(os.environ.get("KEYFRAME_DIR", "../.local/keyframes")).resolve() / file_id
    started = perf_counter()
    timings = {}
    metadata = media_path.stat()
    checkpoint = Checkpoints(keyframe_dir / '.analysis', {
        'size': metadata.st_size, 'mtime': metadata.st_mtime_ns,
        'mode': visual_analysis_mode, 'threshold': coarse_change_percent,
        'ocr': OCR_MODEL_ID, 'ocrDevice': os.environ.get('OCR_DEVICE', 'cpu'),
        'speech': 'faster-whisper-base:beam5:vad:int8',
        'model': os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash'),
        'endpoint': os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
        'prompts': [MAP_VERSION, PAGE_PROMPT_VERSION, REVIEW_VERSION, GROUPING_VERSION],
    })
    def cached(stage, inputs, function, accept=lambda value: True):
        return checkpoint.run(stage, inputs, function, accept)
    def timed(name, function, *args):
        before = perf_counter()
        value = function(*args)
        timings[name] = round((perf_counter() - before) * 1000)
        return value
    try:
        with VisualOcrWorker(media_path, keyframe_dir,
                             page_change_fraction=coarse_change_percent / 100) as visual_worker:
            if os.environ.get("MEDIA_PARALLEL", "1") == "1":
                with ThreadPoolExecutor(max_workers=2) as pool:
                    speech_job = pool.submit(timed, "transcription", cached, 'transcription', {},
                                             lambda: transcribe_file(file_id))
                    visual_job = pool.submit(timed, "visualOcr", cached, 'visualOcr', {}, visual_worker.analyze)
                    transcript, visuals = speech_job.result(), visual_job.result()
            else:
                transcript = timed("transcription", cached, 'transcription', {}, lambda: transcribe_file(file_id))
                visuals = timed("visualOcr", cached, 'visualOcr', {}, visual_worker.analyze)
            before = perf_counter()
            def coverage():
                return review_visual_coverage(
                    duration_ms=media_duration_ms(media_path),
                    segments=transcript["segments"],
                    visuals=visuals,
                    capture=visual_worker.capture,
                    capture_batch=visual_worker.capture_batch,
                )
            visuals, review = cached('coverageReview', {'speech': transcript, 'visuals': visuals}, coverage,
                accept=lambda value: value[1].get('status') in ('completed', 'not_applicable'))
            timings["coverageReview"] = round((perf_counter() - before) * 1000)
        page_groups, transition_times = timed("pageGrouping", cached, 'pageGrouping',
            {'visuals': visuals, 'speech': transcript['segments']},
            lambda: group_pages(visuals, keyframe_dir, transcript['segments']))
        before = perf_counter()
        if page_groups:
            by_time = {frame["frameTimeMs"]: frame for frame in visuals}
            with ThreadPoolExecutor(max_workers=max(1, int(os.environ.get("PAGE_CONCURRENCY", "5")))) as pool:
                # map preserves order even when later pages finish first.
                page_groups = list(pool.map(lambda page: cached(f'page:{page["pageIndex"]}',
                    {'page': page, 'pages': page_groups, 'speech': transcript['segments']},
                    lambda: analyze_page(page, page_groups, by_time, keyframe_dir,
                                        transcript['segments'], visual_analysis_mode),
                    accept=lambda result: (result.get('imageAnalysis') or result.get('textAnalysis') or {}).get('status') != 'failed'),
                    page_groups))
        timings["pageUnderstanding"] = round((perf_counter() - before) * 1000)
        if subtitle_callback_token:
            try:
                publish_subtitle_source(file_id, subtitle_callback_token, transcript['language'],
                                        transcript['segments'], page_groups)
            except Exception as error:
                logging.getLogger(__name__).warning('Unable to schedule subtitle source: %s',
                                                    type(error).__name__)
        with ThreadPoolExecutor(max_workers=2) as pool:
            overview_job=pool.submit(timed,"overview",cached,'overview',
                {'speech':transcript['segments'],'pages':page_groups},
                lambda:safe_overview(transcript['segments'],page_groups),
                lambda result:result.get('status') in ('completed','empty'))
            map_job=pool.submit(timed,"mindMap",lambda:build_mind_map(transcript['segments'],page_groups,checkpoint=checkpoint))
            mind_map=map_job.result()
            overview=overview_job.result()
        timings["total"] = round((perf_counter() - started) * 1000)
        return {
            "language": transcript["language"],
            "segments": transcript["segments"],
            "visualEvidence": visuals,
            "pageGroups": page_groups,
            "mindMap": mind_map,
            "overview": overview,
            "transitionFrameTimesMs": transition_times,
            "visualAnalysisMode": visual_analysis_mode,
            "coarseChangePercent": coarse_change_percent,
            "groupingVersion": GROUPING_VERSION,
            "ocrModelId": OCR_MODEL_ID if visuals else None,
            "imageModelId": os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
                            if visual_analysis_mode == "both" and page_groups else None,
            "review": review,
            "stageTimingsMs": timings,
            "reusedCheckpoints": checkpoint.hits,
        }
    except Exception:
        # Keep task-local evidence/checkpoints for bounded automatic retries.
        # Java removes this directory when the task is deleted or expires.
        raise
