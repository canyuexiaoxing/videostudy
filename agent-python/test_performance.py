"""Regression checks for bounded parallelism, batch timestamps and OCR reuse."""
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import cv2
import numpy as np

from agent_review import review_visual_coverage
from analysis import analyze_file
from visual_evidence import VisualOcrWorker


def fake_visual_server(connection):
    """A spawned transport peer; never load/download models in concurrency tests."""
    try:
        while request := connection.recv():
            if request['op'] == 'bind':
                connection.send({'ok': True, 'value': None})
            elif request['op'] == 'capture_batch':
                connection.send({'ok': True, 'value': [
                    {'frameTimeMs': t, 'ocrBlocks': [{'text': str(os.getpid())}]}
                    for t in request['timesMs']]})
    except EOFError:
        pass
    finally:
        connection.close()


class PerformanceTest(unittest.TestCase):
    def test_review_checks_three_windows_concurrently_then_batches_captures(self):
        barrier = threading.Barrier(3)
        active = peak = 0
        lock = threading.Lock()
        batches = []
        def ask(payload):
            nonlocal active, peak
            if payload['round'] == 2:
                self.assertTrue(any(f['frameTimeMs'] == payload['windowStartMs'] + 1000
                                    for f in payload['ocrFrames']))
                return {'resampleRequests': [], 'concerns': []}
            with lock:
                active += 1
                peak = max(peak, active)
            barrier.wait(timeout=2)
            with lock:
                active -= 1
            t = payload['windowStartMs'] + 1000
            return {'resampleRequests': [{'timeMs': t, 'intervalStartMs': t,
                'intervalEndMs': t + 500, 'reason': 'missing_text', 'evidence': 'Missing table input'}]}
        def capture_batch(times):
            batches.append(times)
            return [{'frameTimeMs': t, 'ocrBlocks': [{'text': 'recovered'}]} for t in times]
        with patch.dict(os.environ, {'REVIEW_CONCURRENCY': '3'}):
            frames, review = review_visual_coverage(duration_ms=1800000, segments=[],
                visuals=[{'frameTimeMs': t, 'ocrBlocks': []} for t in (0, 600000, 1200000)],
                capture=lambda t: self.fail('should use batch capture'),
                capture_batch=capture_batch, ask_json=ask)
        self.assertEqual(peak, 3)
        self.assertEqual(batches, [[1000, 601000, 1201000]])
        self.assertEqual(review['resampledTimesMs'], [1000, 601000, 1201000])
        self.assertEqual(len(frames), 6)

    def test_same_boundary_issue_is_not_captured_twice_in_parallel_windows(self):
        captured = []
        def ask(payload):
            t = 599500 if payload['windowStartMs'] == 0 else 600000
            if payload['round'] == 2:
                t = 599000  # unresolved issue: another time, only on the second round
            return {'resampleRequests': [{'timeMs': t, 'intervalStartMs': 599000,
                'intervalEndMs': 600500, 'reason': 'missing_text', 'evidence': 'Same missing table'}]}
        _, result = review_visual_coverage(duration_ms=610000, segments=[],
            visuals=[{'frameTimeMs': t, 'ocrBlocks': []} for t in (598000, 609000)],
            capture=lambda t: captured.append(t) or [], ask_json=ask)
        self.assertEqual(captured, [599500, 599000])  # one first capture + one second-round alternative
        self.assertEqual(result['resampledTimesMs'], captured)

    def test_speech_and_visual_work_overlap_and_page_results_keep_order(self):
        initial = threading.Barrier(2)
        pages_barrier = threading.Barrier(5)
        lock = threading.Lock()
        active = peak = 0
        def speech(_):
            initial.wait(timeout=2)
            return {'language': 'zh', 'segments': []}
        def visuals():
            initial.wait(timeout=2)
            return []
        def page_analysis(page, pages, frames, root, segments, mode):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            if page['pageIndex'] <= 5:
                pages_barrier.wait(timeout=2)
            time.sleep((6 - page['pageIndex']) * .005)
            with lock:
                active -= 1
            return {**page, 'textAnalysis': {'title': str(page['pageIndex'])}}
        with tempfile.TemporaryDirectory() as d:
            fid = str(uuid4())
            (Path(d) / fid).write_bytes(b'fake media')
            with patch.dict(os.environ, {'MEDIA_TEMP_DIR': d, 'KEYFRAME_DIR': str(Path(d) / 'keyframes'),
                    'PAGE_CONCURRENCY': '5', 'MEDIA_PARALLEL': '1'}), \
                 patch('analysis.transcribe_file', side_effect=speech), \
                 patch('analysis.VisualOcrWorker') as worker, \
                 patch('analysis.media_duration_ms', return_value=2000), \
                 patch('analysis.review_visual_coverage', return_value=([], {})), \
                 patch('analysis.group_pages', return_value=([{'pageIndex': i} for i in range(1, 7)], [])), \
                 patch('analysis.analyze_page', side_effect=page_analysis), \
                 patch('analysis.build_mind_map', return_value={}):
                worker.return_value.__enter__.return_value.analyze.side_effect = visuals
                result = analyze_file(fid, 'ocr_only')
        self.assertEqual(peak, 5)
        self.assertEqual([p['textAnalysis']['title'] for p in result['pageGroups']],
                         ['1', '2', '3', '4', '5', '6'])
        self.assertGreaterEqual(result['stageTimingsMs']['total'], 0)

    def test_visual_process_is_reused_across_media_sessions(self):
        import visual_evidence as visual
        visual.shutdown_visual_worker()
        with patch('visual_evidence._serve_visual_requests', fake_visual_server):
            with VisualOcrWorker(Path('one.mp4')) as first:
                a = first.capture_batch([1000, 2000])
            with VisualOcrWorker(Path('two.mp4')) as second:
                b = second.capture_batch([3000])
            visual.shutdown_visual_worker()
        self.assertEqual(a[0]['ocrBlocks'][0]['text'], b[0]['ocrBlocks'][0]['text'])
        self.assertEqual([f['frameTimeMs'] for f in a], [1000, 2000])

    def test_batch_frame_extraction_keeps_exact_half_second_times(self):
        from visual_evidence import _frames_at
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'colors.avi'
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 4, (160, 90))
            self.assertTrue(writer.isOpened())
            for i in range(16):
                writer.write(np.full((90, 160, 3), i * 12, np.uint8))
            writer.release()
            frames = list(_frames_at(path, [500, 1500, 3000]))
        self.assertEqual([t for t, _ in frames], [500, 1500, 3000])
        self.assertEqual([round(float(f.mean())) for _, f in frames], [24, 72, 144])


if __name__ == '__main__':
    unittest.main()
