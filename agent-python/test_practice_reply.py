"""Model wire replies, format-only repair, and existing question validators."""
import copy,io,json,os,tempfile,unittest
from unittest.mock import patch
from urllib.error import HTTPError
from practice import ask,generate_practice
import test_practice as fixtures
import test_practice_diagrams as diagram_fixtures

class PracticeReplyTests(unittest.TestCase):
 def setUp(self):
  self.calls=[];self.folder=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'DEEPSEEK_API_KEY':'TEST_ONLY','MODEL_LOG_DIR':self.folder.name});self.env.start()
 def tearDown(self):
  from model_diagnostics import close_logs
  close_logs();self.env.stop();self.folder.cleanup()
 def question(self):
  q=fixtures.PracticeTests().question();q['prompt']=r'计算增长率 \(\frac{180-150}{150}\times100\%\)。';return q
 def wire(self,replies):
  def transport(request,timeout):
   self.calls.append(json.loads(request.data));item=replies[len(self.calls)-1]
   if isinstance(item,Exception):raise item
   return io.BytesIO(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':item}}]}).encode())
  return patch('practice.urlopen',side_effect=transport)
 def run_question(self,replies,q=None):
  with self.wire(replies):return generate_practice(fixtures.PracticeTests.nodes,[],3,'basic')
 def test_illegal_latex_escapes_are_repaired_without_another_call(self):
  raw=json.dumps({'questions':[self.question()]},ensure_ascii=False).replace('\\\\','\\')
  result=self.run_question([raw]);self.assertEqual(len(result['questions']),1);self.assertEqual(result['questions'][0]['prompt'],self.question()['prompt']);self.assertEqual(len(self.calls),1)
 def test_valid_json_escapes_are_not_corrupted(self):
  q=self.question();q['prompt']+='\n他说："先量后率"。路径 C:\\notes\\lesson；Unicode 中文。'
  result=self.run_question([json.dumps({'questions':[q]})]);self.assertEqual(result['questions'][0]['prompt'],q['prompt']);self.assertEqual(len(self.calls),1)
 def test_legal_json_but_corrupted_fraction_and_theta_are_recovered(self):
  q=self.question();q['prompt']=r'公式 \(\frac{1}{2}+\theta+\begin{matrix}1\end{matrix}+\underbrace{x}+\upsilon\)。'
  raw=json.dumps({'questions':[q]}).replace(r'\\frac',r'\frac').replace(r'\\theta',r'\theta').replace(r'\\begin',r'\begin').replace(r'\\underbrace',r'\underbrace').replace(r'\\upsilon',r'\upsilon')
  result=self.run_question([raw]);self.assertEqual(result['questions'][0]['prompt'],q['prompt']);self.assertEqual(len(self.calls),1)
 def test_same_conversation_repair_once_retains_images_and_history(self):
  q=self.question();raw=json.dumps({'questions':[q]});bad=raw.replace('"questions":','"questions"',1)
  initial=[{'role':'system','content':'practice schema'},{'role':'user','content':[{'type':'text','text':'course material'},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,TEST_ONLY'}}]},{'role':'assistant','content':'earlier accepted questions'},{'role':'user','content':'current request'}]
  with self.wire([bad,raw]):value=ask({'_messages':initial,'_diagnosticTaskId':'course-test'})
  self.assertEqual(value['questions'][0]['prompt'],q['prompt']);self.assertEqual(len(self.calls),2);repair=self.calls[1]['messages'];self.assertEqual(repair[:len(initial)],initial);self.assertEqual(repair[-2],{'role':'assistant','content':bad});self.assertIn('JSON',repair[-1]['content']);self.assertEqual(initial[-1]['content'],'current request')
 def test_missing_fields_repaired_together_without_changing_existing_values(self):
  q=self.question();bad=copy.deepcopy(q);del bad['takeaway'];del bad['distractorReasons']
  result=self.run_question([json.dumps({'questions':[bad]}),json.dumps({'questions':[q]})]);self.assertEqual(len(result['questions']),1);self.assertEqual(len(self.calls),2);instruction=self.calls[1]['messages'][-1]['content'];self.assertIn('takeaway',instruction);self.assertIn('distractorReasons',instruction)
 def test_repair_does_not_accept_changed_answers(self):
  q=self.question();bad=json.dumps({'questions':[q]}).replace('"questions":','"questions"',1);changed=copy.deepcopy(q);changed['answerIndex']=0
  with self.assertRaises(ValueError):self.run_question([bad,json.dumps({'questions':[changed]})])
  self.assertEqual(len(self.calls),2)
 def test_second_bad_response_stops_after_one_repair(self):
  with self.assertRaises(ValueError):self.run_question(['{"questions": [','{"questions": ['])
  self.assertEqual(len(self.calls),2)
 def test_network_failure_does_not_trigger_format_repair(self):
  with self.assertRaises(HTTPError):self.run_question([HTTPError('https://test.invalid',429,'rate limited',{},None)])
  self.assertEqual(len(self.calls),1)
 def test_wrong_answers_and_invented_evidence_still_rejected_without_retry(self):
  for field,value in [('answerIndex',3),('sourceIds',['invented'])]:
   self.calls=[];q=self.question();q[field]=value;result=self.run_question([json.dumps({'questions':[q]})]);self.assertEqual(result['questions'],[]);self.assertEqual(len(self.calls),1)
 def test_true_false_and_all_structured_diagram_kinds(self):
  diagrams=[None,{'kind':'function','domain':[-2,2],'range':[-1,5],'curves':[{'expression':'x**2'}]}, {'kind':'geometry','points':[{'id':'A','x':0,'y':0},{'id':'B','x':3,'y':0}],'edges':[{'from':'A','to':'B'}]},diagram_fixtures.StructuredDiagramTests().circuit()]
  diagrams[-1].pop('check')
  for kind in ['bar','line','table','pie']:diagrams.append({'kind':kind,'values':[{'label':'A','value':1},{'label':'B','value':2}]})
  diagrams.append({'kind':'scatter','values':[{'label':'A','x':0,'y':1},{'label':'B','x':1,'y':2}]})
  for diagram in diagrams:
   with self.subTest(kind=diagram and diagram['kind']):
    self.calls=[];q=self.question();q.update(kind='true_false',task='concept',options=['正确','错误'],answerIndex=0,distractorReasons=['','原因'],calculation=None,diagram=diagram)
    raw=json.dumps({'questions':[q]}).replace('\\\\','\\');result=self.run_question([raw]);self.assertEqual(len(result['questions']),1);self.assertEqual(result['questions'][0]['validation']['diagramChecked'],diagram is not None);self.assertEqual(len(self.calls),1)
 def test_invalid_diagram_references_still_rejected_without_retry(self):
  q=self.question();q['diagram']={'kind':'geometry','points':[{'id':'A','x':0,'y':0}],'edges':[{'from':'A','to':'missing'}]};result=self.run_question([json.dumps({'questions':[q]})]);self.assertEqual(result['questions'],[]);self.assertEqual(len(self.calls),1)
 def test_dollar_math_and_matrix_linebreaks(self):
  q=self.question();q['prompt']=r'公式 $\frac{1}{2}+\theta$，矩阵 $$\begin{matrix}1&2\\3&4\end{matrix}$$。'
  raw=json.dumps({'questions':[q]}).replace(r'\\frac',r'\frac').replace(r'\\theta',r'\theta').replace(r'\\begin',r'\begin').replace(r'\\underbrace',r'\underbrace').replace(r'\\upsilon',r'\upsilon')
  result=self.run_question([raw]);self.assertEqual(result['questions'][0]['prompt'],q['prompt']);self.assertEqual(len(self.calls),1)
 def test_repair_cannot_change_diagram_data_or_option_order(self):
  for field in ['diagram','options']:
   self.calls=[];q=self.question();q['diagram']={'kind':'line','values':[{'label':'A','value':150},{'label':'B','value':180}],'check':{'operation':'growth_rate','fromIndex':0,'toIndex':1}}
   fixed=copy.deepcopy(q)
   if field=='diagram':fixed['diagram']['values'][0]['value']=100
   else:fixed['options'].reverse()
   bad=json.dumps({'questions':[q]}).replace('"questions":','"questions"',1)
   with self.assertRaises(ValueError):self.run_question([bad,json.dumps({'questions':[fixed]})])
   self.assertEqual(len(self.calls),2)
 def test_failed_repair_transport_does_not_enable_another_backend_retry(self):
  from practice_reply import PracticeReplyError
  with self.assertRaises(PracticeReplyError) as error:self.run_question(['{"questions":[',HTTPError('https://test.invalid',503,'unavailable',{},None)])
  self.assertEqual(error.exception.code,'practice_format_repair_failed');self.assertEqual(len(self.calls),2)
 def test_duplicate_keys_and_nonfinite_numbers_are_not_silently_accepted(self):
  for bad in ['{"questions":[],"questions":[{}]}','{"questions":[],"value":NaN}','{"questions":[],"value":1e999}']:
   self.calls=[]
   with self.assertRaises(ValueError):self.run_question([bad,'{"questions":[]}'])
   self.assertEqual(len(self.calls),2)
 def test_repaired_questions_still_undergo_answer_validation(self):
  q=self.question();q['answerIndex']=3;raw=json.dumps({'questions':[q]});bad=raw.replace('"questions":','"questions"',1)
  result=self.run_question([bad,raw]);self.assertEqual(result['questions'],[]);self.assertEqual(result['rejectedCount'],1);self.assertEqual(len(self.calls),2)
 def test_valid_whitespace_inside_math_is_not_guessed_as_a_command(self):
  q=self.question();q['prompt']='公式 \\(x\nand y\tthen z\\)。转义价格 \\$5 与 \\$10。'
  result=self.run_question([json.dumps({'questions':[q]})]);self.assertEqual(result['questions'][0]['prompt'],q['prompt']);self.assertEqual(len(self.calls),1)
 def test_calculation_questions_keep_numeric_diagram_checks(self):
  cases=[]
  cases.append((4,'2**2',{'kind':'function','domain':[-2,2],'range':[-1,5],'curves':[{'expression':'x**2'}],'check':{'operation':'value_at','curveIndex':0,'x':2}}))
  cases.append((5,'sqrt(3**2+4**2)',{'kind':'geometry','points':[{'id':'A','x':0,'y':0},{'id':'B','x':3,'y':0},{'id':'C','x':0,'y':4}],'edges':[{'from':'B','to':'C'}],'check':{'operation':'distance','from':'B','to':'C'}}))
  cases.append((2,'12/6',diagram_fixtures.StructuredDiagramTests().circuit()))
  for kind in ['bar','line','table']:cases.append((20,'(180-150)/150*100',{'kind':kind,'values':[{'label':'A','value':150},{'label':'B','value':180}],'check':{'operation':'growth_rate','fromIndex':0,'toIndex':1}}))
  cases.append((75,'30/(10+30)*100',{'kind':'pie','values':[{'label':'A','value':10},{'label':'B','value':30}],'check':{'operation':'share','toIndex':1}}))
  cases.append((2,'(6-2)/(3-1)',{'kind':'scatter','values':[{'label':'A','x':1,'y':2},{'label':'B','x':3,'y':6}],'check':{'operation':'slope','fromIndex':0,'toIndex':1}}))
  for value,expression,diagram in cases:
   with self.subTest(kind=diagram['kind']):
    self.calls=[];q=self.question();q.update(options=[str(v) for v in [value-1,value,value+1,value+2]],calculation={'expression':expression,'value':value,'optionValues':[value-1,value,value+1,value+2]},diagram=diagram)
    result=self.run_question([json.dumps({'questions':[q]}).replace('\\\\','\\')]);self.assertEqual(len(result['questions']),1);self.assertTrue(result['questions'][0]['validation']['calculationChecked']);self.assertTrue(result['questions'][0]['validation']['diagramChecked']);self.assertEqual(len(self.calls),1)
 def test_failed_correction_keeps_other_original_valid_questions(self):
  bad=self.question();del bad['takeaway'];good=self.question();good['prompt']='另一道完整题目'
  result=self.run_question([json.dumps({'questions':[bad,good]}),'{"questions": ['])
  self.assertEqual(len(result['questions']),1);self.assertEqual(result['questions'][0]['prompt'],good['prompt']);self.assertEqual(result['rejectedCount'],1);self.assertEqual(len(self.calls),2)
 def test_endpoint_returns_specific_error_without_raw_reply(self):
  import app
  from fastapi import HTTPException
  with self.wire(['{"questions": [','{"questions": [']):
   with self.assertRaises(HTTPException) as error:app.practice(app.PracticeRequest(nodes=fixtures.PracticeTests.nodes))
  self.assertEqual(error.exception.status_code,422);self.assertEqual(error.exception.detail,'practice_format_repair_failed')
 def test_logs_do_not_contain_model_reply_or_secret(self):
  raw=json.dumps({'questions':[self.question()]});self.run_question([raw.replace('"questions":','"questions"',1),raw]);from pathlib import Path
  logs=(Path(self.folder.name)/'model-events.jsonl').read_text();self.assertNotIn('TEST_ONLY',logs);self.assertNotIn('计算增长率',logs);self.assertIn('reply_repair',logs)
if __name__=='__main__':unittest.main()
