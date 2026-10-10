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
