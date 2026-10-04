import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from overview import build_overview

class OverviewTests(unittest.TestCase):
    def test_receives_page_understanding_and_derives_citation_time(self):
        def ask(payload):
            self.assertEqual(payload['pages'][0]['understanding']['content'],'公式解释')
            return {'headline':'增长量课','summary':[{'text':'讲增长量','sourceIds':['s1'],'startMs':999}],
                    'objectives':[],'keyPoints':[],'pitfalls':[],'highlights':[]}
        result=build_overview([{'id':'s1','startMs':1000,'endMs':5000,'text':'讲增长量'}],
            [{'pageIndex':1,'imageAnalysis':{'content':'公式解释'}}],ask)
        self.assertEqual(result['summary'][0]['citations'][0]['startMs'],1000)
    def test_invalid_citation_has_bounded_retries(self):
        calls=[]
        def ask(payload):
            calls.append(payload)
            return {'headline':'课','summary':[{'text':'假引用','sourceIds':['missing']}],
                    'objectives':[],'keyPoints':[],'pitfalls':[],'highlights':[]}
        with self.assertRaises(ValueError): build_overview([{'id':'s','startMs':0,'endMs':1,'text':'课'}],[],ask)
        self.assertEqual(len(calls),3)
    def test_empty_course_does_not_call_model(self):
        self.assertEqual(build_overview([],[],lambda _:self.fail())['status'],'empty')
    def test_payment_error_does_not_loop_or_fail_main_analysis(self):
        from overview import safe_overview
        with patch('overview._ask',side_effect=HTTPError('https://provider.invalid',402,'Payment Required',{},None)) as ask:
            result=safe_overview([{'id':'s','startMs':0,'endMs':1,'text':'课'}],[])
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['error'],'overview_provider_payment_required')
        self.assertEqual(ask.call_count,1)
