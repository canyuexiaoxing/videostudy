"""A mind-map node must seek to transcript evidence that actually exists."""

import unittest
import io
import json
from unittest.mock import patch
from urllib.error import HTTPError

from mind_map import build_mind_map, _deepseek_json


def provider_response(content):
    return io.BytesIO(json.dumps({'choices': [{'finish_reason': 'stop',
        'message': {'content': content}}]}).encode())


def segment(index: int, text: str | None = None) -> dict:
    return {"id": f"t_{index}", "startMs": index * 1000,
            "endMs": index * 1000 + 900, "text": text or f"知识点 {index}"}


class MindMapTest(unittest.TestCase):
    def setUp(self):
        environment = patch.dict('os.environ', {'MINDMAP_CONCURRENCY': '1'})
        environment.start()
        self.addCleanup(environment.stop)

    def test_three_chunks_overlap_and_keep_chapter_order(self):
        import threading
        import time
        barrier = threading.Barrier(3)
        def ask(payload):
            index = int(payload['segments'][0]['id'].split('_')[1])
            barrier.wait(timeout=3)
            time.sleep((160 - index) / 10000)
            return {'topic': str(index), 'children': [{'title': '知识', 'sourceIds': [f't_{index}']}]}
        with patch.dict('os.environ', {'MINDMAP_CONCURRENCY': '3'}):
            result = build_mind_map([segment(i) for i in range(161)], [], ask)
        self.assertEqual([c['title'] for c in result['root']['children']], ['0', '80', '160'])

    def test_resume_requests_only_failed_chunk(self):
        import tempfile
        from pathlib import Path
        from checkpoints import Checkpoints
        calls = []
        def ask(payload):
            source = payload['segments'][0]['id']
            calls.append(source)
            if source == 't_80' and calls.count(source) == 1: raise RuntimeError('temporary failure')
            return {'topic': source, 'children': [{'title': '知识', 'sourceIds': [source]}]}
        with tempfile.TemporaryDirectory() as d:
            cache = Checkpoints(Path(d), {})
            self.assertEqual(build_mind_map([segment(i) for i in range(81)], [], ask, cache)['status'], 'failed')
            result = build_mind_map([segment(i) for i in range(81)], [], ask, Checkpoints(Path(d), {}))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(calls, ['t_0', 't_80', 't_80'])

    def test_invalid_model_json_automatically_repairs_only_failed_chunk(self):
        calls = []
        def fake_open(request, timeout):
            body = json.loads(request.data)
            payload = json.loads(body['messages'][1]['content'])
            calls.append(payload['segments'][0]['id'])
            if len(calls) == 2:
                return provider_response('{"topic":')
            if len(calls) == 3:
                repair = json.loads(body['messages'][-1]['content'])['responseRepair']
                self.assertIn('error', repair)
            return provider_response(json.dumps({'topic': '章节', 'children': [
                {'title': '有效知识', 'sourceIds': [payload['segments'][0]['id']]}]}))
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-only'}), \
             patch('mind_map.urlopen', side_effect=fake_open):
            result = build_mind_map([segment(i) for i in range(81)], [])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(calls, ['t_0', 't_80', 't_80'])
        self.assertEqual(len(result['root']['children']), 2)

    def test_invalid_response_schema_is_retried_automatically(self):
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-only'}), \
             patch('mind_map.urlopen', side_effect=[provider_response('{"topic":"章节"}'),
                provider_response('{"topic":"章节","children":[]}')]) as request:
            answer = _deepseek_json({'segments': []})
        self.assertEqual(answer, {'topic': '章节', 'children': []})
        self.assertEqual(request.call_count, 2)

    def test_bad_http_json_and_rate_limit_share_three_attempt_limit(self):
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-only'}), \
             patch('mind_map.time.sleep'), \
             patch('mind_map.urlopen', side_effect=[
                 HTTPError('https://example.test', 429, 'limited', {}, None),
                 io.BytesIO(b'not a JSON envelope'),
                 provider_response('{"topic":"章节","children":[]}')]) as request:
            answer = _deepseek_json({'segments': []})
        self.assertEqual(answer['topic'], '章节')
        self.assertEqual(request.call_count, 3)

    def test_failed_chunk_stops_after_three_attempts_and_continues_next_chunk(self):
        calls = []
        def fake_open(request, timeout):
            payload = json.loads(json.loads(request.data)['messages'][1]['content'])
            first_id = payload['segments'][0]['id']
            calls.append(first_id)
            if first_id == 't_80':
                return provider_response('{broken JSON')
            return provider_response(json.dumps({'topic': '章节', 'children': [
                {'title': '有效知识', 'sourceIds': [first_id]}]}))
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-only'}), \
             patch('mind_map.urlopen', side_effect=fake_open):
            result = build_mind_map([segment(i) for i in range(161)], [])
        self.assertEqual(calls, ['t_0', 't_80', 't_80', 't_80', 't_160'])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(len(result['root']['children']), 2)

    def test_authentication_failure_is_not_repeated(self):
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-only'}), \
             patch('mind_map.urlopen', side_effect=HTTPError(
                 'https://example.test', 401, 'invalid credential', {}, None)) as request:
            with self.assertRaises(HTTPError):
                _deepseek_json({'segments': []})
        self.assertEqual(request.call_count, 1)

    def test_nested_outline_keeps_five_levels_and_verified_leaf_times(self):
        transcript = [segment(2, "先讲增长量"), segment(9, "现期减基期得到增长量")]
        result = build_mind_map(transcript, [], ask_json=lambda _: {
            "topic": "资料分析", "children": [{"title": "增长", "children": [
                {"title": "增长量", "children": [
                    {"title": "计算", "children": [
                        {"title": "现期减基期", "sourceIds": ["t_9"], "startMs": 1}
                    ]}
                ]}
            ]}]
        })
        node = result["root"]["children"][0]
        for expected in ["增长", "增长量", "计算", "现期减基期"]:
            node = node["children"][0]
            self.assertEqual(node["title"], expected)
            self.assertEqual(node["startMs"], 9000)
        self.assertEqual(node["evidenceRefs"][0]["quote"], "现期减基期得到增长量")

    def test_valid_nodes_use_source_times_and_quotes_not_model_times(self):
        transcript = [segment(1, "增长量等于现期减基期"), segment(8, "增长率等于增长量除以基期")]

        def ask(payload):
            self.assertEqual([item["id"] for item in payload["segments"]], ["t_1", "t_8"])
            return {"topic": "增长量与增长率", "concepts": [
                {"title": "增长量公式", "sourceIds": ["t_1"], "startMs": 999999},
                {"title": "增长率公式", "sourceIds": ["t_8"]},
            ]}

        result = build_mind_map(transcript, [], ask_json=ask)
        chapter = result["root"]["children"][0]
        first, second = chapter["children"]
        self.assertEqual(result["status"], "completed")
        self.assertEqual(chapter["title"], "增长量与增长率")
        self.assertEqual(first["startMs"], 1000)
        self.assertEqual(first["evidenceRefs"][0]["quote"], "增长量等于现期减基期")
        self.assertEqual(second["startMs"], 8000)
        self.assertEqual(second["evidenceRefs"][0]["sourceId"], "t_8")

    def test_unknown_sources_are_removed_and_cannot_create_fake_nodes(self):
        result = build_mind_map([segment(1)], [], ask_json=lambda _: {
            "topic": "章节", "concepts": [
                {"title": "无证据结论", "sourceIds": ["invented"]},
                {"title": "有据可查", "sourceIds": ["invented", "t_1"]},
            ]})
        nodes = result["root"]["children"][0]["children"]
        self.assertEqual([node["title"] for node in nodes], ["有据可查"])
        self.assertEqual([ref["sourceId"] for ref in nodes[0]["evidenceRefs"]], ["t_1"])

    def test_long_transcript_uses_bounded_chunks(self):
        sizes = []

        def ask(payload):
            sizes.append(len(payload["segments"]))
            return {"topic": "一节", "concepts": [{"title": "要点", "sourceIds": [payload["segments"][0]["id"]]}]}

        result = build_mind_map([segment(i) for i in range(161)], [], ask_json=ask)
        self.assertEqual(sizes, [80, 80, 1])
        self.assertEqual(len(result["root"]["children"]), 3)

    def test_empty_transcript_is_explicit_and_does_not_call_model(self):
        result = build_mind_map([], [], ask_json=lambda _: self.fail("must not call model"))
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["root"]["children"], [])

    def test_failed_chunk_preserves_valid_nodes_and_marks_failure(self):
        calls = 0

        def ask(payload):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("model unavailable")
            return {"topic": "首章", "concepts": [{"title": "有效知识", "sourceIds": ["t_0"]}]}

        result = build_mind_map([segment(i) for i in range(81)], [], ask_json=ask)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["root"]["children"]), 1)
        self.assertEqual(result["root"]["children"][0]["children"][0]["title"], "有效知识")

    def test_intentionally_empty_tail_chunk_does_not_mark_valid_map_failed(self):
        calls = 0

        def ask(payload):
            nonlocal calls
            calls += 1
            if calls == 2:
                return {"topic": "结束语", "concepts": []}
            return {"topic": "正文", "concepts": [{"title": "要点", "sourceIds": ["t_0"]}]}

        result = build_mind_map([segment(i) for i in range(81)], [], ask_json=ask)
        self.assertEqual(result["status"], "completed")


if __name__ == "__main__":
    unittest.main()
