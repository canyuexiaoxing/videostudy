import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
class OverviewChatRouteTests(unittest.TestCase):
 def setUp(self):self.client=TestClient(app)
 def payload(self):return dict(courseId='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',overview={'status':'completed'},source={},history=[],message='why')
 def test_dispatches_followup_without_exposing_initial_material(self):
  with patch('overview_chat.reply_to_overview',return_value={'reply':'answer','citations':[],'contextMode':'original'}) as reply:
   result=self.client.post('/overview-chat',json=self.payload())
  self.assertEqual(result.status_code,200);self.assertNotIn('source',result.json());self.assertNotIn('overview',result.json());self.assertEqual(reply.call_args.args[-1],'why')
 def test_invalid_reply_and_request_rejected_without_model(self):
  with patch('overview_chat.reply_to_overview',side_effect=ValueError('invalid_chat_citation')):
   self.assertEqual(self.client.post('/overview-chat',json=self.payload()).status_code,422)
  payload=self.payload();payload['message']='x'*2001
  with patch('overview_chat.reply_to_overview') as reply:
   self.assertEqual(self.client.post('/overview-chat',json=payload).status_code,422);reply.assert_not_called()
