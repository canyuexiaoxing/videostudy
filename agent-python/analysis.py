"""Run all media-analysis stages while the uploaded file is still available."""

import os
from pathlib import Path
import shutil
import subprocess
from uuid import UUID

from agent_review import review_visual_coverage
from page_understanding import analyze_page
from slide_grouping import GROUPING_VERSION, group_pages
from transcription import transcribe_file
from visual_evidence import OCR_MODEL_ID, VisualOcrWorker


def media_duration_ms(path: Path) -> int:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return round(float(result.stdout.strip()) * 1000)


def analyze_file(file_id: str, visual_analysis_mode: str = "both",
                 coarse_change_percent: float = 2.0) -> dict:
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
    try:
        transcript = transcribe_file(file_id)
        with VisualOcrWorker(media_path, keyframe_dir,
                             page_change_fraction=coarse_change_percent / 100) as visual_worker:
            visuals = visual_worker.analyze()
            visuals, review = review_visual_coverage(
                duration_ms=media_duration_ms(media_path),
                segments=transcript["segments"],
                visuals=visuals,
                capture=visual_worker.capture,
            )
        page_groups, transition_times = group_pages(visuals, keyframe_dir, transcript["segments"])
        if page_groups:
            by_time = {frame["frameTimeMs"]: frame for frame in visuals}
            page_groups = [analyze_page(page, page_groups, by_time, keyframe_dir,
                                        transcript["segments"], visual_analysis_mode)
                           for page in page_groups]
        return {
            "language": transcript["language"],
            "segments": transcript["segments"],
            "visualEvidence": visuals,
            "pageGroups": page_groups,
            "transitionFrameTimesMs": transition_times,
            "visualAnalysisMode": visual_analysis_mode,
            "coarseChangePercent": coarse_change_percent,
            "groupingVersion": GROUPING_VERSION,
            "ocrModelId": OCR_MODEL_ID if visuals else None,
            "imageModelId": os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
                            if visual_analysis_mode == "both" and page_groups else None,
            "review": review,
        }
    except Exception:
        shutil.rmtree(keyframe_dir, ignore_errors=True)
        raise
