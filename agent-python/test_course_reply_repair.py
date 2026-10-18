"""Offline same-conversation repair of multiple map response format errors."""
import copy,json,os,tempfile,unittest,threading
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import CancelledError
import course_mind_map as course
from course_json import CourseJsonFormatError
from model_diagnostics import close_logs
class ReplyRepairTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  env=patch.dict(os.environ,{'DEEPSEEK_API_KEY':'TEST_ONLY','MODEL_LOG_DIR':str(self.root/'logs')});env.start();self.addCleanup(env.stop);self.addCleanup(close_logs)
  self.payload=dict(_diagnosticTaskId='11111111-1111-1111-1111-111111111111',concepts=[],examples=[],connections=[],uncertainties=[],sourceEvidence=[dict(sourceId='t_1',sourceType='transcript',startMs=0,endMs=100,quote='PRIVATE_SPEECH')],imageEvidence=[],firstHandImageIds=[],firstHandSourceIds=[])
 def node(self,title):return dict(title=title,children=[],details=[],sourceIds=['t_1'],imageIds=[])
 def good(self):return dict(topic='PRIVATE_COURSE',children=[self.node('PRIVATE_FORMULA')],examples=[],uncertainties=[])
 def invoke(self,texts,signal=None):
  calls=[]
  class Response:
   def __init__(self,text):self.text=text
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':self.text}}]}).encode()
  def transport(request,**kw):
   body=json.loads(request.data);calls.append(body);index=len(calls)-1
   if index>=len(texts):raise AssertionError('unexpected additional model call')
   if signal is not None and index==0:signal.set()
   return Response(texts[index])
  return calls,patch('course_mind_map.urlopen',side_effect=transport)
 def test_valid_map_has_identical_first_request_and_no_retry(self):
  raw=self.good();calls,mock=self.invoke([json.dumps(raw)])
  with mock:result=course._deepseek_course_json(self.payload,[])
  self.assertEqual(result,raw);self.assertEqual(len(calls),1);self.assertEqual(calls[0]['messages'][0]['content'],course.INSTRUCTIONS)
 def test_multiple_conflicts_missing_and_wrong_types_share_one_conversation_repair(self):
  raw=self.good();raw['children'].append(self.node('PRIVATE_SECOND'));fixed=copy.deepcopy(raw)
  text=json.dumps(raw).replace('"children": [], "details": []','"children": [], "children": {}, "details": "PRIVATE_DETAIL"',1)
  text=text.replace('"title": "PRIVATE_SECOND", ','');fixed['children'][0]['details']=[{'title':'PRIVATE_DETAIL'}]
  calls,mock=self.invoke([text,json.dumps(fixed)])
  with mock:result=course._deepseek_course_json(self.payload,[])
  self.assertEqual(result,fixed);self.assertEqual(len(calls),2);self.assertEqual(calls[1]['messages'][:2],calls[0]['messages'])
  self.assertEqual(calls[1]['messages'][2],{'role':'assistant','content':text})
  issues=json.loads(calls[1]['messages'][3]['content'])['issues'];kinds={i['code'] for i in issues}
  self.assertTrue({'duplicate_field','invalid_type','missing_field'}<=kinds)
 def test_missing_top_level_fields_are_repaired_without_discarding_existing_nodes(self):
  fixed=self.good();raw=copy.deepcopy(fixed);del raw['examples'];calls,mock=self.invoke([json.dumps(raw),json.dumps(fixed)])
  with mock:self.assertEqual(course._deepseek_course_json(self.payload,[]),fixed)
  self.assertEqual(len(calls),2)
 def test_second_bad_reply_never_starts_third_call(self):
  raw=self.good();del raw['examples'];calls,mock=self.invoke([json.dumps(raw),json.dumps(raw)])
  with mock:
   with self.assertRaises(CourseJsonFormatError) as failure:course._deepseek_course_json(self.payload,[])
  self.assertEqual(len(calls),2);self.assertIn('已自动修复1次',str(failure.exception))
 def test_repair_cannot_delete_duplicate_branch_formula(self):
  good=self.good();text=json.dumps(good).replace('"children": [],','"children": [], "children": [{"title":"PRIVATE_KEEP"}],',1)
  calls,mock=self.invoke([text,json.dumps(good)])
  with mock:
   with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,[])
  self.assertEqual(len(calls),2)
 def test_repair_cannot_reorganize_an_existing_valid_subtree(self):
  raw=self.good();raw['children'][0]['children']=[self.node('PRIVATE_CHILD')];del raw['examples'];changed=self.good();changed['children'].append(self.node('PRIVATE_CHILD'))
  calls,mock=self.invoke([json.dumps(raw),json.dumps(changed)])
  with mock:
   with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,[])
  self.assertEqual(len(calls),2)
 def test_cancel_after_first_reply_prevents_second_request(self):
  raw=self.good();del raw['examples'];signal=threading.Event();calls,mock=self.invoke([json.dumps(raw)],signal)
  with mock:
   with self.assertRaises(CancelledError):course._deepseek_course_json(self.payload,[],signal=signal)
  self.assertEqual(len(calls),1)
 def test_repair_logs_paths_duration_and_counts_without_course_text(self):
  raw=self.good();del raw['examples'];calls,mock=self.invoke([json.dumps(raw),json.dumps(self.good())])
  with mock:course._deepseek_course_json(self.payload,[])
  logs=(self.root/'logs/model-events.jsonl').read_text();self.assertIn('reply_repair',logs);self.assertIn('root.examples',logs);self.assertIn('elapsed_ms',logs)
  self.assertNotIn('PRIVATE',logs);self.assertNotIn('TEST_ONLY',logs)
 def test_repair_cannot_add_unrequested_knowledge_nodes(self):
  raw=self.good();del raw['examples'];changed=self.good();changed['children'].append(self.node('INVENTED'))
  calls,mock=self.invoke([json.dumps(raw),json.dumps(changed)])
  with mock:
   with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,[])
  self.assertEqual(len(calls),2)
 def test_structure_repair_and_citation_repair_share_one_request_budget(self):
  raw=self.good();raw['children'][0]['sourceIds']=['unknown'];del raw['examples'];fixed=copy.deepcopy(raw);fixed['examples']=[]
  calls,mock=self.invoke([json.dumps(raw),json.dumps(fixed)])
  with mock:result=course._deepseek_course_json(self.payload,[])
  self.assertEqual(len(calls),2);self.assertEqual(result,fixed)
 def test_timeout_is_not_mistaken_for_response_structure_error(self):
  with patch('course_mind_map.urlopen',side_effect=TimeoutError()) as transport:
   with self.assertRaises(TimeoutError):course._deepseek_course_json(self.payload,[])
  self.assertEqual(transport.call_count,1)
 def test_all_duplicate_paths_are_collected_from_different_branches(self):
  from course_reply_repair import parse_map_reply,ReplyStructureError
  text='{"topic":"course","children":[{"title":"first","children":[],"children":{}},{"details":1}],"examples":{},"examples":[]}'
  with self.assertRaises(ReplyStructureError) as failure:parse_map_reply(text)
  paths={i['path'] for i in failure.exception.issues}
  self.assertTrue({'root.children[0].children','root.children[1].title','root.children[1].details','root.examples'}<=paths)
 def test_repair_cannot_append_metadata_or_references_to_valid_node(self):
  raw=self.good();del raw['examples']
  for field,value in [('sourceIds',['t_1','t_UNSUPPORTED']),('kind','invented'),('unsupported_formula','E=mc2')]:
   with self.subTest(field=field):
    changed=self.good();changed['children'][0][field]=value;calls,mock=self.invoke([json.dumps(raw),json.dumps(changed)])
    with mock:
     with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,[])
    self.assertEqual(len(calls),2)
 def test_missing_titles_do_not_allow_references_to_move_between_parents(self):
  raw=self.good();raw['children']=[dict(sourceIds=['t_1'],children=[self.node('A')]),dict(sourceIds=[],imageIds=[],children=[self.node('B')])]
  fixed=copy.deepcopy(raw)
  for i,n in enumerate(fixed['children']):n['title']='module '+str(i)
  calls,mock=self.invoke([json.dumps(raw),json.dumps(fixed)])
  with mock:self.assertEqual(course._deepseek_course_json(self.payload,[]),fixed)
  changed=copy.deepcopy(fixed);changed['children'][0]['sourceIds'],changed['children'][1]['sourceIds']=changed['children'][1]['sourceIds'],changed['children'][0]['sourceIds']
  calls,mock=self.invoke([json.dumps(raw),json.dumps(changed)])
  with mock:
   with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,[])
 def test_root_topic_cannot_be_changed_or_moved_into_missing_title(self):
  raw=self.good();del raw['children'][0]['title'];changed=copy.deepcopy(raw);changed['topic']='DIFFERENT';changed['children'][0]['title']=raw['topic']
  calls,mock=self.invoke([json.dumps(raw),json.dumps(changed)])
  with mock:
   with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,[])
 def test_repair_cannot_swap_existing_classification_decisions(self):
  raw=self.good();del raw['examples'];raw['candidateDecisions']=[dict(candidateIds=['k1'],target='knowledge',reason='r1',sourceIds=['t_1']),dict(candidateIds=['e1'],target='example',reason='r2',sourceIds=['t_2'])]
  changed=copy.deepcopy(raw);changed['examples']=[];changed['candidateDecisions'][0]['target']='example';changed['candidateDecisions'][1]['target']='knowledge'
  calls,mock=self.invoke([json.dumps(raw),json.dumps(changed)])
  with mock:
   with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,[])
  self.assertEqual(len(calls),2)
 def test_syntax_error_with_duplicate_still_enters_one_conversation_repair(self):
  raw=self.good();text=json.dumps(raw).replace('"children": [],','"children": [], "children": {},',1).replace(', "examples"',' "examples"')
  calls,mock=self.invoke([text,json.dumps(raw)])
  with mock:self.assertEqual(course._deepseek_course_json(self.payload,[]),raw)
  self.assertEqual(len(calls),2);self.assertEqual(calls[1]['messages'][2]['content'],text)
  issues=json.loads(calls[1]['messages'][3]['content'])['issues'];self.assertTrue(any(i['code']=='parse_error' for i in issues))
 def test_inspection_limit_does_not_skip_repair(self):
  raw=self.good();text=json.dumps(raw).replace('"children": [],','"children": [], "children": {},',1)
  calls,mock=self.invoke([text,json.dumps(raw)])
  with patch('course_reply_repair.MAX_VISITS',1),mock:
   with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,[])
  self.assertEqual(len(calls),2)
  self.assertIn('reply_visit_limit',(self.root/'logs/model-events.jsonl').read_text())
 def test_unreadable_tail_requests_repair_once_but_never_drops_unknown_content(self):
  raw=self.good();text=json.dumps(raw).replace('"children": [],','"children": [], "children": {},',1)+' UNKNOWN_CONTENT'
  calls,mock=self.invoke([text,json.dumps(raw)])
  with mock:
   with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,[])
  self.assertEqual(len(calls),2)
 def test_tolerant_separator_inspection_never_changes_a_formula(self):
  raw=self.good();text=json.dumps(raw).replace(', "examples"',' "examples"');changed=self.good();changed['children'][0]['title']='DIFFERENT_FORMULA'
  calls,mock=self.invoke([text,json.dumps(changed)])
  with mock:
   with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,[])
  self.assertEqual(len(calls),2)
 def test_invalid_scalar_heading_cannot_be_discarded_or_renamed(self):
  raw=self.good();raw['children'][0]['title']=123
  for replacement,accepted in [('made up',False),('123',True)]:
   fixed=copy.deepcopy(raw);fixed['children'][0]['title']=replacement;calls,mock=self.invoke([json.dumps(raw),json.dumps(fixed)])
   with mock:
    if accepted:self.assertEqual(course._deepseek_course_json(self.payload,[]),fixed)
    else:
     with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,[])
   self.assertEqual(len(calls),2)
 def test_repeated_identical_documents_with_conflicts_can_be_repaired_losslessly(self):
  raw=self.good();part=json.dumps(raw).replace('"children": [],','"children": [], "children": {},',1);text=part+'\n'+part
  calls,mock=self.invoke([text,json.dumps(raw)])
  with mock:self.assertEqual(course._deepseek_course_json(self.payload,[]),raw)
  self.assertEqual(len(calls),2)
 def test_distinct_second_document_cannot_be_dropped_by_repair(self):
  raw=self.good();part=json.dumps(raw).replace('"children": [],','"children": [], "children": {},',1);other=self.good();other['children'][0]['title']='PRIVATE_OTHER_FORMULA';text=part+'\n'+json.dumps(other)
  calls,mock=self.invoke([text,json.dumps(raw)])
  with mock:
   with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,[])
  self.assertEqual(len(calls),2)
if __name__=='__main__':unittest.main()
