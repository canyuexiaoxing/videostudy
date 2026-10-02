"""Check that compact API evidence is smaller and remains lossless."""
import json
import unittest


class EvidencePayloadTest(unittest.TestCase):
    def test_page_rows_preserve_every_word_and_timestamp_without_mutating_source(self):
        from evidence_payload import compact_payload
        payload = {'route': 'ocr_only', 'transcript': [
            {'startMs': 1000, 'endMs': 1500, 'text': '25＋231×9＝2104'},
            {'startMs': 1500, 'endMs': 2500, 'text': '2104－1987＝117'}],
            'ocrLines': [{'text': '增长量', 'sourceFrameTimeMs': 1000},
                         {'text': '增长量', 'sourceFrameTimeMs': 2000}],
            'verification': {'reasons': ['conflict']}}
        before = json.dumps(payload, ensure_ascii=False)
        compact = compact_payload(payload)
        for name in ('transcript', 'ocrLines'):
            table = compact[name]
            self.assertEqual([dict(zip(table['columns'], row)) for row in table['rows']], payload[name])
        self.assertEqual(compact['verification'], {'reasons': ['conflict']})
        self.assertEqual(json.dumps(payload, ensure_ascii=False), before)

    def test_repeated_ocr_strings_are_sent_once_but_every_frame_keeps_order_and_time(self):
        from evidence_payload import compact_payload
        payload = {'ocrFrames': [
            {'frameTimeMs': 1000, 'texts': ['题干', '25＋231×9', '题干']},
            {'frameTimeMs': 2000, 'texts': ['题干', '25＋231×9', '2104']} ]}
        compact = compact_payload(payload)
        self.assertEqual(compact['ocrTextDictionary'], ['题干', '25＋231×9', '2104'])
        restored = [{'frameTimeMs': row[0], 'texts': [compact['ocrTextDictionary'][i] for i in row[1]]}
                    for row in compact['ocrFrames']['rows']]
        self.assertEqual(restored, payload['ocrFrames'])

    def test_many_segments_and_repeated_frames_have_smaller_request_text(self):
        from evidence_payload import compact_payload
        payload = {'transcript': [{'id': f't_{i}', 'startMs': i*1000, 'endMs': (i+1)*1000,
                                  'text': '增长量等于现期减基期'} for i in range(80)],
                   'ocrFrames': [{'frameTimeMs': i*2000,
                                  'texts': ['增长量等于现期减基期', '25＋231×9＝2104']} for i in range(40)]}
        compact = compact_payload(payload)
        self.assertLess(len(json.dumps(compact, ensure_ascii=False)),
                        len(json.dumps(payload, ensure_ascii=False)) * .7)


if __name__ == '__main__':
    unittest.main()
