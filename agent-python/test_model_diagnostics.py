import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request
from urllib.error import HTTPError
from model_diagnostics import request_model_json,close_logs

class DiagnosticsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.env=patch.dict(os.environ,{'MODEL_LOG_DIR':self.tmp.name});self.env.start();self.addCleanup(self.env.stop);self.addCleanup(close_logs)
 def reply(self,envelope):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self):return json.dumps(envelope).encode()
  return lambda *args,**kwargs:Response()
 def rows(self):return [json.loads(line) for line in (Path(self.tmp.name)/'model-events.jsonl').read_text().splitlines()]
 def test_completed_response_records_usage_not_content_or_credentials(self):
  body='{"secret_course_text":"PRIVATE"}'
  envelope={'choices':[{'finish_reason':'stop','message':{'content':body}}],'usage':{'prompt_tokens':50,'completion_tokens':12,'total_tokens':62}}
  req=Request('https://provider.invalid',data=b'PRIVATE_IMAGE_BASE64',headers={'Authorization':'Bearer SECRET_KEY'})
  value=request_model_json(req,30,'unbound','course_map',transport=self.reply(envelope),image_count=4,input_characters=99,output_limit=393216)
  self.assertEqual(value,{'secret_course_text':'PRIVATE'})
  rows=self.rows();self.assertEqual(rows[0]['max_output_tokens'],393216);self.assertEqual(rows[0]['timeout_seconds'],30);self.assertEqual(rows[1]['finish_reason'],'stop');self.assertEqual(rows[1]['completion_tokens'],12)
  self.assertEqual(rows[1]['response_characters'],len(body));text=json.dumps(rows)
  for private in ('PRIVATE','SECRET_KEY','PRIVATE_IMAGE_BASE64'):self.assertNotIn(private,text)
 def test_length_reason_is_saved_and_exposed_without_retry(self):
  envelope={'choices':[{'finish_reason':'length','message':{'content':'partial private reply'}}],'usage':{'completion_tokens':4096}}
  with self.assertRaisesRegex(ValueError,'finish_reason=length'):
   request_model_json(Request('https://provider.invalid'),30,'unbound','course_map',transport=self.reply(envelope))
  rows=self.rows();self.assertEqual(rows[1]['finish_reason'],'length');self.assertEqual(rows[-1]['stage'],'finish_check')
 def test_http_failure_records_status_without_error_body(self):
  def fail(*args,**kwargs):raise HTTPError('https://provider.invalid',402,'PRIVATE PAYMENT DETAIL',{},None)
  with self.assertRaises(HTTPError):request_model_json(Request('https://provider.invalid'),30,'unbound','practice',transport=fail)
  rows=self.rows();self.assertEqual(rows[-1]['http_status'],402);self.assertNotIn('PRIVATE',json.dumps(rows))

 def test_invalid_model_json_logs_position_without_private_reply(self):
  body='{"questions": [PRIVATE_REPLY]}'
  envelope={'choices':[{'finish_reason':'stop','message':{'content':body}}]}
  with self.assertRaises(json.JSONDecodeError):
   request_model_json(Request('https://provider.invalid'),30,'unbound','practice',transport=self.reply(envelope))
  failure=self.rows()[-1]
  self.assertEqual(failure['reason'],'invalid_json');self.assertGreater(failure['json_column'],0)
  self.assertEqual(failure['stage'],'model_json');self.assertNotIn('PRIVATE_REPLY',json.dumps(self.rows()))
