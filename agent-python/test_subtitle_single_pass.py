"""Regression checks for model-decided correction without semantic re-review."""
import unittest

from subtitle_calibration import calibrate_subtitles


class SubtitleSinglePassTest(unittest.TestCase):
    def test_distant_synonyms_and_definition_rewrite_are_rejected(self):
        originals = [{'id': 'a', 'startMs': 0, 'endMs': 1000, 'text': '清晰法'},
                     {'id': 'b', 'startMs': 1000, 'endMs': 2000, 'text': '在实验的情况上'}]
        result = calibrate_subtitles('zh', originals, [], ask_json=lambda _: {'changes': [
            {'segmentId': 'a', 'text': '清楚了', 'reason': '更通顺', 'evidence': []},
            {'segmentId': 'b', 'text': '在基期的基础上', 'reason': '符合定义', 'evidence': []}]})
        self.assertEqual(result['segments'], originals)
        self.assertEqual(result['rejectedCount'], 2)

    def test_minimal_final_particle_and_same_sound_number_are_allowed(self):
        originals = [{'id': 'a', 'startMs': 0, 'endMs': 1000, 'text': '清晰法'},
                     {'id': 'b', 'startMs': 1000, 'endMs': 2000, 'text': '百分之二事'}]
        result = calibrate_subtitles('zh', originals, [], ask_json=lambda _: {'changes': [
            {'segmentId': 'a', 'text': '清晰了', 'reason': '句尾读音和上下文', 'evidence': []},
            {'segmentId': 'b', 'text': '百分之二十', 'reason': '百分数读法', 'evidence': []}]})
        self.assertEqual([s['text'] for s in result['segments']], ['清晰了', '百分之二十'])
    def test_supported_number_reading_is_corrected_without_global_homophone_replacement(self):
        originals = [{'id': 'a', 'startMs': 0, 'endMs': 1000, 'text': '乘以百分之二事'},
                     {'id': 'b', 'startMs': 1000, 'endMs': 2000, 'text': '这件事要分两次处理'}]
        reference = {'sourceFrameTimeMs': 0, 'text': '160×20%=32'}
        result = calibrate_subtitles('zh', originals, [{'pageIndex': 1,
            'firstFrameTimeMs': 0, 'lastFrameTimeMs': 2000, 'ocrLines': [reference]}],
            ask_json=lambda _: {'changes': [{'segmentId': 'a', 'text': '乘以百分之二十',
                'reason': '百分数读法和20%支持二十', 'evidence': [reference]}]})
        self.assertEqual(result['segments'][0]['text'], '乘以百分之二十')
        self.assertEqual(result['segments'][1]['text'], originals[1]['text'])

    def test_prompt_requires_separate_number_reading_and_ordinary_word_checks(self):
        import io
        import json
        from unittest.mock import patch
        import subtitle_calibration as s
        calls = []
        def opened(request, timeout):
            calls.append(json.loads(request.data))
            return io.BytesIO(json.dumps({'choices': [{'finish_reason': 'stop',
                'message': {'content': '{"changes":[]}'}}]}).encode())
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test'}), patch.object(s, 'urlopen', side_effect=opened):
            s._deepseek_json({'mode': 'correction', 'segments': [], 'pageGroups': []})
        instructions = calls[0]['messages'][0]['content']
        self.assertIn('Separate checks for technical terms, ordinary vocabulary, and spoken numbers', instructions)
        self.assertIn('百分之二事', instructions)
        self.assertIn('Do not replace an uncertain spoken number with a convenient slide number', instructions)
        self.assertIn('Phonetic plausibility is required', instructions)
        self.assertIn('清晰法', instructions)
        self.assertIn('实验', instructions)
        self.assertNotIn('pronunciation alone is not a veto', instructions)
        self.assertEqual(len(calls), 1)
    def test_next_slide_can_support_introduction_even_if_previous_sample_is_closer(self):
        original = {'id': 't_117', 'startMs': 668290, 'endMs': 671290,
                    'text': '第三个一道题 上海的一道心题'}
        reference = {'sourceFrameTimeMs': 694000, 'text': '【例3】（2026上海）'}
        result = calibrate_subtitles('zh', [original], [
            {'pageIndex': 6, 'firstFrameTimeMs': 584000, 'lastFrameTimeMs': 666000,
             'ocrLines': [{'sourceFrameTimeMs': 584000, 'text': '【例2】'}]},
            {'pageIndex': 7, 'firstFrameTimeMs': 694000, 'lastFrameTimeMs': 1076000,
             'ocrLines': [reference]}], ask_json=lambda _: {'changes': [{
                 'segmentId': 't_117', 'text': '例三这一道题 上海的一道新题',
                 'reason': '新题符合试题语境，随后课件例3支持例三', 'evidence': [reference]}]})
        self.assertEqual(result['segments'][0]['text'], '例三这一道题 上海的一道新题')

    def test_first_slide_candidate_can_support_speech_before_its_capture_time(self):
        original = {'id': 't_1', 'startMs': 0, 'endMs': 10000,
                    'text': '增长量等于限期 限期期'}
        reference = {'sourceFrameTimeMs': 28000, 'text': '公式一：增长量=现期-基期'}
        result = calibrate_subtitles('zh', [original], [{
            'pageIndex': 1, 'firstFrameTimeMs': 28000, 'lastFrameTimeMs': 108000,
            'ocrLines': [reference]}], ask_json=lambda _: {'changes': [{
                'segmentId': 't_1', 'text': '增长量等于现期减基期',
                'reason': '最近课件的公式和讲解支持这一短语', 'evidence': [reference]}]})
        self.assertEqual(result['segments'][0]['text'], '增长量等于现期减基期')

    def test_each_chunk_has_one_request_even_when_both_chunks_have_changes(self):
        originals = [{'id': f't_{i}', 'startMs': i * 1000, 'endMs': i * 1000 + 900,
                      'text': '我王祺吃饭了'} for i in range(51)]
        calls = []

        def ask(payload):
            calls.append(payload)
            return {'changes': [{'segmentId': item['id'], 'text': '我忘记吃饭了',
                                'reason': '上下文语义支持忘记吃饭', 'evidence': []}
                               for item in payload['segments']]}

        result = calibrate_subtitles('zh', originals, [], ask_json=ask, batch_size=50, concurrency=1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['usage']['requestCount'], 2)
        self.assertEqual(len(result['changes']), 51)
        self.assertTrue(all('reviewCorrections' not in payload for payload in calls))

    def test_evidence_backed_phrase_is_applied_without_phonetic_veto_or_review(self):
        original = {'id': 't_0', 'startMs': 0, 'endMs': 2000,
                    'text': '增长量等于现期限期期'}
        reference = {'sourceFrameTimeMs': 1000, 'text': '增长量=现期-基期'}
        calls = []

        def ask(payload):
            calls.append(payload)
            return {'changes': [{'segmentId': 't_0', 'text': '增长量等于现期减基期',
                                'reason': '同页公式与上下文支持减基期这一短语',
                                'evidence': [reference]}]}

        result = calibrate_subtitles('zh', [original], [{
            'pageIndex': 1, 'firstFrameTimeMs': 0, 'lastFrameTimeMs': 3000,
            'ocrLines': [reference]}], ask_json=ask)
        self.assertEqual(result['segments'][0]['text'], '增长量等于现期减基期')
        self.assertEqual(result['segments'][0]['startMs'], original['startMs'])
        self.assertEqual(result['segments'][0]['endMs'], original['endMs'])
        self.assertEqual(original['text'], '增长量等于现期限期期')
        self.assertEqual(len(calls), 1)
        self.assertNotIn('reviewCorrections', calls[0])

    def test_uncertain_model_result_keeps_original_without_recheck(self):
        original = {'id': 't_0', 'startMs': 0, 'endMs': 2000, 'text': '无法确定的原句'}
        calls = []

        def ask(payload):
            calls.append(payload)
            return {'changes': []}

        result = calibrate_subtitles('zh', [original], [], ask_json=ask)
        self.assertEqual(result['segments'], [original])
        self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
