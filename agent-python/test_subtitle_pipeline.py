import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from app import TranscribeRequest, SubtitleRequest, analyze, generate_subtitles
from analysis import analyze_file


class SubtitlePipelineTest(unittest.TestCase):
    def test_subtitle_endpoint_forwards_text_only_and_rejects_unsupported_target(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            SubtitleRequest(language='zh', segments=[], targetLanguage='fr')
        with patch('subtitle_calibration.calibrate_subtitles', return_value={'status': 'completed'}) as run:
            self.assertEqual(generate_subtitles(SubtitleRequest(language='zh', segments=[], pageGroups=[], targetLanguage='en')),
                             {'status': 'completed'})
        run.assert_called_once_with('zh', [], [], 'en')

    def test_requested_callback_token_reaches_analysis_but_old_calls_are_unchanged(self):
        fid = str(uuid4())
        with patch('app.analyze_file', return_value={}) as run:
            analyze(TranscribeRequest(fileId=fid, subtitleCallbackToken='private-course-token'))
        self.assertEqual(run.call_args.args, (fid, 'both', 2.0, 'private-course-token'))
        with patch('app.analyze_file', return_value={}) as run:
            analyze(TranscribeRequest(fileId=fid))
        self.assertEqual(run.call_args.args, (fid, 'both', 2.0))

    def test_subtitle_source_is_scheduled_after_grouping_before_page_understanding(self):
        with tempfile.TemporaryDirectory() as directory:
            fid = str(uuid4())
            (Path(directory) / fid).write_bytes(b'media')
            events = []
            speech = [{'id': 't_1', 'startMs': 0, 'endMs': 1000, 'text': '原始讲解'}]
            page = {'pageIndex': 1, 'firstFrameTimeMs': 0, 'lastFrameTimeMs': 1000,
                    'ocrLines': [{'text': '题干', 'sourceFrameTimeMs': 500}]}
            def grouped(*args):
                events.append('grouped')
                return [page], []
            def publish(*args): events.append('subtitle')
            def understand(*args):
                events.append('page')
                return {**page, 'imageAnalysis': {'status': 'completed'}}
            def diagram(*args, **kwargs):
                events.append('map')
                return {'status': 'empty'}
            with patch.dict(os.environ, {'MEDIA_TEMP_DIR': directory, 'KEYFRAME_DIR': str(Path(directory) / 'frames')}), \
                 patch('analysis.transcribe_file', return_value={'language': 'zh', 'segments': speech}), \
                 patch('analysis.VisualOcrWorker') as worker, \
                 patch('analysis.media_duration_ms', return_value=1000), \
                 patch('analysis.review_visual_coverage', return_value=([], {'status': 'completed'})), \
                 patch('analysis.group_pages', side_effect=grouped), \
                 patch('analysis.publish_subtitle_source', side_effect=publish) as delivery, \
                 patch('analysis.analyze_page', side_effect=understand), \
                 patch('analysis.build_mind_map', side_effect=diagram):
                worker.return_value.__enter__.return_value.analyze.return_value = []
                result = analyze_file(fid, subtitle_callback_token='private-course-token')
            self.assertEqual(events, ['grouped', 'subtitle', 'page', 'map'])
            delivery.assert_called_once_with(fid, 'private-course-token', 'zh', speech, [page])
            self.assertEqual(result['segments'], speech)

    def test_subtitle_delivery_failure_does_not_fail_main_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            fid = str(uuid4())
            (Path(directory) / fid).write_bytes(b'media')
            with patch.dict(os.environ, {'MEDIA_TEMP_DIR': directory, 'KEYFRAME_DIR': str(Path(directory) / 'frames')}), \
                 patch('analysis.transcribe_file', return_value={'language': 'zh', 'segments': []}), \
                 patch('analysis.VisualOcrWorker') as worker, \
                 patch('analysis.media_duration_ms', return_value=1000), \
                 patch('analysis.review_visual_coverage', return_value=([], {'status': 'completed'})), \
                 patch('analysis.group_pages', return_value=([], [])), \
                 patch('analysis.publish_subtitle_source', side_effect=RuntimeError('transport down')), \
                 patch('analysis.build_mind_map', return_value={'status': 'empty'}):
                worker.return_value.__enter__.return_value.analyze.return_value = []
                result = analyze_file(fid, subtitle_callback_token='private-course-token')
            self.assertEqual(result['language'], 'zh')
            self.assertEqual(result['mindMap']['status'], 'empty')


if __name__ == '__main__': unittest.main()
