import json
import os
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

from subtitle_delivery import publish_subtitle_source, _deliver_source


class SubtitleDeliveryTest(unittest.TestCase):
    def test_source_delivery_is_async_and_snapshots_only_grouped_text(self):
        entered, release = threading.Event(), threading.Event()
        captured = []
        def deliver(url, token, encoded):
            entered.set()
            release.wait(3)
            captured.append(json.loads(encoded))
        segments = [{'id': 't_1', 'startMs': 0, 'endMs': 1000, 'text': '原始讲解'}]
        pages = [{'pageIndex': 1, 'firstFrameTimeMs': 0, 'lastFrameTimeMs': 1000,
                  'ocrLines': [{'text': '题干', 'sourceFrameTimeMs': 500}]}]
        with patch('subtitle_delivery._deliver_source', side_effect=deliver):
            future = publish_subtitle_source(str(uuid4()), 'private-course-token', 'zh', segments, pages)
            try:
                self.assertTrue(entered.wait(1))
                self.assertFalse(future.done())
                segments[0]['text'] = '后来修改'
                pages[0]['ocrLines'][0]['text'] = '后来修改'
            finally:
                release.set()
            future.result(timeout=3)
        self.assertEqual(captured[0]['segments'][0]['text'], '原始讲解')
        self.assertEqual(captured[0]['pageGroups'][0]['ocrLines'][0]['text'], '题干')
        self.assertNotIn('images', captured[0])

    def test_transient_transport_failure_retries_but_unauthorized_does_not(self):
        from urllib.error import HTTPError
        from io import BytesIO
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self): return b'{}'
        with patch('subtitle_delivery.urlopen', side_effect=[OSError('connection lost'), Response()]) as request, \
             patch('subtitle_delivery.time.sleep'):
            self.assertTrue(_deliver_source('http://java-api:18080/callback', 'secret', b'{}'))
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args.args[0].get_header('X-subtitle-token'), 'secret')
        denied = HTTPError('http://java-api:18080/callback', 403, 'denied', {}, BytesIO(b''))
        with patch('subtitle_delivery.urlopen', side_effect=denied) as request, patch('subtitle_delivery.time.sleep'):
            self.assertFalse(_deliver_source('http://java-api:18080/callback', 'secret', b'{}'))
        self.assertEqual(request.call_count, 1)

    def test_missing_callback_token_performs_no_http_request(self):
        with patch('subtitle_delivery._deliver_source') as deliver:
            self.assertIsNone(publish_subtitle_source(str(uuid4()), None, 'zh', [], []))
            deliver.assert_not_called()

    def test_invalid_id_is_rejected_before_network(self):
        with self.assertRaises(ValueError):
            publish_subtitle_source('../../outside', 'token', 'zh', [], [])


if __name__ == '__main__': unittest.main()
