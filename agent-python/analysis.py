"""Run all media-analysis stages while the uploaded file is still available."""

import os
from pathlib import Path
import shutil
import subprocess
from uuid import UUID

from agent_review import review_visual_coverage
from image_understanding import describe_frames
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


def analyze_file(file_id: str, visual_analysis_mode: str = "both") -> dict:
    UUID(file_id)
    if visual_analysis_mode not in ("ocr_only", "both"):
        raise ValueError("visualAnalysisMode must be ocr_only or both")
    media_root = Path(os.environ.get("MEDIA_TEMP_DIR", "../.local/uploads")).resolve()
    media_path = media_root / file_id
    if not media_path.is_file():
        raise FileNotFoundError("uploaded media not found")

    keyframe_dir = Path(os.environ.get("KEYFRAME_DIR", "../.local/keyframes")).resolve() / file_id
    try:
        transcript = transcribe_file(file_id)
        with VisualOcrWorker(media_path, keyframe_dir) as visual_worker:
            visuals = visual_worker.analyze()
            visuals, review = review_visual_coverage(
                duration_ms=media_duration_ms(media_path),
                segments=transcript["segments"],
                visuals=visuals,
                capture=visual_worker.capture,
            )
        page_groups, transition_times = group_pages(visuals, keyframe_dir, transcript["segments"])
        if visual_analysis_mode == "both" and page_groups:
            by_time = {frame["frameTimeMs"]: frame for frame in visuals}
            for page in page_groups:
                representatives = [by_time[time] for time in page["representativeFrameTimesMs"]]
                understood = describe_frames(representatives, keyframe_dir)
                analyses = [frame["imageAnalysis"] for frame in understood]
                if len(analyses) == 1:
                    page["imageAnalysis"] = analyses[0]
                else:
                    completed = [(time, item) for time, item in
                                 zip(page["representativeFrameTimesMs"], analyses)
                                 if item["status"] == "completed"]
                    page["imageAnalysis"] = {
                        "status": "completed" if completed else "failed",
                        "title": completed[-1][1]["title"] if completed else "",
                        "content": "\n".join(f"{time} ms: {item['content']}" for time, item in completed)
                                   if completed else "图片理解未完成",
                        "visualElements": [element for _, item in completed for element in item["visualElements"]],
                        "uncertainties": [element for _, item in completed for element in item["uncertainties"]],
                    }
        return {
            "language": transcript["language"],
            "segments": transcript["segments"],
            "visualEvidence": visuals,
            "pageGroups": page_groups,
            "transitionFrameTimesMs": transition_times,
            "visualAnalysisMode": visual_analysis_mode,
            "groupingVersion": GROUPING_VERSION,
            "ocrModelId": OCR_MODEL_ID if visuals else None,
            "imageModelId": os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
                            if visual_analysis_mode == "both" and page_groups else None,
            "review": review,
        }
    except Exception:
        shutil.rmtree(keyframe_dir, ignore_errors=True)
        raise
