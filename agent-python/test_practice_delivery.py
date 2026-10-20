import copy,unittest
from practice import generate_practice,validate_question
import test_practice as fixtures
class PracticeDeliveryTests(unittest.TestCase):
 def setUp(self):self.fixture=fixtures.PracticeTests();self.nodes=copy.deepcopy(self.fixture.nodes)
 def q(self,i):
  q=self.fixture.question();q['prompt']=f'场景{i}：'+q['prompt'];return q
 def test_missing_auxiliary_fields_do_not_discard_good_question(self):
  q=self.q(1)
  for key in ('title','takeaway','distractorReasons'):q.pop(key)
  result=validate_question(q,self.nodes)
  self.assertEqual(result['answerIndex'],q['answerIndex']);self.assertEqual(len(result['distractorReasons']),4)
 def test_missing_machine_calculation_is_retained_but_not_claimed_checked(self):
  q=self.q(1);q.pop('calculation');result=validate_question(q,self.nodes)
  self.assertFalse(result['validation']['calculationChecked']);self.assertTrue(result['validation']['calculationMissing'])
 def test_incorrect_provided_calculation_still_rejected(self):
  q=self.q(1);q['calculation']['value']=999
  with self.assertRaisesRegex(ValueError,'wrong_calculation'):validate_question(q,self.nodes)
 def test_valid_reference_is_not_discarded_for_an_extra_unknown_reference(self):
  q=self.q(1);q['sourceIds'].append('invented');result=validate_question(q,self.nodes)
  self.assertEqual([r['sourceId'] for r in result['citations']],['s1'])
 def test_ten_is_target_and_one_same_context_fill_adds_only_missing_questions(self):
  calls=[]
  def ask(payload):
   calls.append(copy.deepcopy(payload));return {'questions':[self.q(i) for i in (range(6) if len(calls)==1 else range(6,10))]}
  result=generate_practice(self.nodes,[],10,'basic',ask)
  self.assertEqual(len(result['questions']),10);self.assertEqual(len(calls),2)
  self.assertEqual(calls[0]['requestedQuestions'],10);self.assertEqual(calls[1]['requestedQuestions'],4)
  self.assertEqual(calls[1]['_messages'][:len(calls[0]['_messages'])],calls[0]['_messages'])
  self.assertEqual(result['generatedCount'],10);self.assertEqual(result['fillAttempts'],1);self.assertEqual(result['shortfallCount'],0)
 def test_persistent_shortfall_is_reported_without_infinite_calls(self):
  calls=[]
  def ask(payload):calls.append(payload);return {'questions':[]}
  result=generate_practice(self.nodes,[],10,'basic',ask)
  self.assertEqual(len(calls),2);self.assertEqual(result['shortfallCount'],10);self.assertEqual(result['generatedCount'],0)
 def test_failed_fill_keeps_first_valid_questions(self):
  calls=[]
  def ask(payload):
   calls.append(payload)
   if len(calls)>1:raise TimeoutError()
   return {'questions':[self.q(1)]}
  result=generate_practice(self.nodes,[],3,'basic',ask)
  self.assertEqual(len(result['questions']),1);self.assertEqual(result['fillStatus'],'failed');self.assertEqual(result['shortfallCount'],2)
 def test_full_first_batch_avoids_second_call(self):
  calls=[]
  result=generate_practice(self.nodes,[],3,'basic',lambda p:calls.append(p) or {'questions':[self.q(i) for i in range(3)]})
  self.assertEqual(len(calls),1);self.assertEqual(result['fillAttempts'],0)

 def test_format_repair_budget_is_shared_with_quantity_fill(self):
  import io,json,os
  from unittest.mock import patch
  q=self.q(1);raw=json.dumps({'questions':[q]});bad=raw.replace('"questions":','"questions"',1);calls=[]
  def wire(request,timeout):
   calls.append(json.loads(request.data));reply=[bad,raw,'{"questions": ['][len(calls)-1]
   return io.BytesIO(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':reply}}]}).encode())
  with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'TEST_ONLY'}),patch('practice.urlopen',side_effect=wire):
   result=generate_practice(self.nodes,[],3,'basic')
  self.assertEqual(len(calls),3);self.assertEqual(len(result['questions']),1);self.assertEqual(result['fillStatus'],'failed')
