"""Optional end-to-end media test; only the external DeepSeek response is faked."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import cv2
import numpy as np

from agent_review import review_visual_coverage
from analysis import analyze_file
from slide_grouping import group_pages


@unittest.skipUnless(os.environ.get("RUN_MEDIA_INTEGRATION") == "1", "set RUN_MEDIA_INTEGRATION=1")
class MediaIntegrationTest(unittest.TestCase):
    def test_transcribe_sample_ocr_review_without_deleting_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video_only = root / "slides.avi"
            media_id = str(uuid4())
            writer = cv2.VideoWriter(str(video_only), cv2.VideoWriter_fourcc(*"MJPG"), 2, (960, 540))
            self.assertTrue(writer.isOpened())
            titles = ["SLIDE INTRODUCTION", "SLIDE EXAMPLES", "SLIDE SUMMARY"]
            for index in range(24):
                image = np.full((540, 960, 3), 255, np.uint8)
                cv2.putText(image, titles[index // 8], (55, 180), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 5)
                # Make each slide change exceed the configured 2% pixel threshold.
                # Different short titles alone need not exceed it.
                x = 50 + (index // 8) * 200
                cv2.rectangle(image, (x, 330), (x + 140, 470), (0, 0, 0), -1)
                writer.write(image)
            writer.release()
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_only),
                "-f", "lavfi", "-i", "sine=frequency=440:duration=12", "-c:v", "copy",
                "-c:a", "aac", "-shortest", "-f", "matroska", str(root / media_id),
            ], check=True)

            def fake_review(**kwargs):
                return review_visual_coverage(**kwargs, ask_json=lambda payload: {"resampleRequests": [], "concerns": []})

            def fake_page(page, pages, frames, keyframe_dir, segments, mode):
                self.assertEqual(mode, "both")
                return {**page, "imageAnalysis": {"status": "completed", "title": "SLIDE",
                                                 "content": "Visible slide", "visualElements": [],
                                                 "uncertainties": []}}

            with patch.dict(os.environ, {"MEDIA_TEMP_DIR": directory, "KEYFRAME_DIR": str(root / "keyframes")}):
                with patch("analysis.review_visual_coverage", side_effect=fake_review), \
                     patch("analysis.build_mind_map", return_value={"status": "completed", "root": {"children": []}}), \
                     patch("analysis.group_pages", side_effect=lambda visuals, keyframe_dir, segments:
                           group_pages(visuals, keyframe_dir, segments,
                                       ask_json=lambda payload: {"samePage": False, "reason": "test"})), \
                     patch("analysis.analyze_page", side_effect=fake_page):
                    result = analyze_file(media_id)

            self.assertEqual(result["review"]["status"], "completed")
            self.assertEqual(result["ocrModelId"], "PP-OCRv6_medium")
            self.assertEqual(result["imageModelId"], "deepseek-flash")
            self.assertEqual(len(result["visualEvidence"]), 3)
            self.assertEqual(len(result["pageGroups"]), 3)
            self.assertTrue(any("SLIDE" in block["text"] for frame in result["visualEvidence"]
                                for block in frame["ocrBlocks"]))
            self.assertTrue((root / media_id).is_file())
            self.assertTrue((root / "keyframes" / media_id / "2000.jpg").is_file())
            self.assertTrue(all(page["imageAnalysis"]["title"] == "SLIDE"
                                for page in result["pageGroups"]))


if __name__ == "__main__":
    unittest.main()
