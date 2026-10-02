import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from page_understanding import analyze_page, build_page_context, _deepseek_page_json


def page(index, times, representatives, ocr="题目里的数值是 42"):
    return {"pageIndex": index, "firstFrameTimeMs": times[0], "lastFrameTimeMs": times[-1],
            "memberFrameTimesMs": times, "representativeFrameTimesMs": representatives,
            "ocrLines": [{"text": ocr, "sourceFrameTimeMs": times[0], "sourceBlockIndex": 0}],
            "imageAnalysis": None}


def response(*, occluded=False, missing=False, spoken=False, title="课程例题"):
    return {"title": title, "content": "老师讲解的内容", "confirmedContent": "老师讲解的内容",
            "inferences": [], "unresolvedPoints": [], "corrections": [],
            "visualElements": [], "uncertainties": [], "conflicts": [], "calculationChecks": [],
            "occlusion": {"hasOcclusion": occluded, "criticalContentMissing": missing,
                          "speechCoversMissing": spoken}}


class PageUnderstandingTest(unittest.TestCase):
    def test_third_format_attempt_keeps_only_latest_invalid_reply(self):
        calls = []
        incomplete = response()
        del incomplete['corrections']
        def fake_urlopen(request, timeout):
            body = json.loads(request.data)
            calls.append(body)
            answer = incomplete if len(calls) < 3 else response()
            return io.BytesIO(json.dumps({'choices': [{'finish_reason': 'stop',
                'message': {'content': json.dumps(answer)}}]}).encode())
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-only'}), \
             patch('page_understanding.urlopen', side_effect=fake_urlopen):
            answer = _deepseek_page_json({'route': 'ocr_only', 'transcript': [], 'ocrLines': []}, [])
        self.assertEqual(answer['content'], '老师讲解的内容')
        self.assertEqual(len(calls[2]['messages']), 4)

    def test_invalid_response_retry_tells_model_missing_required_fields(self):
        calls = []
        incomplete = response()
        del incomplete['corrections']
        incomplete['inferences'] = [{'claim': 'unsupported shape'}]
        def fake_urlopen(request, timeout):
            body = json.loads(request.data)
            calls.append(body)
            if len(calls) == 1:
                answer = incomplete
            else:
                repair = json.loads(body['messages'][-1]['content'])['responseRepair']
                self.assertIn('corrections', repair['missingFields'])
                answer = response()
            return io.BytesIO(json.dumps({'choices': [{'finish_reason': 'stop',
                'message': {'content': json.dumps(answer)}}]}).encode())
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-only'}), \
             patch('page_understanding.urlopen', side_effect=fake_urlopen):
            answer = _deepseek_page_json({'route': 'ocr_only', 'transcript': [], 'ocrLines': []}, [])
        self.assertEqual(answer['content'], '老师讲解的内容')
        self.assertEqual(len(calls), 2)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def image(self, time_ms, mark):
        canvas = np.full((180, 320, 3), 255, np.uint8)
        cv2.rectangle(canvas, (40, 40), (140 + mark, 110), (0, 0, 0), 3)
        cv2.imwrite(str(self.root / f"{time_ms}.jpg"), canvas)

    def test_speech_is_assigned_between_neighboring_page_midpoints(self):
        pages = [page(1, [1000, 2000], [2000]), page(2, [5000, 6000], [6000])]
        segments = [{"startMs": 2800, "endMs": 3200, "text": "上一页讲解"},
                    {"startMs": 3900, "endMs": 4200, "text": "下一页讲解"}]
        first = build_page_context(pages[0], pages, segments, "ocr_only")
        second = build_page_context(pages[1], pages, segments, "both")
        self.assertEqual([item["text"] for item in first["transcript"]], ["上一页讲解"])
        self.assertEqual([item["text"] for item in second["transcript"]], ["下一页讲解"])
        self.assertEqual(first["ocrLines"][0]["text"], "题目里的数值是 42")
        self.assertNotIn("ocrLines", second)

    def test_text_route_sends_speech_and_ocr_but_no_images(self):
        selected = page(1, [1000], [1000])
        calls = []
        def ask(payload, images):
            calls.append((payload, images))
            return response()
        result = analyze_page(selected, [selected], {1000: {"frameTimeMs": 1000, "ocrBlocks": []}},
                              self.root, [{"startMs": 500, "endMs": 1500, "text": "讲了增长量"}],
                              "ocr_only", ask_json=ask)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], [])
        self.assertEqual(calls[0][0]["transcript"][0]["text"], "讲了增长量")
        self.assertIn("ocrLines", calls[0][0])
        self.assertEqual(result["textAnalysis"]["status"], "completed")
        self.assertIsNone(result["imageAnalysis"])

    def test_image_route_sends_speech_and_one_image_without_ocr(self):
        self.image(1000, 10)
        selected = page(1, [1000], [1000])
        calls = []
        def ask(payload, images):
            calls.append((payload, images))
            return response()
        result = analyze_page(selected, [selected], {1000: {"frameTimeMs": 1000, "ocrBlocks": []}},
                              self.root, [{"startMs": 500, "endMs": 1500, "text": "讲了增长量"}],
                              "both", ask_json=ask)
        self.assertEqual(len(calls), 1)
        self.assertEqual([time for time, _ in calls[0][1]], [1000])
        self.assertEqual(calls[0][0]["transcript"][0]["text"], "讲了增长量")
        self.assertNotIn("ocrLines", calls[0][0])
        self.assertNotIn("题目里的数值是 42", json.dumps(calls[0][0], ensure_ascii=False))
        self.assertEqual(result["imageAnalysis"]["status"], "completed")

    def test_critical_occlusion_not_covered_by_speech_sends_one_more_same_page_image(self):
        self.image(1000, 10)
        self.image(2000, 50)
        selected = page(1, [1000, 2000], [1000, 2000])
        frames = {time: {"frameTimeMs": time, "ocrBlocks": [{"text": str(time)}]}
                  for time in (1000, 2000)}
        calls = []
        def ask(payload, images):
            calls.append((payload, [time for time, _ in images]))
            return response(occluded=True, missing=True) if len(calls) == 1 else response(title="补图后的结果")
        result = analyze_page(selected, [selected], frames, self.root,
                              [{"startMs": 1000, "endMs": 2000, "text": "只讲了背景"}],
                              "both", ask_json=ask)
        self.assertEqual([times for _, times in calls], [[2000], [2000, 1000]])
        self.assertTrue(all("ocrLines" not in payload for payload, _ in calls))
        self.assertEqual(result["representativeFrameTimesMs"], [2000, 1000])
        self.assertEqual(result["imageAnalysis"]["title"], "补图后的结果")

    def test_critical_occlusion_sends_two_ranked_same_page_images_together(self):
        for time_ms, mark in ((1000, 10), (2000, 30), (3000, 50), (4000, 70)):
            self.image(time_ms, mark)
        selected = page(1, [1000, 2000, 3000, 4000], [1000, 4000])
        frames = {
            1000: {"frameTimeMs": 1000, "ocrBlocks": [{"text": "题干"}]},
            2000: {"frameTimeMs": 2000, "ocrBlocks": [{"text": "题干"}, {"text": "步骤"}]},
            3000: {"frameTimeMs": 3000, "ocrBlocks": [{"text": "题干"}, {"text": "步骤"},
                                                       {"text": "最终结果117"}]},
            4000: {"frameTimeMs": 4000, "ocrBlocks": [{"text": "题干"}]},
        }
        calls = []

        def ask(payload, images):
            calls.append((payload, [time for time, _ in images]))
            return response(occluded=True, missing=True) if len(calls) == 1 else response()

        result = analyze_page(selected, [selected], frames, self.root, [], "both", ask_json=ask)
        self.assertEqual([times for _, times in calls], [[4000], [4000, 3000, 2000]])
        self.assertEqual(result["representativeFrameTimesMs"], [4000, 3000, 2000])
        self.assertEqual(len(calls), 2)

    def test_speech_covers_occlusion_so_no_second_image(self):
        self.image(1000, 10)
        self.image(2000, 50)
        selected = page(1, [1000, 2000], [1000, 2000])
        calls = []
        result = analyze_page(selected, [selected],
                              {time: {"frameTimeMs": time, "ocrBlocks": []} for time in (1000, 2000)},
                              self.root, [], "both",
                              ask_json=lambda payload, images: calls.append(images) or
                              response(occluded=True, missing=True, spoken=True))
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["representativeFrameTimesMs"], [2000])

    def test_missing_content_without_occlusion_does_not_request_another_image(self):
        self.image(1000, 10)
        self.image(2000, 50)
        selected = page(1, [1000, 2000], [1000, 2000])
        calls = []
        analyze_page(selected, [selected],
                     {time: {"frameTimeMs": time, "ocrBlocks": []} for time in (1000, 2000)},
                     self.root, [], "both",
                     ask_json=lambda payload, images: calls.append(images) or
                     response(occluded=False, missing=True, spoken=False))
        self.assertEqual(len(calls), 1)

    def test_failed_second_image_keeps_first_answer(self):
        self.image(1000, 10)
        self.image(2000, 50)
        selected = page(1, [1000, 2000], [1000, 2000])
        calls = []
        def ask(payload, images):
            calls.append(images)
            if len(calls) == 2:
                raise TimeoutError("second request timed out")
            return response(occluded=True, missing=True, title="首次结果")
        result = analyze_page(selected, [selected],
                              {time: {"frameTimeMs": time, "ocrBlocks": []} for time in (1000, 2000)},
                              self.root, [], "both", ask_json=ask)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["imageAnalysis"]["title"], "首次结果")
        self.assertIn("补充截图分析失败", "".join(result["imageAnalysis"]["uncertainties"]))

    def test_near_duplicate_candidate_is_not_sent_again(self):
        self.image(1000, 10)
        (self.root / "2000.jpg").write_bytes((self.root / "1000.jpg").read_bytes())
        selected = page(1, [1000, 2000], [1000, 2000])
        calls = []
        result = analyze_page(selected, [selected],
                              {time: {"frameTimeMs": time, "ocrBlocks": []} for time in (1000, 2000)},
                              self.root, [], "both",
                              ask_json=lambda payload, images: calls.append(images) or
                              response(occluded=True, missing=True, spoken=False))
        self.assertEqual(len(calls), 1)
        self.assertIn("没有找到", "".join(result["imageAnalysis"]["uncertainties"]))

    def test_model_failure_preserves_raw_page_evidence(self):
        selected = page(1, [1000], [1000])
        result = analyze_page(selected, [selected], {}, self.root, [], "ocr_only",
                              ask_json=lambda payload, images: (_ for _ in ()).throw(TimeoutError("slow")))
        self.assertEqual(result["textAnalysis"]["status"], "failed")
        self.assertEqual(result["ocrLines"], selected["ocrLines"])

    def test_image_conflict_triggers_one_independent_verification_without_ocr(self):
        self.image(1000, 10)
        selected = page(1, [1000], [1000])
        calls = []
        def ask(payload, images):
            calls.append((payload, images))
            if len(calls) == 1:
                return {**response(), "content": "语音是2014，图片是2104",
                        "conflicts": ["语音2014与画面2104不符"]}
            return {**response(title="复核正确"), "content": "25+231×9=2104，2104-1987=117"}
        result = analyze_page(selected, [selected], {1000: {"frameTimeMs": 1000, "ocrBlocks": []}},
                              self.root, [], "both", ask_json=ask)
        self.assertEqual(len(calls), 2)
        self.assertEqual([time for time, _ in calls[1][1]], [1000])
        self.assertNotIn("ocrLines", calls[1][0])
        self.assertIn("verification", calls[1][0])
        self.assertEqual(result["imageAnalysis"]["title"], "复核正确")

    def test_incorrect_arithmetic_triggers_verification_even_if_model_misses_conflict(self):
        selected = page(1, [1000], [1000])
        calls = []
        def ask(payload, images):
            calls.append(payload)
            if len(calls) == 1:
                return {**response(), "content": "25+231×9=2079",
                        "calculationChecks": [{"expression": "25+231*9", "result": "2079"}]}
            return {**response(), "content": "25+231×9=2104",
                    "calculationChecks": [{"expression": "25+231*9", "result": "2104"}]}
        result = analyze_page(selected, [selected], {}, self.root, [], "ocr_only", ask_json=ask)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("verification", calls[0])
        self.assertIn("calculation", " ".join(calls[1]["verification"]["reasons"]).lower())
        self.assertEqual(result["textAnalysis"]["status"], "completed")
        self.assertIn("2104", result["textAnalysis"]["content"])

    def test_unresolved_conflict_does_not_publish_wrong_conclusion_as_completed(self):
        selected = page(1, [1000], [1000])
        wrong = {**response(), "content": "25+231×9=2079",
                 "calculationChecks": [{"expression": "25+231*9", "result": "2079"}]}
        result = analyze_page(selected, [selected], {}, self.root, [], "ocr_only",
                              ask_json=lambda payload, images: wrong)
        self.assertEqual(result["textAnalysis"]["status"], "unverified")
        self.assertNotIn("2079", result["textAnalysis"]["content"])
        self.assertIn("争议结论：？", result["textAnalysis"]["content"])
        self.assertIn("老师讲解的内容", result["textAnalysis"]["content"])
        self.assertTrue(result["textAnalysis"]["uncertainties"])

    def test_unresolved_occlusion_preserves_confirmed_content_and_marks_specific_gap(self):
        self.image(1000, 10)
        self.image(2000, 50)
        selected = page(1, [1000, 2000], [2000])
        answer = {**response(occluded=True, missing=True),
                  "content": "题干是增长量，答案是我猜的117",
                  "confirmedContent": "题干讨论增长量。",
                  "unresolvedPoints": ["最终计算结果"]}
        result = analyze_page(selected, [selected],
                              {time: {"frameTimeMs": time, "ocrBlocks": [{"text": str(time)}]}
                               for time in (1000, 2000)},
                              self.root, [], "both", ask_json=lambda payload, images: answer)
        analysis = result["imageAnalysis"]
        self.assertEqual(analysis["status"], "unverified")
        self.assertIn("题干讨论增长量", analysis["content"])
        self.assertIn("最终计算结果：？", analysis["content"])
        self.assertNotIn("117", analysis["content"])

    def test_grounded_inference_is_labeled_and_does_not_claim_to_be_video_text(self):
        selected = page(1, [1000], [1000])
        answer = {**response(), "confirmedContent": "题干给出25与231×9。",
                  "inferences": ["据题干算式推得25＋231×9＝2104（非视频原文）"],
                  "calculationChecks": [{"expression": "25+231*9", "result": "2104"}]}
        result = analyze_page(selected, [selected], {}, self.root, [], "ocr_only",
                              ask_json=lambda payload, images: answer)
        self.assertEqual(result["textAnalysis"]["status"], "inferred")
        self.assertIn("推导", result["textAnalysis"]["content"])
        self.assertIn("2104", result["textAnalysis"]["content"])

    def test_model_can_return_confirmed_content_as_a_list_of_supported_points(self):
        selected = page(1, [1000], [1000])
        answer = {**response(), "confirmedContent": ["题干给出两个年份。", "老师比较了增长量。"],
                  "unresolvedPoints": ["最后一步的数字"]}
        result = analyze_page(selected, [selected], {}, self.root, [], "ocr_only",
                              ask_json=lambda payload, images: answer)
        self.assertEqual(result["textAnalysis"]["status"], "unverified")
        self.assertIn("题干给出两个年份", result["textAnalysis"]["content"])
        self.assertIn("老师比较了增长量", result["textAnalysis"]["content"])
        self.assertIn("最后一步的数字：？", result["textAnalysis"]["content"])

    def test_corrected_recognition_is_disclosed_after_verification(self):
        selected = page(1, [1000], [1000])
        calls = []
        def ask(payload, images):
            calls.append(payload)
            if len(calls) == 1:
                return {**response(), "conflicts": ["转写2014与算式2104冲突"]}
            return {**response(), "confirmedContent": "老师用原算式计算增长量。",
                    "corrections": ["语音转写2014更正为2104；依据25＋231×9＝2104"]}
        result = analyze_page(selected, [selected], {}, self.root, [], "ocr_only", ask_json=ask)
        self.assertEqual(result["textAnalysis"]["status"], "completed")
        self.assertIn("识别修正", result["textAnalysis"]["content"])
        self.assertIn("2014", result["textAnalysis"]["content"])

    def test_request_body_separates_text_and_image_routes(self):
        image = self.root / "1000.jpg"
        image.write_bytes(b"jpeg bytes")
        bodies = []
        def fake_urlopen(request, timeout):
            bodies.append(json.loads(request.data))
            return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {
                "content": json.dumps(response())}}]}).encode())
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-only"}), \
             patch("page_understanding.urlopen", side_effect=fake_urlopen):
            _deepseek_page_json({"route": "ocr_only", "transcript": [{"text": "讲解"}],
                                 "ocrLines": [{"text": "OCR"}]}, [])
            _deepseek_page_json({"route": "both", "transcript": [{"text": "讲解"}]}, [(1000, image)])
        text_content = bodies[0]["messages"][1]["content"]
        image_content = bodies[1]["messages"][1]["content"]
        self.assertIn("OCR", json.dumps(text_content, ensure_ascii=False))
        self.assertNotIn("image_url", json.dumps(text_content))
        self.assertIn("讲解", json.dumps(image_content, ensure_ascii=False))
        self.assertNotIn("OCR", json.dumps(image_content, ensure_ascii=False))
        self.assertIn("image_url", json.dumps(image_content))


if __name__ == "__main__":
    unittest.main()
