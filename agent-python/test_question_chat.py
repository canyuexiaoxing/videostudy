import unittest
from question_chat import reply_to_question

class ChatTests(unittest.TestCase):
    def context(self):
        return {'question': {'prompt': '增长率？'}, 'feedback': {'selectedReason': '误用现期'},
                'evidence': [{'sourceId': 's1', 'startMs': 1000, 'endMs': 2000, 'quote': '分母是基期'}], 'pages': []}
    def test_rebuilds_citations_and_keeps_question_history(self):
        seen=[]
        def ask(payload):
            seen.append(payload)
            return {'reply': '你为什么用现期？', 'sourceIds': ['s1', 's1'], 'startMs': 99999}
        result=reply_to_question(self.context(), [{'role':'user','content':'上次问题'}], '我除以现期', ask)
        self.assertEqual(result['citations'], self.context()['evidence'])
        self.assertEqual(seen[0]['message'], '我除以现期')
        self.assertEqual(len(seen[0]['history']), 1)
    def test_rejects_invented_sources(self):
        with self.assertRaises(ValueError):
            reply_to_question(self.context(), [], '为什么', lambda p: {'reply':'解释','sourceIds':['fake']})
    def test_allows_clarification_without_claiming_evidence(self):
        self.assertEqual(reply_to_question(self.context(), [], '我猜的', lambda p: {'reply':'请说说思路','sourceIds':[]})['citations'], [])
    def test_bounds_message_and_history_before_provider(self):
        with self.assertRaises(ValueError): reply_to_question(self.context(), [], 'x'*2001, lambda p: self.fail())
        captured=[]
        reply_to_question(self.context(), [{'role':'user','content':str(i)} for i in range(30)], '为什么', lambda p: captured.append(p) or {'reply':'解释','sourceIds':[]})
        self.assertEqual(len(captured[0]['history']),12)
        with self.assertRaises(ValueError): reply_to_question(self.context(), [], '为什么', lambda p: {'reply':'','sourceIds':[]})

    def test_fastapi_route_uses_saved_context(self):
        from app import app
        import asyncio, json
        from unittest.mock import patch
        with patch('question_chat.ask_provider',return_value={'reply':'解释','sourceIds':['s1']}) as provider:
            events=[]
            async def receive():
                return {'type':'http.request','body':json.dumps({'context':self.context(),'history':[],'message':'为什么'}).encode(),'more_body':False}
            async def send(event): events.append(event)
            scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'POST','scheme':'http','path':'/question-chat','raw_path':b'/question-chat','query_string':b'','root_path':'','headers':[(b'content-type',b'application/json')],'server':('test',80),'client':('test',123)}
            asyncio.run(app(scope,receive,send))
        self.assertEqual(events[0]['status'],200)
        self.assertEqual(json.loads(events[1]['body'])['citations'],self.context()['evidence'])
        self.assertEqual(provider.call_count,1)


class CourseFirstChatTests(unittest.TestCase):
    def setUp(self):
        import tempfile,os,cv2,numpy as np
        from pathlib import Path
        from uuid import uuid4
        from unittest.mock import patch
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.course=str(uuid4());self.root=Path(self.tmp.name)/self.course;self.root.mkdir()
        self.env=patch.dict(os.environ,{'KEYFRAME_DIR':self.tmp.name});self.env.start();self.addCleanup(self.env.stop)
        for ms in [1000,2000,9000]:cv2.imwrite(str(self.root/f'{ms}.jpg'),np.full((40,80,3),ms//40%255,np.uint8))
        self.context={'courseId':self.course,'question':{'prompt':'请计算增长率'},'evidence':[{'sourceType':'transcript','sourceId':'s1','startMs':1000,'endMs':2000,'quote':'分母用基期'}],
                      'pages':[{'firstFrameTimeMs':1000,'lastFrameTimeMs':2000}],
                      '_imageCandidates':[1000,2000], '_ignoredRegion':None}
    def prepare(self,message):
        import question_chat
        return question_chat.prepare_course_context(self.context,message)
    def test_visual_followup_sends_only_related_real_images(self):
        text,images=self.prepare('老师这个公式的推导步骤是什么？')
        self.assertEqual([i['frameTimeMs'] for i in images],[1000,2000])
        self.assertNotIn('_imageCandidates',text)
        self.assertTrue(all(i['_bytes'].startswith(b'\xff\xd8') for i in images))
    def test_plain_followup_without_visual_need_stays_text_only(self):
        self.context['question']['prompt']='什么是基期？'
        text,images=self.prepare('基期这个词是什么意思？')
        self.assertEqual(images,[])
    def test_missing_or_invalid_image_is_disclosed_without_losing_text(self):
        (self.root/'1000.jpg').unlink();(self.root/'2000.jpg').write_bytes(b'not an image')
        text,images=self.prepare('看不懂老师的公式')
        self.assertEqual(images,[]);self.assertTrue(text['materialLimitations'])
        self.assertEqual(text['evidence'],self.context['evidence'])
    def test_invalid_course_path_never_loads_files(self):
        self.context['courseId']='../outside'
        text,images=self.prepare('解释这个图')
        self.assertEqual(images,[])
        self.assertTrue(text['materialLimitations'])
    def test_provider_receives_multimodal_content_and_course_first_policy(self):
        import json,os
        from unittest.mock import patch
        from question_chat import ask_provider,SYSTEM
        captured=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'reply':'解释','sourceIds':['s1']})}}],'usage':{'prompt_tokens':30,'completion_tokens':10}}).encode()
        text,images=self.prepare('解释老师的公式')
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'test-key'}),patch('question_chat.urlopen',side_effect=lambda request,**kw:captured.append(json.loads(request.data)) or Response()):
            ask_provider({'context':text,'history':[],'message':'解释老师的公式','_images':images})
        parts=captured[0]['messages'][1]['content']
        self.assertEqual(sum(p.get('type')=='image_url' for p in parts),2)
        self.assertIn('优先',SYSTEM);self.assertIn('补充解法',SYSTEM)
        self.assertNotIn('_bytes',parts[0]['text'])

    def test_saved_map_snapshot_supplies_only_matched_images_and_speech(self):
        import json
        from map_conversation import save_map_conversation
        result={'status':'completed','root':{'id':'root','title':'课程','children':[]},'createdAt':'test'}
        payload={'effectiveTranscript':[{'id':'s1','startMs':1000,'endMs':2000,'text':'本课方法'},{'id':'other','startMs':9000,'endMs':9500,'text':'其他内容'}]}
        save_map_conversation(self.root,payload,[(ms,None,None) for ms in [1000,2000,9000]],{'root':{}},result,'rules')
        self.context['_mapResult']=result;self.context['_imageCandidates']=[]
        text,images=self.prepare('老师的公式怎么推导？')
        self.assertEqual([i['frameTimeMs'] for i in images],[1000,2000])
        self.assertEqual([s['id'] for s in text['courseSpeech']],['s1'])
        self.assertNotIn('_mapResult',text)
    def test_changed_snapshot_image_is_omitted_and_disclosed(self):
        import cv2,numpy as np
        from map_conversation import save_map_conversation
        result={'status':'completed','root':{'id':'root','children':[]}}
        save_map_conversation(self.root,{},[(1000,None,None)],{},result,'rules')
        cv2.imwrite(str(self.root/'1000.jpg'),np.zeros((40,80,3),np.uint8))
        self.context['_mapResult']=result;self.context['_imageCandidates']=[1000]
        text,images=self.prepare('解释公式')
        self.assertEqual(images,[]);self.assertTrue(text['materialLimitations'])
    def test_image_budget_is_bounded(self):
        import cv2,numpy as np
        self.context['_imageCandidates']=list(range(1000,8000,1000))
        for ms in self.context['_imageCandidates']:cv2.imwrite(str(self.root/f'{ms}.jpg'),np.full((40,80,3),50,np.uint8))
        text,images=self.prepare('看不懂推导')
        self.assertEqual(len(images),4)


class ProviderRepairTests(unittest.TestCase):
    def run_provider(self, contents):
        import json, os
        from unittest.mock import patch
        from question_chat import ask_provider
        captured=[]
        class Response:
            def __init__(self, content):self.content=content
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':self.content}}]}).encode()
        def transport(request,**kw):
            captured.append(json.loads(request.data))
            return Response(contents[len(captured)-1])
        payload={'context':{'question':{'prompt':'test'},'evidence':[{'sourceId':'s1'}]},'history':[{'role':'user','content':'previous'}],'message':'why','_images':[{'imageId':'frame_0','_bytes':b'fixture'}]}
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'test-key'}),patch('question_chat.urlopen',side_effect=transport):
            try:result=ask_provider(payload)
            except ValueError as error:result=error
        return result,captured
    def test_unknown_evidence_repaired_in_same_context_once(self):
        import json
        invalid=json.dumps({'reply':'explain','sourceIds':['invented']})
        result,calls=self.run_provider([invalid,json.dumps({'reply':'fixed','sourceIds':['s1']})])
        self.assertEqual(result['sourceIds'],['s1']);self.assertEqual(len(calls),2)
        self.assertEqual(calls[1]['messages'][:2],calls[0]['messages'])
        self.assertEqual(calls[1]['messages'][2],{'role':'assistant','content':invalid})
        self.assertIn('s1',calls[1]['messages'][3]['content'])
        self.assertEqual(sum(p.get('type')=='image_url' for p in calls[1]['messages'][1]['content']),1)
    def test_invalid_json_and_required_fields_are_repaired(self):
        import json
        for invalid in ['{invalid',json.dumps({'reply':'missing sources'}),json.dumps({'reply':'','sourceIds':[]})]:
            with self.subTest(invalid=invalid):
                result,calls=self.run_provider([invalid,json.dumps({'reply':'fixed','sourceIds':[]})])
                self.assertEqual(result['reply'],'fixed');self.assertEqual(len(calls),2)
    def test_repeated_invalid_reply_stops_after_one_retry(self):
        import json
        invalid=json.dumps({'reply':'explain','sourceIds':['invented']})
        result,calls=self.run_provider([invalid,invalid])
        self.assertIsInstance(result,ValueError);self.assertEqual(len(calls),2)
    def test_http_failure_does_not_trigger_format_retry(self):
        import os
        from unittest.mock import patch
        from urllib.error import HTTPError
        from question_chat import ask_provider
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'test-key'}),patch('question_chat.urlopen',side_effect=HTTPError('https://example.invalid',401,'unauthorized',{},None)) as transport:
            with self.assertRaises(HTTPError):ask_provider({'context':{'evidence':[]}})
        self.assertEqual(transport.call_count,1)

    def test_valid_reply_has_no_extra_call(self):
        import json
        result,calls=self.run_provider([json.dumps({'reply':'ok','sourceIds':['s1']})])
        self.assertEqual(result['reply'],'ok');self.assertEqual(len(calls),1)
    def test_oversized_invalid_reply_is_not_echoed(self):
        import json
        result,calls=self.run_provider([json.dumps({'reply':'x'*20001,'sourceIds':[]})])
        self.assertIsInstance(result,ValueError);self.assertEqual(len(calls),1)
    def test_truncated_response_does_not_trigger_format_retry(self):
        import json,os
        from unittest.mock import patch
        from question_chat import ask_provider
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return json.dumps({'choices':[{'finish_reason':'length','message':{'content':'{unfinished'}}]}).encode()
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'test-key'}),patch('question_chat.urlopen',return_value=Response()) as transport:
            with self.assertRaisesRegex(ValueError,'finish_reason=length'):ask_provider({'context':{'evidence':[]}})
        self.assertEqual(transport.call_count,1)
