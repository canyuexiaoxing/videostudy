import json,unittest
from unittest.mock import patch
from overview import build_overview,_ask

SPEECH=[dict(id='s1',startMs=1000,endMs=3000,text='增长量为现期减基期')]
def response(notes=True):
 result=dict(headline='增长量课程',summary=[dict(text='介绍增长量计算',sourceIds=['s1'])],objectives=[],keyPoints=[],pitfalls=[],highlights=[])
 if notes:result['notes']=[dict(title='增长量计算',sourceIds=['s1'],anchorSourceId='s1',points=[dict(label='公式',text='增长量等于现期减基期',sourceIds=['s1'])],children=[])]
 return result

class RequiredNotesTests(unittest.TestCase):
 def test_missing_notes_repaired_even_without_map(self):
  calls=[]
  def ask(payload):
   calls.append(payload)
   if len(calls)==1:return response(False)
   self.assertIn('notes',payload['repairInstruction'])
   self.assertIn('Missing course notes',payload['repairInstruction'])
   return response()
  result=build_overview(SPEECH,[],ask)
  self.assertEqual(len(calls),2);self.assertTrue(result['notes'][0]['points'])
 def test_repeated_empty_notes_fail_with_bounded_retries(self):
  calls=[]
  def ask(payload):
   calls.append(payload);result=response();result['notes']=[];return result
  with self.assertRaisesRegex(ValueError,'Missing course notes'):build_overview(SPEECH,[],ask)
  self.assertEqual(len(calls),3)
 def test_title_only_is_not_a_successful_notebook(self):
  def ask(payload):
   result=response();result['notes'][0]['points']=[];return result
  with self.assertRaisesRegex(ValueError,'Missing note content'):build_overview(SPEECH,[],ask)
 def test_output_contract_explicitly_includes_required_notes(self):
  with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'TEST_ONLY'}),patch('overview.request_model_json',return_value=response()) as transport:
   _ask({'speech':[['s1',1000,3000,'test']]})
  body=json.loads(transport.call_args.args[0].data)
  prompt=body['messages'][0]['content']
  self.assertIn('notes',prompt[prompt.index('输出中文 JSON'):])
  self.assertIn('必须',prompt)
