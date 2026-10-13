"""Offline integration of streaming media, ready groups, final revision and APIs."""
import json
import os
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
from uuid import uuid4
from concurrent.futures import CancelledError

import analysis
from analysis_progress import AnalysisProgress


def frame(ms):
    return {'frameTimeMs': ms, 'ocrBlocks': []}


def page(n, ms):
    return {'pageIndex': n, 'firstFrameTimeMs': ms, 'lastFrameTimeMs': ms,
            'memberFrameTimesMs': [ms], 'representativeFrameTimesMs': [ms], 'ocrLines': []}


class FakeSignal:
    def __init__(self, root):
        self.root = root
        self.cancelled = False
    def is_set(self):
        return self.cancelled
    def check(self):
        if self.cancelled:
            raise CancelledError('cancelled')


class FakeGrouper:
    def __init__(self, *args, **kwargs):
        self.count = 0
    def add(self, evidence):
        self.count += 1
        return [dict(page(self.count, evidence['frameTimeMs']), _closedAtMs=evidence['frameTimeMs'] + 1)]
    def finish(self):
        return []


class FakeScheduler:
    instances = []
    def __init__(self, root, analyze, **kwargs):
        self.analyze = analyze
        self.calls = []
        self.closed = False
        self.cancelled = False
        self.signal = kwargs['signal']
        self.instances.append(self)
    def update(self, pages, segments, visuals, **flags):
        self.calls.append((list(pages), list(segments), list(visuals), flags))
    def finish(self, pages, segments, visuals):
        self.final = (pages, segments, visuals)
        return [dict(p, groupUnderstanding={'status': 'completed', 'knowledgeCandidates': [],
                     'exampleCandidates': []}, imageAnalysis={'status': 'completed'}) for p in pages]
    def cancel(self):
        self.cancelled = True
    def close(self):
        self.closed = True


class GroupedPipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fid = str(uuid4())
        (self.root / self.fid).write_bytes(b'media')
        FakeScheduler.instances.clear()
        self.scheduler_module = types.ModuleType('group_scheduler')
        self.scheduler_module.RunSignal = FakeSignal
        self.scheduler_module.ReadyGroupScheduler = FakeScheduler
        self.scheduler_module.cancel_run = lambda p: None
        self.scheduler_module.reset_run = lambda p: None
        self.course_module = types.ModuleType('course_mind_map')
        self.course_module.build_course_mind_map = lambda *a, **kw: {'status': 'empty', 'root': {'children': []}}
        self.env = patch.dict(os.environ, {'MEDIA_TEMP_DIR': str(self.root),
                        'KEYFRAME_DIR': str(self.root / 'frames'), 'MEDIA_PARALLEL': '1'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def run_pipeline(self, speech, visual, final_pages=None):
        def transcribe(fid, on_segment=None):
            for item in speech:
                if on_segment:
                    on_segment(item)
            return {'language': 'zh', 'segments': speech}
        def recognize(on_frame=None):
            for item in visual:
                if on_frame:
                    on_frame(item)
            return visual
        modules = {'group_scheduler': self.scheduler_module, 'course_mind_map': self.course_module}
        with patch.dict('sys.modules', modules), patch('analysis.transcribe_file', side_effect=transcribe), \
             patch('analysis.VisualOcrWorker') as worker, \
             patch('slide_grouping.IncrementalPageGrouper', FakeGrouper), \
             patch('analysis.media_duration_ms', return_value=9000), \
             patch('analysis.review_visual_coverage', return_value=(visual, {'status': 'completed'})), \
             patch('analysis.group_pages', return_value=(final_pages or [page(1, 1000)], [])), \
             patch('analysis.safe_overview', return_value={'status': 'empty'}), \
             patch('analysis.build_mind_map', return_value={'status': 'empty'}) as old_map:
            worker.return_value.__enter__.return_value.analyze.side_effect = recognize
            value = analysis.analyze_file(self.fid, grouped_analysis=True)
            return value, old_map.call_count

    def test_opt_in_rejects_ocr_only(self):
        with self.assertRaisesRegex(ValueError, 'both'):
            analysis.analyze_file(self.fid, 'ocr_only', grouped_analysis=True)

    def test_fewer_than_four_groups_finalize_and_use_group_course_map(self):
        value, old_calls = self.run_pipeline([], [frame(1000)])
        self.assertEqual(value['pageGroups'][0]['groupUnderstanding']['status'], 'completed')
        self.assertEqual(old_calls, 0)
        self.assertTrue(FakeScheduler.instances[0].closed)
        self.assertTrue(value['groupedAnalysis'])
        self.assertIn('refinement', value['stageTimingsMs'])

    def test_callbacks_update_scheduler_before_media_stage_completes(self):
        speech = [{'id': 's1', 'startMs': 0, 'endMs': 9000, 'text': 'teacher'}]
        self.run_pipeline(speech, [frame(n * 1000) for n in range(1, 6)])
        calls = FakeScheduler.instances[0].calls
        self.assertTrue(any(len(pages) >= 4 and not flags.get('grouping_complete', False)
                            for pages, segments, visuals, flags in calls))

    def test_real_scheduler_starts_four_groups_while_visual_media_is_still_running(self):
        from group_scheduler import ReadyGroupScheduler
        self.scheduler_module.ReadyGroupScheduler = ReadyGroupScheduler
        started = threading.Event()
        speech = [{'id': 's1', 'startMs': 0, 'endMs': 9000, 'text': 'teacher'}]
        def transcribe(fid, on_segment):
            on_segment(speech[0])
            return {'language': 'zh', 'segments': speech}
        def recognize(on_frame):
            for n in range(1, 6):
                ms = n * 1000
                path = self.root / 'frames' / self.fid / f'{ms}.jpg'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'provider screenshot')
                on_frame(frame(ms))
                if n == 4:
                    self.assertTrue(started.wait(2), 'four ready groups must start before OCR returns')
            return [frame(n * 1000) for n in range(1, 6)]
        def understand(p, *args, **kwargs):
            started.set()
            return dict(p, groupUnderstanding={'status': 'completed', 'knowledgeCandidates': [],
                'exampleCandidates': [], 'supplementCount': 0, 'uncertainties': [],
                'forwardImageTimesMs': []})
        with patch.dict('sys.modules', {'group_scheduler': self.scheduler_module,
                                       'course_mind_map': self.course_module}), \
             patch('analysis.transcribe_file', side_effect=transcribe), \
             patch('analysis.VisualOcrWorker') as worker, \
             patch('slide_grouping.IncrementalPageGrouper', FakeGrouper), \
             patch('group_understanding.analyze_group', side_effect=understand), \
             patch('analysis.media_duration_ms', return_value=9000), \
             patch('analysis.review_visual_coverage', return_value=([frame(n * 1000) for n in range(1, 6)],
                                                                   {'status': 'completed'})), \
             patch('analysis.group_pages', return_value=([page(n, n * 1000) for n in range(1, 6)], [])), \
             patch('analysis.safe_overview', return_value={'status': 'empty'}):
            worker.return_value.__enter__.return_value.analyze.side_effect = recognize
            result = analysis.analyze_file(self.fid, grouped_analysis=True)
        self.assertEqual(len(result['pageGroups']), 5)
        self.assertTrue(started.is_set())

    def test_checkpoint_hits_replay_evidence_without_duplicate_frame_callbacks(self):
        speech = [{'id': 's1', 'startMs': 0, 'endMs': 9000, 'text': 'teacher'}]
        self.run_pipeline(speech, [frame(1000), frame(2000)])
        value, _ = self.run_pipeline(speech, [frame(1000), frame(2000)])
        scheduler = FakeScheduler.instances[-1]
        self.assertEqual(len(scheduler.final[1]), 1)
        self.assertEqual(len(scheduler.final[2]), 2)
        self.assertEqual(value['reusedCheckpoints']['transcription'], 1)
        self.assertEqual(value['reusedCheckpoints']['visualOcr'], 1)
        self.assertTrue(any(pages and segments for pages, segments, visuals, flags in scheduler.calls))

    def test_final_grouping_revision_is_passed_to_scheduler_finish(self):
        revised = [dict(page(1, 1000), lastFrameTimeMs=2000, memberFrameTimesMs=[1000, 2000])]
        value, _ = self.run_pipeline([], [frame(1000), frame(2000)], revised)
        self.assertEqual(FakeScheduler.instances[-1].final[0], revised)
        self.assertEqual(value['pageGroups'][0]['memberFrameTimesMs'], [1000, 2000])

    def test_signal_cancellation_stops_coverage_and_materials(self):
        original = FakeSignal.check
        def check(signal):
            if FakeScheduler.instances and FakeScheduler.instances[-1].calls:
                raise CancelledError('cancelled')
            original(signal)
        with patch.object(FakeSignal, 'check', check):
            with self.assertRaises(CancelledError):
                self.run_pipeline([], [frame(1000)])
        self.assertTrue(FakeScheduler.instances[0].cancelled)
        self.assertTrue(FakeScheduler.instances[0].closed)

    def test_group_progress_does_not_replace_media_counters(self):
        progress = AnalysisProgress(self.root / 'progress')
        progress.enter('media', 0, 2)
        progress.unit_done('transcription', 'media')
        progress.update_groups(4, 2, 5, 'content')
        value = json.loads((self.root / 'progress' / 'progress.json').read_text())
        self.assertEqual(value['stage'], 'media')
        self.assertEqual(value['completedUnits'], 1)
        self.assertEqual(value['readyGroups'], 4)
        self.assertEqual(value['completedGroups'], 2)

    def test_app_only_passes_grouped_keyword_when_opted_in(self):
        from app import TranscribeRequest, analyze
        with patch('app.analyze_file', return_value={}) as call:
            analyze(TranscribeRequest(fileId=self.fid))
            self.assertNotIn('grouped_analysis', call.call_args.kwargs)
            analyze(TranscribeRequest(fileId=self.fid, groupedAnalysis=True))
            self.assertTrue(call.call_args.kwargs['grouped_analysis'])

    def test_grouped_mind_map_uses_saved_candidates_without_page_reanalysis(self):
        import app
        candidates = [dict(page(1, 1000), groupUnderstanding={'status': 'completed',
            'knowledgeCandidates': [], 'exampleCandidates': []})]
        captured = []
        self.course_module.build_course_mind_map = lambda *a, **kw: captured.append(a) or {'status': 'empty'}
        with patch.dict('sys.modules', {'course_mind_map': self.course_module,
                                       'group_scheduler': self.scheduler_module}), \
             patch('group_understanding.analyze_group') as page_analyze, \
             patch('app.build_mind_map') as old_map:
            value = app.generate_mind_map(app.MindMapRequest(segments=[], pageGroups=candidates,
                        groupedAnalysis=True, courseId=self.fid))
        self.assertEqual(value['status'], 'empty')
        self.assertEqual(captured[0][1], candidates)
        page_analyze.assert_not_called()
        old_map.assert_not_called()

    def test_historical_refresh_missing_course_id_rejects_before_model(self):
        import app
        from fastapi import HTTPException
        with patch('group_understanding.analyze_group') as page_analyze, patch('app.build_mind_map') as old_map:
            with self.assertRaises(HTTPException):
                app.generate_mind_map(app.MindMapRequest(segments=[], pageGroups=[page(1, 1000)],
                                                       groupedAnalysis=True))
            page_analyze.assert_not_called()
            old_map.assert_not_called()

    def test_legacy_mind_map_remains_default_without_paid_group_analysis(self):
        import app
        with patch('app.build_mind_map', return_value={'status': 'empty'}) as old_map, \
             patch('group_understanding.analyze_group') as page_analyze:
            app.generate_mind_map(app.MindMapRequest(segments=[], pageGroups=[page(1, 1000)]))
        old_map.assert_called_once_with([], [page(1, 1000)])
        page_analyze.assert_not_called()

    def test_cancel_api_rejects_paths_and_uses_uuid_task_directory(self):
        import app
        from fastapi import HTTPException
        with patch.dict('sys.modules', {'group_scheduler': self.scheduler_module}):
            with self.assertRaises(HTTPException):
                app.cancel_analysis(app.AnalysisControlRequest(fileId='../secret'))
            captured = []
            self.scheduler_module.cancel_run = lambda path: captured.append(path)
            app.cancel_analysis(app.AnalysisControlRequest(fileId=self.fid))
            self.assertEqual(captured, [(self.root / 'frames' / self.fid / '.analysis').resolve()])


if __name__ == '__main__':
    unittest.main()
