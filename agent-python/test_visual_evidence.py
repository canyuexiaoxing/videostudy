"""Exercise visual coarse selection on a generated lesson-like video."""

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import cv2
import numpy as np

from visual_evidence import _candidate_times, analyze_visuals


class VisualEvidenceTest(unittest.TestCase):
    def test_coarse_frames_use_batch_extraction_and_preserve_ocr_and_files(self):
        frames = [(1000, np.full((20, 30, 3), 20, np.uint8)),
                  (2500, np.full((20, 30, 3), 80, np.uint8))]
        with tempfile.TemporaryDirectory() as d, \
             patch('visual_evidence._has_video', return_value=True), \
             patch('visual_evidence._candidate_times', return_value=[1000, 2500]), \
             patch('visual_evidence._frames_at', return_value=iter(frames)), \
             patch('visual_evidence._frame_at', side_effect=AssertionError('serial extraction used')):
            root = Path(d)
            path = root / 'lesson.mp4'
            path.write_bytes(b'fixture')
            result = analyze_visuals(path, keyframe_dir=root,
                recognize=lambda frame: [{'text': str(int(frame[0, 0, 0])), 'score': 1, 'polygon': []}])
            self.assertEqual([f['frameTimeMs'] for f in result], [1000, 2500])
            self.assertEqual([f['ocrBlocks'][0]['text'] for f in result], ['20', '80'])
            self.assertEqual(sorted(p.name for p in root.glob('*.jpg')), ['1000.jpg', '2500.jpg'])

    def test_small_annotation_does_not_create_its_own_candidate_before_slide_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "annotation.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 2, (640, 360))
            self.assertTrue(writer.isOpened())
            for frame_index in range(16):
                image = np.full((360, 640, 3), 255, np.uint8)
                if frame_index >= 4:
                    cv2.rectangle(image, (20, 20), (79, 79), (0, 0, 0), -1)
                if frame_index >= 12:
                    cv2.rectangle(image, (80, 80), (560, 280), (0, 0, 0), -1)
                writer.write(image)
            writer.release()

            self.assertEqual(_candidate_times(path), [4000, 6000])

    def test_repeated_frames_are_skipped_but_each_slide_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "slides.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 2, (640, 360))
            self.assertTrue(writer.isOpened())
            for index in range(24):
                slide = index // 8
                image = np.full((360, 640, 3), 255, np.uint8)
                title = ["INTRODUCTION", "EXAMPLES", "SUMMARY"][slide]
                cv2.putText(image, title, (35, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 4)
                writer.write(image)
            writer.release()

            evidence = analyze_visuals(path, recognize=lambda image: [{"text": "slide", "score": 1.0, "polygon": []}])

            self.assertEqual(len(evidence), 3)
            self.assertEqual([item["frameTimeMs"] for item in evidence], [2000, 6000, 10000])
            self.assertEqual(evidence[0]["ocrBlocks"][0]["text"], "slide")

    def test_audio_only_media_has_no_visual_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio.wav"
            import wave
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\0\0" * 16000)
            self.assertEqual(analyze_visuals(path, recognize=lambda image: []), [])

    def test_selected_frames_are_saved_for_image_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "slides.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 2, (640, 360))
            self.assertTrue(writer.isOpened())
            for _ in range(8):
                writer.write(np.full((360, 640, 3), 255, np.uint8))
            writer.release()

            evidence = analyze_visuals(path, recognize=lambda image: [], keyframe_dir=root / "keyframes")

            self.assertEqual(len(evidence), 1)
            self.assertTrue((root / "keyframes" / f"{evidence[0]['frameTimeMs']}.jpg").is_file())

    def test_small_progressive_annotations_are_grouped_into_completed_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "writing.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 2, (640, 360))
            self.assertTrue(writer.isOpened())
            for frame_index in range(40):
                image = np.full((360, 640, 3), 255, np.uint8)
                for mark in range(frame_index // 4):
                    x = 20 + (mark % 5) * 100
                    y = 30 + (mark // 5) * 80
                    cv2.rectangle(image, (x, y), (x + 30, y + 20), (0, 0, 0), -1)
                writer.write(image)
            writer.release()

            evidence = analyze_visuals(path, recognize=lambda image: [])

            self.assertEqual([item["frameTimeMs"] for item in evidence], [18000])


if __name__ == "__main__":
    unittest.main()
