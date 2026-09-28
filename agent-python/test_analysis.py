import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from analysis import analyze_file


class AnalysisTest(unittest.TestCase):
    def test_ocr_only_keeps_page_groups_without_sending_images(self):
        with tempfile.TemporaryDirectory() as directory:
            file_id = str(uuid4())
            (Path(directory) / file_id).write_bytes(b"fake media")
            page = {"pageIndex": 1, "firstFrameTimeMs": 1000, "lastFrameTimeMs": 2000,
                    "memberFrameTimesMs": [1000, 2000], "representativeFrameTimesMs": [2000],
                    "ocrLines": [], "imageAnalysis": None}
            visuals = [{"frameTimeMs": time, "ocrBlocks": []} for time in (1000, 2000)]
            with patch.dict(os.environ, {"MEDIA_TEMP_DIR": directory, "KEYFRAME_DIR": directory}), \
                 patch("analysis.transcribe_file", return_value={"language": "zh", "segments": []}), \
                 patch("analysis.VisualOcrWorker") as worker, \
                 patch("analysis.media_duration_ms", return_value=3000), \
                 patch("analysis.review_visual_coverage", return_value=(visuals, {"status": "completed"})), \
                 patch("analysis.group_pages", return_value=([page], [])), \
                 patch("analysis.analyze_page", side_effect=lambda page, pages, frames, root, segments, mode:
                       {**page, "textAnalysis": {"status": "completed", "title": "OCR page", "content": "speech+OCR",
                                                  "visualElements": [], "uncertainties": []}}) as analyze:
                worker.return_value.__enter__.return_value.analyze.return_value = visuals
                result = analyze_file(file_id, "ocr_only")
            analyze.assert_called_once()
            self.assertEqual(analyze.call_args.args[-1], "ocr_only")
            self.assertEqual(result["pageGroups"][0]["memberFrameTimesMs"], [1000, 2000])
            self.assertEqual(result["pageGroups"][0]["textAnalysis"]["title"], "OCR page")
            self.assertIsNone(result["imageModelId"])
            self.assertEqual(result["visualAnalysisMode"], "ocr_only")
            worker.assert_called_once()
            self.assertEqual(worker.call_args.kwargs["page_change_fraction"], 0.02)

    def test_selected_threshold_reaches_visual_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            file_id = str(uuid4())
            (Path(directory) / file_id).write_bytes(b"fake media")
            with patch.dict(os.environ, {"MEDIA_TEMP_DIR": directory, "KEYFRAME_DIR": directory}), \
                 patch("analysis.transcribe_file", return_value={"language": "zh", "segments": []}), \
                 patch("analysis.VisualOcrWorker") as worker, \
                 patch("analysis.media_duration_ms", return_value=3000), \
                 patch("analysis.review_visual_coverage", return_value=([], {"status": "not_applicable"})), \
                 patch("analysis.group_pages", return_value=([], [])):
                worker.return_value.__enter__.return_value.analyze.return_value = []
                result = analyze_file(file_id, coarse_change_percent=3)
            self.assertEqual(worker.call_args.kwargs["page_change_fraction"], 0.03)
            self.assertEqual(result["coarseChangePercent"], 3)

    def test_both_sends_only_page_representatives(self):
        with tempfile.TemporaryDirectory() as directory:
            file_id = str(uuid4())
            (Path(directory) / file_id).write_bytes(b"fake media")
            visuals = [{"frameTimeMs": time, "ocrBlocks": []} for time in (1000, 2000, 3000)]
            page = {"pageIndex": 1, "firstFrameTimeMs": 1000, "lastFrameTimeMs": 3000,
                    "memberFrameTimesMs": [1000, 2000, 3000], "representativeFrameTimesMs": [3000],
                    "ocrLines": [], "imageAnalysis": None}
            sent = []
            def fake_analyze(page, pages, frames, root, segments, mode):
                sent.append((page["representativeFrameTimesMs"], mode, segments))
                return {**page, "imageAnalysis": {"status": "completed", "title": "Final", "content": "visible",
                                                 "visualElements": [], "uncertainties": []}}
            with patch.dict(os.environ, {"MEDIA_TEMP_DIR": directory, "KEYFRAME_DIR": directory}), \
                 patch("analysis.transcribe_file", return_value={"language": "zh", "segments": []}), \
                 patch("analysis.VisualOcrWorker") as worker, \
                 patch("analysis.media_duration_ms", return_value=4000), \
                 patch("analysis.review_visual_coverage", return_value=(visuals, {"status": "completed"})), \
                 patch("analysis.group_pages", return_value=([page], [])), \
                 patch("analysis.analyze_page", side_effect=fake_analyze):
                worker.return_value.__enter__.return_value.analyze.return_value = visuals
                result = analyze_file(file_id)
            self.assertEqual(sent, [([3000], "both", [])])
            self.assertEqual(result["pageGroups"][0]["imageAnalysis"]["title"], "Final")
            self.assertEqual(len(result["visualEvidence"]), 3)

    def test_video_remains_available_through_agent_review(self):
        with tempfile.TemporaryDirectory() as directory:
            file_id = str(uuid4())
            path = Path(directory) / file_id
            path.write_bytes(b"fake media")
            with patch.dict(os.environ, {"MEDIA_TEMP_DIR": directory, "KEYFRAME_DIR": directory}):
                with patch("analysis.transcribe_file", return_value={"language": "zh", "segments": []}), \
                     patch("analysis.VisualOcrWorker") as worker, \
                     patch("analysis.media_duration_ms", return_value=3000), \
                     patch("analysis.group_pages", return_value=([{"pageIndex": 1, "firstFrameTimeMs": 1000,
                         "lastFrameTimeMs": 1000, "memberFrameTimesMs": [1000],
                         "representativeFrameTimesMs": [1000], "ocrLines": [], "imageAnalysis": None}], [])), \
                     patch("analysis.analyze_page", side_effect=lambda page, pages, frames, root, segments, mode:
                           {**page, "imageAnalysis": {"status": "completed", "title": "Slide", "content": "Text",
                                                      "visualElements": [], "uncertainties": []}}), \
                     patch("analysis.review_visual_coverage", return_value=(
                         [{"frameTimeMs": 1000, "ocrBlocks": []}],
                         {"status": "completed", "resampledTimesMs": [], "concerns": []},
                     )) as review:
                    worker.return_value.__enter__.return_value.analyze.return_value = [{"frameTimeMs": 1000, "ocrBlocks": []}]
                    result = analyze_file(file_id)

            self.assertTrue(path.exists())
            self.assertEqual(result["review"]["status"], "completed")
            self.assertEqual(result["imageModelId"], "deepseek-flash")
            self.assertEqual(result["pageGroups"][0]["imageAnalysis"]["title"], "Slide")
            review.assert_called_once()


if __name__ == "__main__":
    unittest.main()
