"""Image understanding remains separate from OCR evidence."""

import tempfile
import unittest
import io
import json
from pathlib import Path
from unittest.mock import patch

from image_understanding import VisionFormatError, _deepseek_vision_json, describe_frames


class ImageUnderstandingTest(unittest.TestCase):
    def test_maps_batched_image_results_back_to_frame_times(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            visuals = [{"frameTimeMs": time, "ocrBlocks": [{"text": f"OCR {time}"}]}
                       for time in (1000, 2000, 3000)]
            for time in (1000, 2000, 3000):
                (root / f"{time}.jpg").write_bytes(b"image")
            batches = []

            def fake_vision(frames):
                batches.append([time for time, _ in frames])
                return {"frames": [{"frameTimeMs": time, "title": f"Page {time}",
                                    "content": "Visible content", "visualElements": [], "uncertainties": []}
                                   for time, _ in frames]}

            result = describe_frames(visuals, root, ask_json=fake_vision, batch_size=2)

            self.assertEqual(batches, [[1000, 2000], [3000]])
            self.assertEqual(result[0]["ocrBlocks"], visuals[0]["ocrBlocks"])
            self.assertEqual(result[0]["imageAnalysis"]["title"], "Page 1000")
            self.assertEqual(result[0]["imageAnalysis"]["status"], "completed")
            self.assertEqual(result[2]["imageAnalysis"]["content"], "Visible content")

    def test_rejects_missing_frame_response(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "1000.jpg").write_bytes(b"image")
            result = describe_frames([{"frameTimeMs": 1000, "ocrBlocks": []}], root,
                                     ask_json=lambda _: {"frames": []})
            self.assertEqual(result[0]["imageAnalysis"]["status"], "failed")

    def test_deepseek_request_contains_image_data_and_timestamp_without_ocr(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "1000.jpg"
            image.write_bytes(b"image bytes")
            sent = []

            def fake_urlopen(request, timeout):
                sent.append(json.loads(request.data))
                return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {
                    "content": '{"frames":[]}'}}]}).encode())

            with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-only", "DEEPSEEK_MODEL": "deepseek-flash"}), \
                 patch("image_understanding.urlopen", side_effect=fake_urlopen):
                _deepseek_vision_json([(1000, image)])

            content = sent[0]["messages"][1]["content"]
            self.assertIn("frameTimeMs=1000", content[1]["text"])
            self.assertTrue(content[2]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
            self.assertNotIn("OCR", json.dumps(content))

    def test_malformed_json_is_retried_for_the_same_image(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "1000.jpg"
            image.write_bytes(b"image bytes")
            replies = iter(['{"frames":[{"frameTimeMs":1000,"title":"bad}',
                            '{"frames":[{"frameTimeMs":1000,"title":"ok","content":"text",'
                            '"visualElements":[],"uncertainties":[]}]}'])
            requests = []

            def fake_urlopen(request, timeout):
                requests.append(request)
                return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {
                    "content": next(replies)}}]}).encode())

            with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-only"}), \
                 patch("image_understanding.urlopen", side_effect=fake_urlopen):
                result = _deepseek_vision_json([(1000, image)])

            self.assertEqual(len(requests), 2)
            self.assertEqual(result["frames"][0]["title"], "ok")

    def test_one_unreadable_image_does_not_discard_ocr_or_other_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for time in (1000, 2000):
                (root / f"{time}.jpg").write_bytes(b"image")
            visuals = [{"frameTimeMs": time, "ocrBlocks": [{"text": "OCR"}]} for time in (1000, 2000)]

            def fake_vision(frames):
                time = frames[0][0]
                if time == 1000:
                    raise VisionFormatError("invalid JSON")
                return {"frames": [{"frameTimeMs": time, "title": "ok", "content": "text",
                                    "visualElements": [], "uncertainties": []}]}

            result = describe_frames(visuals, root, ask_json=fake_vision)

            self.assertEqual(result[0]["ocrBlocks"][0]["text"], "OCR")
            self.assertEqual(result[0]["imageAnalysis"]["status"], "failed")
            self.assertEqual(result[1]["imageAnalysis"]["status"], "completed")

    def test_image_service_failure_preserves_ocr_and_marks_only_that_page(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "1000.jpg").write_bytes(b"image")
            visual = {"frameTimeMs": 1000, "ocrBlocks": [{"text": "公式"}]}
            result = describe_frames([visual], root, ask_json=lambda _: (_ for _ in ()).throw(TimeoutError("slow")))
            self.assertEqual(result[0]["ocrBlocks"], visual["ocrBlocks"])
            self.assertEqual(result[0]["imageAnalysis"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
