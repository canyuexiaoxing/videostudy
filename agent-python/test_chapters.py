import unittest
from chapters import build_chapters

class ChaptersTest(unittest.TestCase):
    def test_model_ids_become_contiguous_timeline_not_invented_times(self):
        segments = [{'id':'s1','startMs':1000,'endMs':5000,'text':'介绍'},
                    {'id':'s2','startMs':12000,'endMs':20000,'text':'例题'}]
        result = build_chapters(segments, [], ask_json=lambda _: {'chapters':[
            {'title':'介绍','sourceSegmentId':'s1','startMs':99999},
            {'title':'例题','sourceSegmentId':'s2'}]})
        self.assertEqual([(c['startMs'],c['endMs']) for c in result['chapters']], [(0,12000),(12000,20000)])
    def test_unknown_or_out_of_order_ids_are_retried_boundedly(self):
        calls=[]
        def ask(payload):
            calls.append(payload)
            return {'chapters':[{'title':'虚构','sourceSegmentId':'missing'}]}
        with self.assertRaises(ValueError):
            build_chapters([{'id':'s1','startMs':0,'endMs':1000,'text':'真实'}], [], ask_json=ask)
        self.assertEqual(len(calls),3)
    def test_empty_speech_is_explicit_without_api_call(self):
        result=build_chapters([],[],ask_json=lambda _:self.fail('no source'))
        self.assertEqual(result['status'],'empty')
