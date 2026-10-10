import json
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from analysis_progress import AnalysisProgress

class ProgressTest(unittest.TestCase):
    def test_parallel_page_completion_is_atomic_and_unique(self):
        with tempfile.TemporaryDirectory() as d:
            progress=AnalysisProgress(Path(d))
            progress.enter('pages',3,20)
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda i: progress.unit_done(str(i%20),'pages'),range(40)))
            value=json.loads((Path(d)/'progress.json').read_text())
            self.assertEqual(value,{'stage':'pages','completedStages':3,'totalStages':5,'completedUnits':20,'totalUnits':20})
            progress.enter('materials',4,2)
            progress.unit_done('old-page','pages')
            self.assertEqual(json.loads((Path(d)/'progress.json').read_text())['completedUnits'],0)

    def test_progress_failure_does_not_fail_analysis(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            with patch.object(Path,'mkdir',side_effect=OSError('disk unavailable')):
                AnalysisProgress(Path(d)).enter('media',0,2)

    def test_reported_stages_follow_actual_pipeline_and_cached_retry(self):
        import os
        from uuid import uuid4
        from unittest.mock import patch
        import analysis
        with tempfile.TemporaryDirectory() as d:
            fid=str(uuid4());(Path(d)/fid).write_bytes(b'media')
            root=Path(d)/'frames'/fid/'.analysis'
            def stage():return json.loads((root/'progress.json').read_text())
            def page(*args):
                self.assertEqual(stage()['stage'],'pages')
                return {'pageIndex':1,'imageAnalysis':{'status':'completed'}}
            def overview(*args):
                self.assertEqual(stage()['stage'],'materials')
                return {'status':'completed'}
            with patch.dict(os.environ,{'MEDIA_TEMP_DIR':d,'KEYFRAME_DIR':str(Path(d)/'frames')}), patch('analysis.transcribe_file',return_value={'language':'zh','segments':[]}) as speech, patch('analysis.VisualOcrWorker') as worker, patch('analysis.media_duration_ms',return_value=1000), patch('analysis.review_visual_coverage',return_value=([],{'status':'completed'})), patch('analysis.group_pages',return_value=([{'pageIndex':1}],[])), patch('analysis.analyze_page',side_effect=page), patch('analysis.safe_overview',side_effect=overview), patch('analysis.build_mind_map',return_value={'status':'completed'}):
                worker.return_value.__enter__.return_value.analyze.return_value=[]
                analysis.analyze_file(fid)
                self.assertEqual(stage()['stage'],'saving')
                self.assertEqual(stage()['completedStages'],4)
                analysis.analyze_file(fid)
                self.assertEqual(speech.call_count,1)
                self.assertEqual(stage()['stage'],'saving')
