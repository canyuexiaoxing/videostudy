import unittest
import io
import json
import os
from unittest.mock import patch

from agent_review import _deepseek_json, review_visual_coverage


class AgentReviewTest(unittest.TestCase):
    def test_json_review_disables_thinking_and_allows_complete_output(self):
        sent = {}

        def fake_urlopen(request, timeout):
            sent.update(json.loads(request.data))
            return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {
                "content": '{"resampleTimesMs":[],"concerns":[]}'}}]}).encode())

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-only", "DEEPSEEK_MODEL": "deepseek-flash"}):
            with patch("agent_review.urlopen", side_effect=fake_urlopen):
                answer = _deepseek_json({"ocrFrames": []})

        self.assertEqual(answer, {"resampleTimesMs": [], "concerns": []})
        self.assertEqual(sent["thinking"], {"type": "disabled"})
        self.assertGreaterEqual(sent["max_tokens"], 1024)

    def test_agent_requests_bounded_half_second_resampling_and_reviews_again(self):
        requested = []
        rounds = iter([
            {"resampleTimesMs": [1490, -500, 999999], "concerns": ["A bullet may appear late"]},
            {"resampleTimesMs": [], "concerns": []},
        ])

        visuals, review = review_visual_coverage(
            duration_ms=4000,
            segments=[{"id": "t_1", "startMs": 0, "endMs": 4000, "text": "First and second point"}],
            visuals=[{"frameTimeMs": 2000, "ocrBlocks": [{"text": "First point", "score": 0.9, "polygon": []}]}],
            ask_json=lambda payload: next(rounds),
            capture=lambda time_ms: requested.append(time_ms) or [{"text": "Second point", "score": 0.9, "polygon": []}],
        )

        self.assertEqual(requested, [1500])
        self.assertEqual([item["frameTimeMs"] for item in visuals], [1500, 2000])
        self.assertEqual(review["status"], "completed")
        self.assertEqual(review["resampledTimesMs"], [1500])

    def test_one_review_can_request_more_than_three_distinct_times(self):
        captured = []
        answers = iter([
            {"resampleTimesMs": [500, 1000, 1500, 2000, 2500], "concerns": []},
            {"resampleTimesMs": [], "concerns": []},
        ])
        _, review = review_visual_coverage(
            duration_ms=4000,
            segments=[],
            visuals=[{"frameTimeMs": 0, "ocrBlocks": []}],
            ask_json=lambda payload: next(answers),
            capture=lambda time_ms: captured.append(time_ms) or [],
        )
        self.assertEqual(captured, [500, 1000, 1500, 2000, 2500])
        self.assertEqual(review["resampledTimesMs"], captured)

    def test_whole_video_safety_limit_still_stops_excess_suggestions(self):
        captured = []
        calls = []
        _, review = review_visual_coverage(
            duration_ms=20000,
            segments=[],
            visuals=[{"frameTimeMs": 0, "ocrBlocks": []}],
            ask_json=lambda payload: calls.append(payload) or {
                "resampleTimesMs": [time_ms for time_ms in range(500, 10000, 500)],
                "concerns": []},
            capture=lambda time_ms: captured.append(time_ms) or [],
        )
        self.assertEqual(len(captured), 12)
        self.assertEqual(len(calls), 1)
        self.assertEqual(review["resampledTimesMs"], captured)


if __name__ == "__main__":
    unittest.main()
