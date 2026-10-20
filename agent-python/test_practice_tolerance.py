import copy,json,unittest
import test_practice as fixtures
from practice import generate_practice,validate_question
from practice_reply import PracticeReplyError,readable_original_questions,repair_instruction,parse_practice_reply
class PracticeToleranceTests(unittest.TestCase):
 def setUp(self):self.f=fixtures.PracticeTests();self.nodes=self.f.nodes
 def test_text_comparison_options_are_kept_without_claiming_numeric_mapping(self):
  q=self.f.question();q.update(options=['甲商店，增长30件','乙商店，增长20件','两商店增长量相同','无法比较'],answerIndex=0,calculation={'expression':'150-120','value':30,'optionValues':[30,20,0,0]})
  result=validate_question(q,self.nodes);self.assertFalse(result['validation']['optionValuesChecked']);self.assertTrue(result['validation']['calculationChecked'])
 def test_explanation_cannot_change_the_question_when_option_missing(self):
  q=self.f.question();q['explanation']='甲今年500，乙今年250，差250元。选项无250。重新设问：改问增长量之差，答案50元。'
  with self.assertRaisesRegex(ValueError,'question_answer_conflict'):validate_question(q,self.nodes)
 def test_normal_revised_method_explanation_is_retained(self):
  q=self.f.question();q['explanation']='不要把增长量误当增长率，应重新计算：(180-150)/150=20%。'
  validate_question(q,self.nodes)
 def test_close_to_reference_count_does_not_make_another_request(self):
  calls=[]
  def provider(p):
   calls.append(p);qs=[]
   for i in range(8):q=self.f.question();q['prompt']=str(i)+q['prompt'];qs.append(q)
   return {'questions':qs}
  result=generate_practice(self.nodes,[],10,'basic',provider)
  self.assertEqual(len(calls),1);self.assertEqual(len(result['questions']),8)
 def test_bad_numeric_literal_does_not_lose_other_complete_questions(self):
  good=json.dumps(self.f.question(),ensure_ascii=False);bad=good.replace('"value": 20','"value": 1/5')
  source='{"questions":['+good+','+bad+','+good+']}'
  try:parse_practice_reply(source)
  except PracticeReplyError as e:error=e
  recovered=readable_original_questions(error)
  self.assertEqual(len(recovered['questions']),2);self.assertEqual(recovered['unreadableCount'],1)
 def test_duplicate_top_level_fields_are_never_salvaged(self):
  self.assertIsNone(readable_original_questions(PracticeReplyError('{"questions":[],"questions":[{}]}',['duplicate_field'])))
 def test_repair_contains_exact_syntax_location_and_numeric_requirement(self):
  try:parse_practice_reply('{"questions": [1/2]}')
  except PracticeReplyError as e:error=e
  instruction=repair_instruction(error);self.assertIn('列',instruction);self.assertIn('数值',instruction)
