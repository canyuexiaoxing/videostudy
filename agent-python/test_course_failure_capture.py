import json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request
from course_reply_repair import parse_map_reply,repair_instruction,preserves_reply
from model_diagnostics import request_model_json,close_logs
import course_failure_capture as capture

class FailureCaptureTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  env=patch.dict(os.environ,{'MODEL_LOG_DIR':str(self.root/'logs'),'DEEPSEEK_API_KEY':'TEST_SECRET_12345','MODEL_FAILURE_CAPTURE':'1'});env.start();self.addCleanup(env.stop);self.addCleanup(close_logs)
 def reply(self,text):
  class Response:
   status=200
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':text}}]}).encode()
  return lambda *a,**k:Response()
 def files(self):return list((self.root/'logs/private-model-failures').glob('*.json'))
 def invoke(self,text,operation='course_map'):
  return request_model_json(Request('https://test.invalid',headers={'Authorization':'Bearer TEST_SECRET_12345'}),30,'11111111-1111-1111-1111-111111111111',operation,transport=self.reply(text),content_parser=parse_map_reply)
 def test_failed_model_reply_is_separate_and_linked_to_request(self):
  with self.assertRaises(ValueError):self.invoke('{"topic":"PRIVATE_COURSE"} }')
  files=self.files();self.assertEqual(len(files),1);saved=json.loads(files[0].read_text());self.assertIn('PRIVATE_COURSE',saved['response']);self.assertIn('issues',saved)
  events=[json.loads(l) for l in (self.root/'logs/model-events.jsonl').read_text().splitlines()]
  self.assertEqual(saved['requestId'],next(e['request_id'] for e in events if e['event']=='request_started'))
  self.assertNotIn('PRIVATE_COURSE',json.dumps(events));self.assertNotIn('TEST_SECRET',files[0].read_text())
 def test_incomplete_response_capture_keeps_finish_reason(self):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self):return json.dumps({'choices':[{'finish_reason':'length','message':{'content':'{"topic":"PRIVATE_PARTIAL'}}]}).encode()
  with self.assertRaisesRegex(ValueError,'finish_reason=length'):
   request_model_json(Request('https://test.invalid'),30,'unbound','course_map',transport=lambda *a,**k:Response())
  saved=json.loads(self.files()[0].read_text());self.assertEqual(saved['finishReason'],'length');self.assertEqual(saved['stage'],'finish_check')
 def test_success_and_other_operations_do_not_save_bodies(self):
  self.invoke('{"topic":"x","children":[],"examples":[]}')
  with self.assertRaises(ValueError):self.invoke('bad','practice')
  self.assertEqual(self.files(),[])
 def test_key_and_bearer_are_redacted_without_mutating_error(self):
  text='{"topic":"TEST_SECRET_12345 sk-abcdef0123456789 Authorization: Bearer private-token-123"} ,'
  try:parse_map_reply(text)
  except ValueError as error:capture.save_failure(error,task='unbound',request_id='00000000-0000-0000-0000-000000000000',stage='model_json',finish_reason='stop');self.assertEqual(error.doc,text)
  saved=json.loads(self.files()[0].read_text());self.assertTrue(saved['redacted']);self.assertNotIn('TEST_SECRET',saved['response']);self.assertNotIn('sk-abcdef',saved['response']);self.assertNotIn('private-token',saved['response'])
 def test_retention_is_bounded_and_expired_removed(self):
  for i in range(5):
   try:parse_map_reply('{} ,')
   except ValueError as error:
    with patch.object(capture,'MAX_FILES',2):capture.save_failure(error,task='unbound',request_id=str(i),stage='model_json',finish_reason='stop')
  self.assertEqual(len(self.files()),2)
  old=self.files()[0];os.utime(old,(0,0))
  try:parse_map_reply('{} ,')
  except ValueError as error:
   with patch.object(capture,'MAX_FILES',2):capture.save_failure(error,task='unbound',request_id='x',stage='model_json',finish_reason='stop')
  self.assertFalse(old.exists());self.assertLessEqual(len(self.files()),2)
 def test_oversize_and_disabled_never_save_partial_response(self):
  try:parse_map_reply('{} ,')
  except ValueError as error:
   with patch.object(capture,'MAX_FILE_BYTES',1):self.assertIsNone(capture.save_failure(error,task='unbound',request_id='x',stage='model_json',finish_reason='stop'))
   with patch.dict(os.environ,{'MODEL_FAILURE_CAPTURE':'0'}):self.assertIsNone(capture.save_failure(error,task='unbound',request_id='x',stage='model_json',finish_reason='stop'))
  self.assertEqual(self.files(),[])
 def test_disk_error_does_not_replace_original_failure(self):
  with patch('course_failure_capture.Path.mkdir',side_effect=OSError('PRIVATE_PATH')):
   with self.assertRaises(ValueError) as error:self.invoke('{} ,')
  self.assertTrue(hasattr(error.exception,'issues'));self.assertEqual(self.files(),[])

class FormatBoundaryTests(unittest.TestCase):
 def good(self):return {'topic':'course','children':[{'title':'x = \\frac{1}{2}','children':[],'sourceIds':['t_1']}],'examples':[]}
 def instruction(self,text):
  try:parse_map_reply(text)
  except ValueError as error:return repair_instruction(error)
  self.fail('expected invalid format')
 def test_trailing_classification_contains_no_course_text(self):
  prefix=json.dumps(self.good())
  for suffix,kind in [(' ,','separators_only'),(' }]','extra_closing_delimiters'),(' {"secret":"PRIVATE"}','second_json_object'),(' PRIVATE_TAIL','text_or_other')]:
   info=self.instruction(prefix+suffix)['trailingContentRepair'];self.assertEqual(info['trailingKind'],kind);self.assertNotIn('PRIVATE',json.dumps(info));self.assertEqual(info['completedRootEndCharacter'],len(prefix))
 def test_redundant_closers_can_be_verified_but_not_silently_parsed(self):
  good=self.good();text=json.dumps(good)+' } ] ,'
  with self.assertRaises(ValueError):parse_map_reply(text)
  self.assertTrue(preserves_reply(text,good))
  changed=self.good();changed['children'][0]['title']='changed';self.assertFalse(preserves_reply(text,changed))
 def test_distinct_document_text_or_ambiguous_early_closure_cannot_be_removed(self):
  good=self.good();prefix=json.dumps(good)
  for suffix in [' {"topic":"other","children":[],"examples":[]}',' "PRIVATE_TEXT"',' , "children":[{"title":"LOST"}]}',' [ ]']:
   self.assertFalse(preserves_reply(prefix+suffix,good))

if __name__=='__main__':unittest.main()
