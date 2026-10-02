import unittest
import io
import json
import os
from urllib.error import HTTPError
from unittest.mock import patch

from agent_review import _deepseek_json, review_visual_coverage


def gap(time_ms, start_ms, end_ms, reason="missing_text", evidence=None):
    return {"timeMs": time_ms, "intervalStartMs": start_ms, "intervalEndMs": end_ms,
            "reason": reason, "evidence": evidence or "The stated number is absent from speech and nearby OCR."}


class AgentReviewTest(unittest.TestCase):
    def test_temporary_api_rate_limit_retries_and_returns_real_json(self):
        response = io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {
            "content": '{"resampleRequests":[],"concerns":[]}'}}]}).encode())
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-only"}), \
             patch("agent_review.urlopen", side_effect=[
                 HTTPError("https://example.test", 429, "rate limited", {}, None), response]), \
             patch("agent_review.time.sleep"):
            self.assertEqual(_deepseek_json({}), {"resampleRequests": [], "concerns": []})

    def test_json_review_uses_provider_output_default(self):
        sent = {}

        def fake_urlopen(request, timeout):
            sent.update(json.loads(request.data))
            return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {
                "content": '{"resampleRequests":[],"concerns":[]}'}}]}).encode())

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-only", "DEEPSEEK_MODEL": "deepseek-flash"}):
            with patch("agent_review.urlopen", side_effect=fake_urlopen):
                answer = _deepseek_json({"ocrFrames": []})

        self.assertEqual(answer, {"resampleRequests": [], "concerns": []})
        self.assertEqual(sent["thinking"], {"type": "disabled"})
        self.assertNotIn("max_tokens", sent)
        self.assertIn("OCR cannot show whether a line", sent["messages"][0]["content"])
        self.assertIn("numeric table values not spoken aloud", sent["messages"][0]["content"])

    def test_agent_requests_bounded_half_second_resampling_and_reviews_again(self):
        requested = []
        rounds = iter([
            {"resampleRequests": [gap(1490, 1000, 1900), gap(-500, 0, 1900),
                                  gap(999999, 0, 1900)], "concerns": ["A bullet may appear late"]},
            {"resampleRequests": [], "concerns": []},
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

    def test_dense_requests_for_one_gap_capture_only_one_then_review_again(self):
        captured = []
        answers = iter([
            {"resampleRequests": [gap(time_ms, 0, 3000) for time_ms in
                                  (500, 1000, 1500, 2000, 2500)], "concerns": []},
            {"resampleRequests": [], "concerns": []},
        ])
        _, review = review_visual_coverage(
            duration_ms=4000,
            segments=[],
            visuals=[{"frameTimeMs": 0, "ocrBlocks": []}],
            ask_json=lambda payload: next(answers),
            capture=lambda time_ms: captured.append(time_ms) or [],
        )
        self.assertEqual(captured, [500])
        self.assertEqual(review["resampledTimesMs"], captured)

    def test_distinct_gaps_have_no_whole_video_cap(self):
        captured = []
        calls = []
        _, review = review_visual_coverage(
            duration_ms=600000,
            segments=[],
            visuals=[{"frameTimeMs": 0, "ocrBlocks": []}],
            ask_json=lambda payload: calls.append(payload) or {
                "resampleRequests": [gap(time_ms, time_ms, time_ms + 500)
                                     for time_ms in range(1000, 560000, 35000)],
                "concerns": []},
            capture=lambda time_ms: captured.append(time_ms) or [],
        )
        self.assertEqual(len(captured), 16)
        self.assertEqual(len(calls), 2)
        self.assertEqual(review["resampledTimesMs"], captured)

    def test_separate_one_second_intervals_for_one_issue_capture_once_per_round(self):
        captured = []
        requests = [gap(time_ms, time_ms, time_ms + 500)
                    for time_ms in range(530000, 554000, 1000)]
        _, review = review_visual_coverage(
            duration_ms=600000, segments=[],
            visuals=[{"frameTimeMs": 508000, "ocrBlocks": []}],
            ask_json=lambda payload: {"resampleRequests": requests, "concerns": []},
            capture=lambda time_ms: captured.append(time_ms) or [],
        )
        self.assertEqual(len(captured), 2)
        self.assertEqual(review["resampledTimesMs"], captured)

    def test_two_distinct_nearby_missing_facts_can_both_be_captured(self):
        captured = []
        answers = iter([
            {"resampleRequests": [
                gap(1000, 500, 2500, evidence="The formula denominator is missing."),
                gap(1500, 500, 2500, evidence="The table's June value is missing."),
            ], "concerns": []},
            {"resampleRequests": [], "concerns": []},
        ])
        _, review = review_visual_coverage(
            duration_ms=4000, segments=[],
            visuals=[{"frameTimeMs": 0, "ocrBlocks": []}],
            ask_json=lambda payload: next(answers),
            capture=lambda time_ms: captured.append(time_ms) or [],
        )
        self.assertEqual(captured, [1000, 1500])
        self.assertEqual(review["resampledTimesMs"], captured)

    def test_cross_window_issue_can_capture_in_owning_window_with_neighbor_context(self):
        captured = []
        seen_second_window = []

        def ask(payload):
            if payload["windowStartMs"] == 0:
                return {"resampleRequests": [], "concerns": []}
            seen_second_window.append(payload)
            return {"resampleRequests": [gap(
                600000, 599500, 600500,
                evidence="Numeric table values are only visible at the 10-minute boundary.")],
                "concerns": []}

        _, review = review_visual_coverage(
            duration_ms=610000,
            segments=[{"startMs": 599500, "endMs": 600500, "text": "看表二五月和六月的数值"}],
            visuals=[{"frameTimeMs": 599000, "ocrBlocks": [{"text": "前一页"}]},
                     {"frameTimeMs": 609000, "ocrBlocks": [{"text": "后一页"}]}],
            ask_json=ask,
            capture=lambda time_ms: captured.append(time_ms) or [{"text": "表二"}],
        )
        self.assertEqual(captured, [600000])
        self.assertEqual(review["resampledTimesMs"], [600000])
        self.assertIn(599000, [frame["frameTimeMs"] for frame in seen_second_window[0]["ocrFrames"]])

    def test_ocr_cannot_justify_resampling_a_spoken_line(self):
        captured = []
        _, review = review_visual_coverage(
            duration_ms=4000,
            segments=[{"startMs": 0, "endMs": 4000, "text": "看这条线"}],
            visuals=[{"frameTimeMs": 0, "ocrBlocks": []}],
            ask_json=lambda payload: {"resampleRequests": [gap(1500, 0, 3000, "visual_geometry")],
                                      "concerns": ["Line might be missing"]},
            capture=lambda time_ms: captured.append(time_ms) or [],
        )
        self.assertEqual(captured, [])
        self.assertEqual(review["resampledTimesMs"], [])

    def test_unstructured_legacy_times_do_not_trigger_captures(self):
        captured = []
        _, review = review_visual_coverage(
            duration_ms=4000, segments=[],
            visuals=[{"frameTimeMs": 0, "ocrBlocks": []}],
            ask_json=lambda payload: {"resampleTimesMs": [500, 1000, 1500]},
            capture=lambda time_ms: captured.append(time_ms) or [],
        )
        self.assertEqual(captured, [])
        self.assertEqual(review["resampledTimesMs"], [])


if __name__ == "__main__":
    unittest.main()
