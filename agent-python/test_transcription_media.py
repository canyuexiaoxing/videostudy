import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import cv2
import numpy as np

from transcription import transcribe_file


class TranscriptionMediaTest(unittest.TestCase):
    def test_silent_video_has_empty_transcript_instead_of_failing_ocr_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            media_id = str(uuid4())
            path = Path(directory) / media_id
            source = Path(directory) / "silent.avi"
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"MJPG"), 2, (320, 180))
            self.assertTrue(writer.isOpened())
            for _ in range(4):
                writer.write(np.full((180, 320, 3), 255, np.uint8))
            writer.release()
            source.rename(path)
            with patch.dict(os.environ, {"MEDIA_TEMP_DIR": directory}):
                self.assertEqual(transcribe_file(media_id), {"language": "und", "segments": []})


if __name__ == "__main__":
    unittest.main()
