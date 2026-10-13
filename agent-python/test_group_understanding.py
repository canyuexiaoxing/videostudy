"""Offline contracts for group evidence; providers below never access a network."""
import tempfile
import unittest
from pathlib import Path

try:
    from group_understanding import analyze_group
except ImportError:
    analyze_group = None


def group(index, ms, ready=True):
    return {'pageIndex': index, 'firstFrameTimeMs': ms, 'lastFrameTimeMs': ms,
            'memberFrameTimesMs': [ms], 'representativeFrameTimesMs': [ms],
            'ocrLines': [{'text': 'formula on slide', 'sourceFrameTimeMs': ms}], '_ready': ready}


def answer(**updates):
    return dict({'status': 'completed', 'knowledgeCandidates': [], 'exampleCandidates': [],
                 'connections': {}, 'uncertainties': []}, **updates)


def knowledge(ms=2000):
    return {'id': 'model-invented', 'title': 'a²+b²=c²', 'kind': 'formula',
            'details': [{'title': 'Right triangle only', 'sourceIds': [], 'imageIds': [f'frame_{ms}']}],
            'sourceIds': [], 'imageIds': [f'frame_{ms}']}


class GroupUnderstandingTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(analyze_group, 'group analysis module must be implemented')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pages = [group(1, 1000), group(2, 2000), group(3, 3000)]
        self.visuals = {ms: {'frameTimeMs': ms, 'ocrBlocks': [{'text': 'formula'}]}
                        for ms in (1000, 2000, 3000)}
        for ms in self.visuals:
            (self.root / f'{ms}.jpg').write_bytes(b'provider fixture')
        self.segments = [{'id': f's{n}', 'startMs': ms - 100, 'endMs': ms + 100,
                          'text': '不是任意三角形，仅直角三角形'}
                         for n, ms in enumerate(self.visuals, 1)]

    def run_group(self, provider, **kwargs):
        return analyze_group(self.pages[1], self.pages, self.visuals, self.root,
                             self.segments, ask_json=provider, **kwargs)

    def test_closed_tail_does_not_receive_future_speech_or_future_citations(self):
        self.pages=self.pages[:2];self.pages[-1]['_closedAtMs']=3000
        self.segments.append({'id':'future','startMs':6000,'endMs':7000,'text':'另一页题目'})
        calls=[]
        result=self.run_group(lambda p,imgs:calls.append(p) or answer(knowledgeCandidates=[
            {'title':'非法未来内容','kind':'concept','sourceIds':['future'],'imageIds':[],'details':[]}]))
        self.assertEqual(calls[0]['current']['speechWindowEndMs'],2500)
        self.assertNotIn('future',[s['id'] for s in calls[0]['current']['transcript']])
        self.assertEqual(result['groupUnderstanding']['knowledgeCandidates'],[])

    def test_formula_visible_but_not_spoken_is_grounded_and_program_ids(self):
        result = self.run_group(lambda p, imgs: answer(knowledgeCandidates=[knowledge()]))
        item = result['groupUnderstanding']['knowledgeCandidates'][0]
        self.assertEqual(item['id'], 'page_2_knowledge_1')
        self.assertEqual(item['sourceIds'], [])
        self.assertEqual(item['imageIds'], ['frame_2000'])
        self.assertIn('a²+b²=c²', result['imageAnalysis']['content'])
        self.assertEqual(result['imageAnalysis']['status'], 'completed')

    def test_payload_labels_current_and_neighbors_and_preserves_negation(self):
        calls = []
        self.run_group(lambda p, imgs: calls.append((p, imgs)) or answer())
        payload, imgs = calls[0]
        self.assertEqual(payload['current']['pageIndex'], 2)
        self.assertEqual(payload['previous']['pageIndex'], 1)
        self.assertEqual(payload['next']['pageIndex'], 3)
        self.assertEqual([(ms, detail) for ms, _, detail in imgs],
                         [(2000, 'original'), (1000, 'low'), (3000, 'low')])
        self.assertTrue(payload['current']['ocrLines'])
        self.assertEqual(payload['current']['transcript'][0]['id'], 's2')
        self.assertIn('不是', payload['current']['transcript'][0]['text'])

    def test_examples_stay_separate_from_core_knowledge(self):
        example = {'title': 'Example 2: data substitution', 'sourceIds': ['s2'], 'imageIds': []}
        result = self.run_group(lambda p, imgs: answer(exampleCandidates=[example]))
        self.assertEqual(result['groupUnderstanding']['knowledgeCandidates'], [])
        self.assertEqual(result['groupUnderstanding']['exampleCandidates'][0]['id'], 'page_2_example_1')

    def test_invalid_or_neighbor_only_citations_are_rejected(self):
        forged = knowledge(9999)
        wrong_page = knowledge(1000)
        missing_source = dict(knowledge(), sourceIds=['invented'])
        result = self.run_group(lambda p, imgs: answer(
            knowledgeCandidates=[forged, wrong_page, missing_source]))
        self.assertEqual(result['groupUnderstanding']['knowledgeCandidates'], [])
        self.assertEqual(result['groupUnderstanding']['status'], 'partial')
        self.assertEqual(result['groupUnderstanding']['forwardImageTimesMs'], [2000])

    def test_connection_requires_evidence_from_both_groups_and_reason(self):
        valid = {'relation': 'example_continuation', 'sourceIds': ['s1', 's2'],
                 'imageIds': [], 'reason': 'Speech explicitly continues the same numbered question'}
        result = self.run_group(lambda p, imgs: answer(connections={'previous': valid,
            'next': {'relation': 'knowledge_continuation', 'sourceIds': ['s2'],
                     'imageIds': [], 'reason': 'same subject'}}))
        links = result['groupUnderstanding']['connections']
        self.assertEqual(links['previous']['relation'], 'example_continuation')
        self.assertEqual(links['next']['relation'], 'uncertain')
        self.assertEqual(links['next']['sourceIds'], [])

    def test_empty_evidence_relationship_is_not_published(self):
        result = self.run_group(lambda p, imgs: answer(connections={'previous': {
            'relation': 'review', 'reason': 'guess', 'sourceIds': [], 'imageIds': []}}))
        self.assertEqual(result['groupUnderstanding']['connections']['previous']['relation'], 'uncertain')

    def test_not_ready_neighbor_is_placeholder_then_link_keeps_prior_candidates(self):
        self.pages[0]['_ready'] = False
        calls = []
        first = self.run_group(lambda p, imgs: calls.append((p, imgs)) or answer(
            knowledgeCandidates=[knowledge()]))
        self.assertFalse(calls[0][0]['previous']['ready'])
        self.assertNotIn(1000, [ms for ms, _, _ in calls[0][1]])
        self.pages[0]['_ready'] = True
        linked = self.run_group(lambda p, imgs: answer(connections={'previous': {
            'relation': 'knowledge_continuation', 'sourceIds': ['s1', 's2'], 'imageIds': [],
            'reason': 'Next step of the stated theorem'}}), phase='link', prior=first)
        self.assertEqual(linked['groupUnderstanding']['knowledgeCandidates'],
                         first['groupUnderstanding']['knowledgeCandidates'])
        self.assertEqual(linked['groupUnderstanding']['connections']['previous']['relation'],
                         'knowledge_continuation')

    def test_neighbor_hd_supplements_are_bounded_and_include_corresponding_speech(self):
        calls = []
        def provider(payload, imgs):
            calls.append((payload, imgs))
            return answer(supplementRequests=[{'side': 'previous', 'reason': 'missing question stem'},
                                              {'side': 'next', 'reason': 'missing derivation conclusion'}])
        result = self.run_group(provider, max_supplements=1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['groupUnderstanding']['supplementCount'], 1)
        self.assertEqual([detail for ms, _, detail in calls[1][1] if ms == 1000], ['original'])
        self.assertEqual(calls[1][0]['previous']['transcript'][0]['id'], 's1')
        self.assertEqual(result['groupUnderstanding']['status'], 'partial')

    def test_low_quality_and_provider_failure_forward_real_primary_image(self):
        for provider in (lambda p, imgs: answer(status='partial', uncertainties=['unreadable formula']),
                         lambda p, imgs: (_ for _ in ()).throw(TimeoutError('offline'))):
            with self.subTest(provider=provider):
                result = self.run_group(provider)
                self.assertEqual(result['groupUnderstanding']['forwardImageTimesMs'], [2000])
                self.assertIn(result['groupUnderstanding']['status'], ('partial', 'failed'))
                self.assertTrue(result['imageAnalysis']['uncertainties'])

    def test_failed_supplement_preserves_first_supported_candidates(self):
        calls = []
        def provider(p, imgs):
            calls.append(p)
            if len(calls) == 2:
                raise TimeoutError('offline')
            return answer(knowledgeCandidates=[knowledge()], supplementRequests=[
                {'side': 'previous', 'reason': 'missing question stem'}])
        result = self.run_group(provider)
        self.assertEqual(result['groupUnderstanding']['knowledgeCandidates'][0]['title'], 'a²+b²=c²')
        self.assertEqual(result['groupUnderstanding']['status'], 'partial')

    def test_ocr_only_never_sends_images_and_keeps_legacy_shape(self):
        calls = []
        result = self.run_group(lambda p, imgs: calls.append(imgs) or answer(
            knowledgeCandidates=[knowledge()]), mode='ocr_only')
        self.assertEqual(calls, [[]])
        self.assertIsNone(result['imageAnalysis'])
        self.assertIn('content', result['textAnalysis'])

    def test_cropped_out_ocr_cannot_be_cited(self):
        self.pages[1]['ocrLines'].append({'text': 'hidden', 'sourceFrameTimeMs': 9999})
        calls = []
        result = self.run_group(lambda p, imgs: calls.append(p) or answer(
            knowledgeCandidates=[knowledge(9999)]))
        self.assertNotIn(9999, [line['sourceFrameTimeMs'] for line in calls[0]['current']['ocrLines']])
        self.assertEqual(result['groupUnderstanding']['knowledgeCandidates'], [])

    def test_cancellation_prevents_provider_call(self):
        import threading
        signal = threading.Event()
        signal.set()
        result = self.run_group(lambda p, imgs: self.fail('cancelled request called provider'), signal=signal)
        self.assertEqual(result['groupUnderstanding']['status'], 'partial')

class GroupBoundaryRegressionTest(unittest.TestCase):
    setUp = GroupUnderstandingTest.setUp
    run_group = GroupUnderstandingTest.run_group

    def test_neighbor_with_two_representatives_promotes_only_one_hd_image_per_budget(self):
        self.pages[0]['memberFrameTimesMs'].append(1100)
        self.pages[0]['representativeFrameTimesMs'].append(1100)
        self.pages[0]['lastFrameTimeMs'] = 1100
        self.visuals[1100] = {'frameTimeMs': 1100, 'ocrBlocks': []}
        (self.root / '1100.jpg').write_bytes(b'fixture')
        calls = []
        def provider(p, imgs):
            calls.append(imgs)
            return answer(supplementRequests=[{'side': 'previous', 'reason': 'missing stem'}])
        self.run_group(provider, max_supplements=1)
        self.assertEqual(sum(detail == 'original' for ms, _, detail in calls[1] if ms != 2000), 1)

    def test_link_rejects_prior_from_another_page(self):
        prior = {'pageIndex': 99, 'groupUnderstanding': {'knowledgeCandidates': [
            dict(knowledge(), id='page_99_knowledge_1')], 'exampleCandidates': []}}
        result = self.run_group(lambda p, imgs: answer(), phase='link', prior=prior)
        self.assertEqual(result['groupUnderstanding']['knowledgeCandidates'], [])
        self.assertEqual(result['groupUnderstanding']['status'], 'partial')

    def test_invalid_detail_is_not_rendered_as_grounded_content(self):
        item = knowledge()
        item['details'].append({'title': 'Forged conclusion', 'sourceIds': ['outside'], 'imageIds': []})
        result = self.run_group(lambda p, imgs: answer(knowledgeCandidates=[item]))
        self.assertNotIn('Forged conclusion', result['imageAnalysis']['content'])
        self.assertEqual(result['groupUnderstanding']['status'], 'partial')

    def test_cancellation_during_provider_does_not_publish_response(self):
        import threading
        signal = threading.Event()
        def provider(p, imgs):
            signal.set()
            return answer(knowledgeCandidates=[knowledge()])
        result = self.run_group(provider, signal=signal)
        self.assertEqual(result['groupUnderstanding']['knowledgeCandidates'], [])
        self.assertEqual(result['groupUnderstanding']['status'], 'partial')

    def test_neighbor_preview_limits_boundary_speech_but_hd_restores_context(self):
        self.segments = [{'id': f'p{n}', 'startMs': n * 100, 'endMs': n * 100 + 99,
                          'text': 'boundary context'} for n in range(1, 15)] + self.segments[1:]
        calls = []
        def provider(p, imgs):
            calls.append(p)
            return answer(supplementRequests=[{'side': 'previous', 'reason': 'missing stem'}])
        self.run_group(provider, max_supplements=1)
        self.assertLessEqual(len(calls[0]['previous']['transcript']), 6)
        self.assertGreater(len(calls[1]['previous']['transcript']), 6)

    def test_malformed_provider_answer_remains_ui_readable(self):
        result = self.run_group(lambda p, imgs: ['not an object'])
        self.assertEqual(result['groupUnderstanding']['status'], 'failed')
        self.assertIsInstance(result['imageAnalysis']['content'], str)


if __name__ == '__main__':
    unittest.main()
