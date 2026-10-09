"""Single-pass subtitle decisions preserve source metadata and validate citations."""

import copy
import importlib
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

try:
    calibration = importlib.import_module('subtitle_calibration')
except ModuleNotFoundError:
    calibration = None


def segment(index=0, text='我王祺吃饭了'):
    return {'id': f't_{index}', 'startMs': index * 1000,
            'endMs': index * 1000 + 900, 'text': text}


def page(text='忘记吃饭', first=0, last=10000, frame=1000, index=1):
    return {'pageIndex': index, 'firstFrameTimeMs': first, 'lastFrameTimeMs': last,
            'ocrLines': [{'sourceFrameTimeMs': frame, 'text': text}],
            'imageAnalysis': {'title': 'Do not send derived guesses'},
            'imagePath': '/private/frame.jpg'}


def change(source='t_0', text='我忘记吃饭了', evidence=None, reason='同音近音识别错误'):
    return {'segmentId': source, 'text': text, 'reason': reason,
            'evidence': evidence if evidence is not None else []}


def response(content, usage=None, model='deepseek-test'):
    envelope = {'model': model, 'choices': [{'finish_reason': 'stop',
                  'message': {'content': content}}]}
    if usage is not None:
        envelope['usage'] = usage
    return io.BytesIO(json.dumps(envelope).encode())


class SubtitleCalibrationTest(unittest.TestCase):




    def test_punctuation_does_not_consume_spoken_character_budget(self):
        originals = [segment(text='我王祺吃饭了。')]
        result = self.run_calibration(originals, [change(text='我忘记吃饭了！')])
        self.assertEqual(result['segments'][0]['text'], '我忘记吃饭了！')

    def setUp(self):
        self.assertIsNotNone(calibration, 'subtitle calibration module is not implemented')

    def run_calibration(self, originals, changes, language='zh', pages=None, target='source'):
        return calibration.calibrate_subtitles(language, originals, pages or [], target,
                                               ask_json=lambda _: {'changes': changes})

    def test_chinese_near_sound_correction_keeps_original_times_and_input(self):
        originals = [segment()]
        snapshot = copy.deepcopy(originals)
        reference = {'sourceFrameTimeMs': 1000, 'text': '忘记吃饭'}
        result = self.run_calibration(originals, [change(evidence=[reference])], pages=[page()])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['segments'], [segment(text='我忘记吃饭了')])
        self.assertEqual(result['sourceLanguage'], 'zh')
        self.assertEqual(result['targetLanguage'], 'zh')
        self.assertEqual(result['mode'], 'correction')
        self.assertEqual(result['changes'][0]['originalText'], '我王祺吃饭了')
        self.assertEqual(result['changes'][0]['evidence'], [reference])
        self.assertEqual(originals, snapshot)




    def test_one_local_missing_character_can_be_restored_from_source_ocr(self):
        originals = [segment(text='我们今讨论增长率')]
        reference = {'sourceFrameTimeMs': 1000, 'text': '今天讨论增长率'}
        result = self.run_calibration(originals, [change(text='我们今天讨论增长率', evidence=[reference])],
                                      pages=[page(text=reference['text'])])
        self.assertEqual(result['segments'][0]['text'], '我们今天讨论增长率')
        self.assertEqual(result['rejectedCount'], 0)


    def test_english_homophones_and_spelling_variants_are_allowed(self):
        for before, after in [('There car is red.', 'Their car is red.'),
                              ('The colour is blue.', 'The color is blue.'),
                              ('It is a dark night.', 'It is a dark knight.')]:
            with self.subTest(before=before):
                result = self.run_calibration([segment(text=before)], [change(text=after)], language='en')
                self.assertEqual(result['segments'][0]['text'], after)
                self.assertEqual(result['rejectedCount'], 0)




    def test_translation_allows_non_phonetic_changes_in_both_directions(self):
        for source, target, original, translated in [
                ('zh', 'en', '我忘记吃饭了', 'I forgot to eat.'),
                ('en', 'zh', 'I forgot to eat.', '我忘记吃饭了')]:
            with self.subTest(source=source):
                result = self.run_calibration([segment(text=original)], [change(text=translated)],
                                              language=source, target=target)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(result['mode'], 'translation')
                self.assertEqual(result['targetLanguage'], target)
                self.assertEqual(result['segments'], [segment(text=translated)])

    def test_untranslated_segment_marks_translation_partial_with_original_fallback(self):
        originals = [segment(0, '你好'), segment(1, '再见')]
        result = self.run_calibration(originals, [change(text='Hello.')], target='en')
        self.assertEqual(result['status'], 'partial')
        self.assertEqual([item['text'] for item in result['segments']], ['Hello.', '再见'])
        self.assertTrue(result['concerns'])

    def test_wrong_target_language_translation_is_rejected(self):
        originals = [segment(text='你好')]
        result = self.run_calibration(originals, [change(text='您好')], target='en')
        self.assertEqual(result['segments'], originals)
        self.assertEqual(result['rejectedCount'], 1)
        self.assertEqual(result['status'], 'partial')

    def test_unknown_source_and_target_languages_never_call_model(self):
        for source, target in [('fr', 'source'), ('zh', 'fr')]:
            with self.subTest(source=source, target=target):
                originals = [segment()]
                result = calibration.calibrate_subtitles(source, originals, [], target,
                    ask_json=lambda _: self.fail('unsupported language must not call model'))
                self.assertEqual(result['status'], 'unsupported')
                self.assertEqual(result['segments'], originals)

    def test_empty_input_completes_without_calling_model(self):
        result = calibration.calibrate_subtitles('en', [], [], ask_json=lambda _: self.fail('no input'))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['segments'], [])
        self.assertEqual(result['changes'], [])
        self.assertEqual(result['usage']['requestCount'], 0)

    def test_unknown_ids_blank_reasons_and_duplicate_ids_cannot_overwrite_sources(self):
        originals = [segment(0), segment(1)]
        proposals = [change('invented'), change('t_0', reason=''),
                     change('t_1'), change('t_1', text='我望记吃饭了')]
        result = self.run_calibration(originals, proposals)
        self.assertEqual(result['segments'], originals)
        self.assertEqual(result['changes'], [])
        self.assertEqual(result['rejectedCount'], 4)

    def test_invented_ocr_time_or_quotation_rejects_entire_change(self):
        for reference in [{'sourceFrameTimeMs': 2000, 'text': '忘记吃饭'},
                          {'sourceFrameTimeMs': 1000, 'text': '模型编造的内容'}]:
            with self.subTest(reference=reference):
                originals = [segment()]
                result = self.run_calibration(originals, [change(evidence=[reference])], pages=[page()])
                self.assertEqual(result['segments'], originals)
                self.assertEqual(result['rejectedCount'], 1)

    def test_reference_from_unrelated_page_in_same_chunk_is_rejected(self):
        originals = [segment(0), segment(90)]
        reference = {'sourceFrameTimeMs': 90000, 'text': '忘记吃饭'}
        unrelated = page(first=89000, last=100000, frame=90000, index=2)
        result = self.run_calibration(originals, [change(evidence=[reference])], pages=[unrelated])
        self.assertEqual(result['segments'], originals)
        self.assertEqual(result['rejectedCount'], 1)

    def test_same_page_later_ocr_remains_eligible_as_context(self):
        reference = {'sourceFrameTimeMs': 50000, 'text': '忘记吃饭'}
        result = self.run_calibration([segment()], [change(evidence=[reference])],
                                      pages=[page(last=60000, frame=50000)])
        self.assertEqual(result['segments'][0]['text'], '我忘记吃饭了')
        self.assertEqual(result['changes'][0]['evidence'], [reference])

    def test_payload_uses_source_ocr_and_whitelisted_ids_without_derived_visual_claims(self):
        payloads = []
        def ask(payload):
            payloads.append(payload)
            return {'changes': []}
        calibration.calibrate_subtitles('zh', [segment()], [page()], ask_json=ask)
        sent = payloads[0]
        self.assertEqual(sent['allowedSegmentIds'], ['t_0'])
        self.assertEqual(sent['pageGroups'], [{'pageIndex': 1, 'firstFrameTimeMs': 0,
            'lastFrameTimeMs': 10000, 'ocrLines': [{'sourceFrameTimeMs': 1000, 'text': '忘记吃饭'}]}])
        self.assertNotIn('imageAnalysis', json.dumps(sent))
        self.assertNotIn('imagePath', json.dumps(sent))

    def test_page_understanding_is_sent_as_context_without_images_or_private_fields(self):
        p = page()
        p['ocrLines'] = []
        p['imageAnalysis'] = {'status': 'completed', 'title': '例三',
            'content': '讲解基期乘以增长率', 'visualElements': ['增长量=基期×增长率'],
            'uncertainties': ['批注不清楚'], 'imagePath': '/private/image.jpg', 'secret': 'hidden'}
        payloads = []
        calibration.calibrate_subtitles('zh', [segment()], [p],
            ask_json=lambda value: payloads.append(value) or {'changes': []})
        context = payloads[0]['pageGroups'][0]['imageAnalysis']
        self.assertEqual(context['content'], '讲解基期乘以增长率')
        self.assertEqual(context['uncertainties'], ['批注不清楚'])
        self.assertNotIn('imagePath', json.dumps(payloads))
        self.assertNotIn('secret', json.dumps(payloads))

    def test_text_route_context_is_kept_and_failed_image_interpretation_is_omitted(self):
        p = page()
        p['imageAnalysis'] = {'status': 'failed', 'content': 'bad guess'}
        p['textAnalysis'] = {'status': 'completed', 'content': '同页文字理解'}
        payloads = []
        calibration.calibrate_subtitles('zh', [segment()], [p],
            ask_json=lambda value: payloads.append(value) or {'changes': []})
        self.assertNotIn('imageAnalysis', payloads[0]['pageGroups'][0])
        self.assertEqual(payloads[0]['pageGroups'][0]['textAnalysis']['content'], '同页文字理解')

    def test_invalid_chunks_retry_three_times_then_continue_with_raw_fallback(self):
        calls = []
        def ask(payload):
            first = payload['allowedSegmentIds'][0]
            calls.append(first)
            if first == 't_50':
                return {'bad': 'schema'}
            return {'changes': []}
        originals = [segment(i) for i in range(101)]
        result = calibration.calibrate_subtitles('zh', originals, [], ask_json=ask, batch_size=50, concurrency=1)
        self.assertEqual(calls, ['t_0', 't_50', 't_50', 't_50', 't_100'])
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['segments'], originals)
        self.assertEqual(result['usage']['requestCount'], 5)
        self.assertEqual(result['usage']['successfulChunkCount'], 2)
        self.assertEqual(result['usage']['failedChunkCount'], 1)

    def test_chunk_context_does_not_allow_neighbor_edits(self):
        payloads = []
        def ask(payload):
            payloads.append(payload)
            if payload['allowedSegmentIds'][0] == 't_50':
                return {'changes': [change('t_49')]}
            return {'changes': []}
        originals = [segment(i) for i in range(51)]
        result = calibration.calibrate_subtitles('zh', originals, [], ask_json=ask, batch_size=50, concurrency=1)
        self.assertIn('t_49', [item['id'] for item in payloads[1]['contextSegments']])
        self.assertNotIn('t_49', payloads[1]['allowedSegmentIds'])
        self.assertEqual(result['segments'], originals)
        self.assertEqual(result['rejectedCount'], 1)

    def test_all_chunks_failing_returns_failed_and_preserves_every_segment(self):
        def ask(_):
            raise TimeoutError('provider timeout')
        originals = [segment()]
        result = calibration.calibrate_subtitles('zh', originals, [], ask_json=ask)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['segments'], originals)
        self.assertEqual(result['usage']['requestCount'], 3)
        self.assertTrue(result['concerns'])

    def test_transient_failure_retries_only_until_success(self):
        calls = []
        def ask(payload):
            calls.append(payload)
            if len(calls) == 1:
                raise TimeoutError('temporary')
            return {'changes': [change()]}
        result = calibration.calibrate_subtitles('zh', [segment()], [], ask_json=ask)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['segments'][0]['text'], '我忘记吃饭了')
        self.assertEqual(result['usage']['requestCount'], 2)

    def test_duplicate_original_ids_are_not_editable_and_original_order_is_kept(self):
        originals = [segment(5), segment(0), segment(0, '另一个字幕')]
        result = self.run_calibration(originals, [change('t_0')])
        self.assertEqual(result['segments'], originals)
        self.assertTrue(result['concerns'])

    def test_model_cannot_change_timestamps(self):
        proposed = {**change(), 'startMs': 120000, 'endMs': 130000}
        result = self.run_calibration([segment()], [proposed])
        self.assertEqual(result['segments'][0]['startMs'], 0)
        self.assertEqual(result['segments'][0]['endMs'], 900)


class SubtitleProviderTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(calibration, 'subtitle calibration module is not implemented')

    def test_provider_uses_existing_environment_and_keeps_usage_without_token_cap(self):
        bodies = []
        def open_request(request, timeout):
            bodies.append(json.loads(request.data))
            return response(json.dumps({'changes': [change()]}),
                            {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30})
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-only', 'DEEPSEEK_MODEL': 'configured-model'}), \
             patch.object(calibration, 'urlopen', side_effect=open_request):
            result = calibration.calibrate_subtitles('zh', [segment()], [])
        self.assertEqual(result['segments'][0]['text'], '我忘记吃饭了')
        self.assertEqual(result['modelId'], 'deepseek-test')
        self.assertEqual(result['usage']['prompt_tokens'], 20)
        self.assertEqual(result['usage']['completion_tokens'], 10)
        self.assertEqual(result['usage']['total_tokens'], 30)
        self.assertEqual(result['usage']['requestCount'], 1)
        self.assertEqual(len(bodies), 1)
        self.assertEqual(bodies[0]['model'], 'configured-model')
        self.assertNotIn('max_tokens', bodies[0])
        self.assertIsInstance(result['durationMs'], int)

    def test_provider_malformed_json_and_http_failure_share_total_three_attempts(self):
        def fake_open(request, timeout):
            body = json.loads(request.data)
            fake_open.calls.append(body)
            if len(fake_open.calls) == 1:
                raise HTTPError('https://example.test', 429, 'limited', {}, None)
            if len(fake_open.calls) == 2:
                return response('{bad')
            self.assertIn('responseRepair', json.loads(body['messages'][-1]['content']))
            return response('{"changes":[]}')
        fake_open.calls = []
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-only'}), \
             patch.object(calibration, 'urlopen', side_effect=fake_open), \
             patch.object(calibration.time, 'sleep'):
            result = calibration.calibrate_subtitles('zh', [segment()], [])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['usage']['requestCount'], 3)
        self.assertEqual(len(fake_open.calls), 3)

    def test_permanent_auth_failure_is_not_retried_or_leaked(self):
        calls = []
        def fake_open(request, timeout):
            calls.append(1)
            raise HTTPError('https://example.test', 401, 'private token text', {}, None)
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-only'}), \
             patch.object(calibration, 'urlopen', side_effect=fake_open):
            result = calibration.calibrate_subtitles('zh', [segment()], [])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(len(calls), 1)
        self.assertEqual(result['usage']['requestCount'], 1)
        self.assertNotIn('private token text', json.dumps(result))

    def test_provider_instructions_use_text_evidence_and_conservative_correction(self):
        bodies = []
        def fake_open(request, timeout):
            bodies.append(json.loads(request.data))
            return response('{"changes":[]}')
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-only'}), \
             patch.object(calibration, 'urlopen', side_effect=fake_open):
            calibration.calibrate_subtitles('zh', [segment()], [page()])
        instruction = bodies[0]['messages'][0]['content'].lower()
        self.assertIn('no access to audio', instruction)
        self.assertIn('no access to images', instruction)
        self.assertIn('untrusted data', instruction)
        self.assertIn('preserve meaning', instruction)
        self.assertIn('insertion', instruction)
        self.assertIn('uncertain', instruction)
        self.assertIn('single pass', instruction)
        self.assertIn('sufficient evidence', instruction)
        self.assertIn('minimal local edits', instruction)
        self.assertIn('do not add fillers', instruction)
        self.assertIn('at most one character', instruction)
        self.assertIn('phonetic plausibility is required', instruction)
        self.assertIn('ocr is not required', instruction)
        self.assertIn('ordinary language knowledge', instruction)
        self.assertIn('several different readings remain plausible', instruction)
        self.assertIn('never fabricate an ocr quotation', instruction)
        self.assertIn('no one-error-per-segment limit', instruction)
        self.assertIn('arithmetic operators', instruction)
        self.assertIn('references to numbered examples', instruction)
        self.assertIn('the same response', instruction)
        self.assertNotIn('final semantic review', instruction)


if __name__ == '__main__':
    unittest.main()
