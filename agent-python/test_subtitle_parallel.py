import threading
import unittest
from subtitle_calibration import calibrate_subtitles


class ParallelSubtitleTest(unittest.TestCase):
    def test_translation_completeness_is_checked_after_merging_batches(self):
        originals = [{'id': str(i), 'startMs': i * 1000, 'endMs': i * 1000 + 900,
                      'text': '原句'} for i in range(40)]
        def ask(payload):
            return {'changes': [{'segmentId': s['id'], 'text': 'Original sentence.',
                'reason': 'Translation', 'evidence': []} for s in payload['segments']]}
        result = calibrate_subtitles('zh', originals, [], 'en', ask_json=ask, batch_size=20, concurrency=3)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(result['changes']), 40)
        self.assertFalse(any('could not be translated' in message for message in result['concerns']))

    def test_three_batches_overlap_and_merge_in_original_order(self):
        barrier = threading.Barrier(3)
        originals = [{'id': str(i), 'startMs': i * 1000, 'endMs': i * 1000 + 900,
                      'text': '原句'} for i in range(60)]
        def ask(payload):
            barrier.wait(timeout=2)
            return {'changes': [{'segmentId': s['id'], 'text': '元句', 'reason': '同音上下文', 'evidence': []}
                                for s in payload['segments']], '_provider': {'usage': {'total_tokens': 10}}}
        result = calibrate_subtitles('zh', originals, [], ask_json=ask, batch_size=20, concurrency=3)
        self.assertEqual([s['id'] for s in result['segments']], [s['id'] for s in originals])
        self.assertEqual(len(result['changes']), 60)
        self.assertEqual(result['usage']['requestCount'], 3)
        self.assertEqual(result['usage']['total_tokens'], 30)
        self.assertEqual(originals[0]['text'], '原句')

    def test_failed_parallel_batch_retains_original_and_counts_retries(self):
        originals = [{'id': str(i), 'startMs': i * 1000, 'endMs': i * 1000 + 900,
                      'text': '原句'} for i in range(60)]
        def ask(payload):
            if payload['allowedSegmentIds'][0] == '20': return {'bad': 'schema'}
            return {'changes': []}
        result = calibrate_subtitles('zh', originals, [], ask_json=ask, batch_size=20, concurrency=3)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['usage']['requestCount'], 5)
        self.assertEqual(result['usage']['failedChunkCount'], 1)
        self.assertEqual(result['segments'], originals)
