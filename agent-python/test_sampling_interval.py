import io
import os
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock, patch
import numpy as np
from visual_evidence import _candidate_times
from analysis import analyze_file
from app import TranscribeRequest
from pydantic import ValidationError

class SamplingIntervalTests(unittest.TestCase):
    def test_sampling_filter_and_timestamps_follow_selected_interval(self):
        for seconds in (2,3,4):
            with self.subTest(seconds=seconds):
                process=Mock()
                process.stdout=io.BytesIO(b''.join(np.full((180,320),v,np.uint8).tobytes() for v in (0,100,200)))
                process.stderr=io.BytesIO()
                process.wait.return_value=0
                process.poll.return_value=0
                with patch('visual_evidence.subprocess.Popen',return_value=process) as launch:
                    times=_candidate_times(Path('fixture'),sample_seconds=seconds)
                self.assertEqual(times,[0,seconds*1000,seconds*2000])
                self.assertIn(f'fps=1/{seconds}',launch.call_args.args[0][launch.call_args.args[0].index('-vf')+1])

    def test_invalid_interval_is_rejected_before_media_processing(self):
        for value in (0,1,5,2.5):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                TranscribeRequest(fileId='fixture',coarseSampleSeconds=value)
        self.assertEqual(TranscribeRequest(fileId='fixture').coarseSampleSeconds,2)

    def test_interval_reaches_worker_and_invalidates_analysis_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            file_id=str(uuid4())
            (Path(directory)/file_id).write_bytes(b'fixture')
            with patch.dict(os.environ,{'MEDIA_TEMP_DIR':directory,'KEYFRAME_DIR':str(Path(directory)/'frames')}), \
                 patch('analysis.transcribe_file',return_value={'language':'zh','segments':[]}), \
                 patch('analysis.VisualOcrWorker') as worker, \
                 patch('analysis.media_duration_ms',return_value=10000), \
                 patch('analysis.review_visual_coverage',return_value=([],{'status':'not_applicable'})), \
                 patch('analysis.group_pages',return_value=([],[])):
                worker.return_value.__enter__.return_value.analyze.return_value=[]
                analyze_file(file_id,coarse_sample_seconds=2)
                result=analyze_file(file_id,coarse_sample_seconds=4)
                self.assertEqual(worker.call_args.kwargs['sample_seconds'],4)
                self.assertEqual(worker.return_value.__enter__.return_value.analyze.call_count,2)
                self.assertEqual(result['coarseSampleSeconds'],4)
