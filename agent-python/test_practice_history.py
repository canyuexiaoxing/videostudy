import copy,json,unittest
from practice import generate_practice
from practice_history import continue_messages,history_prompt_keys
import test_practice as fixtures

class PracticeHistoryTests(unittest.TestCase):
 def history(self):
  saved=fixtures.PracticeTests().question();saved['citations']=fixtures.PracticeTests.nodes[0]['evidenceRefs'];saved.pop('sourceIds')
  return [{'id':'old-set','request':{'scopeTitle':'增长率','difficulty':'basic','count':1},'questions':[saved]}]
 def test_recent_round_is_replayed_without_internal_validation_metadata(self):
  history=self.history();history[0]['questions'][0]['validation']={'PRIVATE_INTERNAL':True}
  base=[{'role':'system','content':'rules'},{'role':'user','content':'current'}]
  messages,stats=continue_messages(base,history)
  assistant=next(m for m in messages if m['role']=='assistant')
  question=json.loads(assistant['content'])['questions'][0]
  self.assertEqual(question['sourceIds'],['s1']);self.assertEqual(question['task'],'calculation')
  self.assertNotIn('validation',question);self.assertNotIn('citations',question)
  self.assertEqual(messages[-1],base[-1]);self.assertEqual(stats['history_rounds'],1)
 def test_previous_exact_question_is_rejected_but_new_variant_is_kept(self):
  old=fixtures.PracticeTests().question();new=copy.deepcopy(old);new['prompt']='另一种情景：从150增加到180，增长率是多少？'
  seen=[]
  def ask(payload):seen.append(payload);return {'questions':[old,new]}
  result=generate_practice(fixtures.PracticeTests.nodes,[],3,'basic',ask,history=self.history())
  self.assertEqual(len(result['questions']),1);self.assertEqual(result['rejectedCount'],1)
  self.assertIn('continuationInstruction',seen[0]);self.assertEqual(result['historyQuestions'],1)
 def test_long_history_is_bounded_and_old_rounds_are_summarized(self):
  history=self.history()*50
  messages,stats=continue_messages([{'role':'system','content':'rules'},{'role':'user','content':'current'}],history)
  self.assertEqual(sum(m['role']=='assistant' for m in messages),2)
  self.assertGreater(stats['history_summarized'],0);self.assertLessEqual(stats['history_characters'],22000)
 def test_question_keys_ignore_spacing_punctuation_and_case(self):
  history=self.history();history[0]['questions'][0]['prompt']='  ABC，增长率？ '
  self.assertIn('abc增长率',history_prompt_keys(history))

 def test_math_sign_change_is_not_an_exact_repeat(self):
  from practice_history import prompt_key
  self.assertNotEqual(prompt_key('计算 x+y'),prompt_key('计算 x-y'))

 def test_api_passes_history_to_generation_and_keeps_grounding_mode(self):
  from unittest.mock import patch
  from uuid import uuid4
  import app
  context={'systemText':'map rules','userText':'course','assistantText':'map reply','_images':[]}
  history=self.history()
  request=app.PracticeRequest(nodes=fixtures.PracticeTests.nodes,courseId=str(uuid4()),mode='map_context',mindMap={'root':{'id':'root'}},scopeNodeId='n1',practiceHistory=history)
  with patch('map_conversation.load_map_conversation',return_value=context),patch('practice.generate_practice',return_value={'status':'empty'}) as generate:
   app.practice(request)
  self.assertEqual(generate.call_args.kwargs['history'],history)
  self.assertEqual(generate.call_args.kwargs['mode'],'map_context')
 def test_history_log_does_not_include_question_body(self):
  from unittest.mock import patch
  seen=[]
  with patch('practice.record_event',side_effect=lambda *a,**kw:seen.append((a,kw))):
   generate_practice(fixtures.PracticeTests.nodes,[],1,'basic',lambda _: {'questions':[]},history=self.history())
  event=next(kwargs for args,kwargs in seen if kwargs.get('stage')=='history')
  self.assertEqual(event['history_questions'],1)
  self.assertNotIn(self.history()[0]['questions'][0]['prompt'],json.dumps(seen,ensure_ascii=False))

 def test_invalid_provider_json_has_specific_api_error_and_no_implicit_retry(self):
  from unittest.mock import patch
  import app
  from fastapi import HTTPException
  error=json.JSONDecodeError('Expecting value','PRIVATE_BODY',0)
  request=app.PracticeRequest(nodes=fixtures.PracticeTests.nodes)
  with patch('practice.generate_practice',side_effect=error) as generate:
   with self.assertRaises(HTTPException) as captured:app.practice(request)
  self.assertEqual(captured.exception.detail,'practice_provider_invalid_json');self.assertEqual(generate.call_count,1)
