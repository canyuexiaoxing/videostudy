import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from overview import build_overview

class OverviewTests(unittest.TestCase):
    def test_receives_page_understanding_and_derives_citation_time(self):
        def ask(payload):
            self.assertEqual(payload['pages'][0]['understanding']['content'],'公式解释')
            return {'headline':'增长量课','summary':[{'text':'讲增长量','sourceIds':['s1'],'startMs':999}],
                    'objectives':[],'keyPoints':[],'pitfalls':[],'highlights':[],
                    'notes':[dict(title='增长量',sourceIds=['s1'],points=[dict(label='内容',text='讲增长量',sourceIds=['s1'])],children=[])]}
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

    def test_notes_use_map_structure_real_images_and_one_grounded_anchor(self):
        speech=[dict(id='s1',startMs=1000,endMs=5000,text='增长量介绍'),dict(id='s2',startMs=6000,endMs=9000,text='给基期增长率')]
        def ask(payload):
            self.assertEqual(payload['mindMap']['root']['title'],'增长量')
            return dict(headline='增长量',summary=[dict(text='课程介绍',sourceIds=['s1'])],objectives=[],keyPoints=[],pitfalls=[],highlights=[],notes=[dict(title='增长量计算',sourceIds=['s1'],imageIds=['frame_2000'],anchorSourceId='s1',points=[],children=[dict(title='给基期、增长率',sourceIds=['s2'],points=[dict(label='公式',text='基期乘增长率',sourceIds=['s2'])],children=[])])])
        result=build_overview(speech,[],ask,mind_map={'root':{'title':'增长量'}},visuals=[{'frameTimeMs':2000}])
        self.assertEqual(result['notes'][0]['anchor']['startMs'],1000)
        self.assertEqual(result['notes'][0]['image']['startMs'],2000)
        self.assertEqual(len(result['notes'][0]['children']),1)
        self.assertEqual(result['notes'][0]['children'][0]['anchor']['sourceId'],'s2')
    def test_unknown_note_image_and_anchor_are_rejected(self):
        from overview import _notes
        sources={'s1':dict(id='s1',startMs=0,endMs=1,text='介绍')}
        with self.assertRaises(ValueError):_notes([dict(title='课',sourceIds=['s1'],imageIds=['frame_999'],children=[])],sources,{})
        with self.assertRaises(ValueError):_notes([dict(title='课',sourceIds=['s1'],anchorSourceId='made_up',children=[])],sources,{})

    def test_validation_logs_stage_attempt_task_without_course_text(self):
        task='12345678-1234-1234-1234-123456789abc'
        def ask(payload):return dict(headline='课',summary=[dict(text='错误摘要',sourceIds=['missing'])],objectives=[],keyPoints=[],pitfalls=[],highlights=[])
        with self.assertLogs('uvicorn.error.overview',level='INFO') as captured:
            with self.assertRaises(ValueError):build_overview([dict(id='s',startMs=0,endMs=1,text='PRIVATE_COURSE_TEXT')],[],ask,course_id=task)
        output='\n'.join(captured.output)
        self.assertIn('task='+task,output);self.assertIn('stage=section_summary',output)
        self.assertIn('reason=Unknown evidence',output);self.assertIn('attempt=3',output)
        self.assertNotIn('PRIVATE_COURSE_TEXT',output)
    def test_unexpected_provider_error_does_not_log_sensitive_message(self):
        def ask(payload):raise RuntimeError('SECRET_KEY_PRIVATE_BODY')
        with self.assertLogs('uvicorn.error.overview',level='INFO') as captured:
            with self.assertRaises(RuntimeError):build_overview([dict(id='s',startMs=0,endMs=1,text='课')],[],ask)
        output='\n'.join(captured.output)
        self.assertIn('stage=provider_request',output);self.assertIn('retry=False',output)
        self.assertNotIn('SECRET_KEY_PRIVATE_BODY',output)
