"""Provider-boundary citation handles and bounded immutable repair, offline only."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
import course_mind_map as course
from model_diagnostics import close_logs

class CitationTransportTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  env=patch.dict(os.environ,{'DEEPSEEK_API_KEY':'TEST_ONLY','MODEL_LOG_DIR':str(self.root/'logs')});env.start();self.addCleanup(env.stop);self.addCleanup(close_logs)
  self.payload=dict(_directEvidence=True,concepts=[],examples=[],connections=[],uncertainties=[],firstHandSourceIds=['t_1'],firstHandImageIds=['frame_2274021'],sourceEvidence=[dict(sourceType='transcript',sourceId='t_1',startMs=0,endMs=100,quote='PRIVATE_SPEECH')],imageEvidence=[dict(sourceType='image',sourceId='frame_2274021',startMs=2274021,endMs=2274021,quote='slide')],outlineHints=[])
  self.image=self.root/'2274021.jpg';cv2.imwrite(str(self.image),np.zeros((20,30,3),np.uint8));self.images=[(2274021,self.image,'original')]
 def raw(self,ref):return dict(topic='PRIVATE_COURSE',children=[dict(title='PRIVATE_METHOD',imageIds=[ref],sourceIds=['t_1'],children=[],details=[])],examples=[],uncertainties=[])
 def invoke(self,replies):
  calls=[]
  def send(req,*a,**k):calls.append(json.loads(req.data));value=replies[len(calls)-1];return copy.deepcopy(value)
  with patch('course_mind_map.request_model_json',side_effect=send):result=course._deepseek_course_json(self.payload,self.images)
  return result,calls
 def test_short_handle_matches_caption_and_registry_and_restores_actual_time(self):
  self.payload['outlineHints']=[{'imageId':'frame_2274021','title':'PRIVATE_STRUCTURE','parentLabels':[],'headings':[]}]
  original=copy.deepcopy(self.payload);result,calls=self.invoke([self.raw('img_1')]);content=calls[0]['messages'][1]['content'];wire=json.loads(content[0]['text'])
  self.assertEqual(wire['imageEvidence'][0]['sourceId'],'img_1');self.assertEqual(wire['firstHandImageIds'],['img_1']);self.assertEqual(wire['outlineHints'][0]['imageId'],'img_1');self.assertIn('imageId=img_1',content[1]['text'])
  self.assertEqual(result['children'][0]['imageIds'],['frame_2274021']);self.assertEqual(original,self.payload);self.assertEqual(len(calls),1)
  final=course.finalize_course_reply(result,self.payload,'test');self.assertEqual(final['status'],'completed');self.assertIn(2274021,[r['startMs'] for r in final['root']['children'][0]['evidenceRefs']])
 def test_bad_timestamp_gets_one_reference_only_repair(self):
  raw=self.raw('frame_274021');fix={'corrections':[{'path':'children[0]','field':'imageIds','index':0,'from':'frame_274021','to':'img_1'}]}
  result,calls=self.invoke([raw,fix]);self.assertEqual(len(calls),2);self.assertEqual(result,self.raw('frame_2274021'))
  self.assertEqual(calls[1]['messages'][:2],calls[0]['messages']);self.assertEqual(json.loads(calls[1]['messages'][2]['content']),raw)
  self.assertEqual(raw,self.raw('frame_274021'))
 def test_unknown_or_missing_patch_never_guesses_or_loops(self):
  for fix in ({'corrections':[]},{'corrections':[{'path':'children[0]','field':'imageIds','index':0,'from':'frame_274021','to':'img_2'}]}):
   result,calls=self.invoke([self.raw('frame_274021'),fix]);self.assertEqual(len(calls),2);self.assertEqual(result['children'][0]['imageIds'],['frame_274021'])
   self.assertEqual(course.finalize_course_reply(result,self.payload,'test')['status'],'failed')
 def test_unrequested_node_changes_and_extra_patches_rejected_atomically(self):
  raw=self.raw('frame_274021');raw['children'].append(dict(title='keep',imageIds=['img_1']))
  fix={'corrections':[{'path':'children[0]','field':'imageIds','index':0,'from':'frame_274021','to':'img_1'},{'path':'children[1]','field':'imageIds','index':0,'from':'img_1','to':'img_1'}]}
  result,calls=self.invoke([raw,fix]);self.assertEqual(result['children'][0]['imageIds'],['frame_274021']);self.assertEqual(result['children'][1]['title'],'keep')
 def test_valid_canonical_id_remains_compatible(self):
  result,calls=self.invoke([self.raw('frame_2274021')]);self.assertEqual(len(calls),1);self.assertEqual(result,self.raw('frame_2274021'))
 def test_unknown_alias_is_not_resolved_by_position_or_nearest_time(self):
  result,calls=self.invoke([self.raw('img_999'),{'corrections':[]}]);self.assertEqual(result['children'][0]['imageIds'],['img_999']);self.assertEqual(len(calls),2)
 def test_nested_details_examples_and_wrong_field_handles_decode_without_tree_changes(self):
  raw=self.raw('img_1');raw['children'][0]['details']=[dict(title='method text img_1',sourceIds=[' img_1 '])];raw['examples']=[dict(title='question',imageIds=['img_1'],mergeEvidence=dict(reason='same',imageIds=['img_1']))]
  result,calls=self.invoke([raw]);self.assertEqual(result['children'][0]['details'][0]['title'],'method text img_1');self.assertEqual(result['children'][0]['details'][0]['sourceIds'],['frame_2274021']);self.assertEqual(result['examples'][0]['mergeEvidence']['imageIds'],['frame_2274021']);self.assertEqual(len(calls),1)
 def test_collision_is_rejected_before_sending(self):
  self.payload['sourceEvidence'][0]['sourceId']='img_1'
  with self.assertRaisesRegex(ValueError,'citation_handle_collision'):self.invoke([])
 def test_repair_network_failure_preserves_original_and_does_not_retry(self):
  raw=self.raw('frame_274021')
  with patch('course_mind_map.request_model_json',side_effect=[raw,TimeoutError('PRIVATE_NETWORK')]) as send:
   result=course._deepseek_course_json(self.payload,self.images)
  self.assertEqual(result,raw);self.assertEqual(send.call_count,2)
  logs=(self.root/'logs/model-events.jsonl').read_text();self.assertIn('citation_repair',logs);self.assertIn('reference_repair_failed',logs)
  for private in ('PRIVATE_COURSE','PRIVATE_METHOD','PRIVATE_NETWORK','TEST_ONLY'):self.assertNotIn(private,logs)
 def test_cancelled_after_original_response_prevents_repair_call(self):
  import threading
  from concurrent.futures import CancelledError
  cancel=threading.Event()
  def response(*a,**k):cancel.set();return self.raw('frame_274021')
  with patch('course_mind_map.request_model_json',side_effect=response) as send:
   with self.assertRaises(CancelledError):course._deepseek_course_json(self.payload,self.images,signal=cancel)
  self.assertEqual(send.call_count,1)
 def test_repair_cannot_alter_title_or_drop_original_reference(self):
  fix={'corrections':[{'path':'children[0]','field':'imageIds','index':0,'from':'frame_274021','to':'img_1','title':'replacement'}]}
  result,calls=self.invoke([self.raw('frame_274021'),fix]);self.assertEqual(result,self.raw('frame_274021'))
 def test_repaired_map_context_uses_canonical_images_for_future_practice(self):
  from map_conversation import save_map_conversation,load_map_conversation
  result,_=self.invoke([self.raw('img_1')]);final=course.finalize_course_reply(result,self.payload,'test')
  save_map_conversation(self.root,self.payload,self.images,result,final,course.INSTRUCTIONS)
  saved=load_map_conversation(self.root,final)
  self.assertEqual(json.loads(saved['assistantText'])['children'][0]['imageIds'],['frame_2274021'])
  self.assertEqual(saved['images'][0]['imageId'],'frame_2274021')
 def test_too_many_invalid_slots_does_not_start_unbounded_repair(self):
  raw=self.raw('frame_274021');raw['children'][0]['imageIds']=[f'frame_{i+1}' for i in range(129)]
  result,calls=self.invoke([raw]);self.assertEqual(len(calls),1);self.assertEqual(result,raw)
 def test_format_repair_preserves_content_and_sends_only_reply_not_course_images(self):
  from course_json import CourseJsonFormatError
  raw=self.raw('img_1');invalid=json.dumps(raw).replace(', "examples"',' "examples"')
  with patch('course_mind_map.request_model_json',side_effect=[CourseJsonFormatError('json_invalid_syntax',invalid),raw]) as send:
   result=course._deepseek_course_json(self.payload,self.images)
  self.assertEqual(result,self.raw('frame_2274021'));self.assertEqual(send.call_count,2)
  body=json.loads(send.call_args_list[1].args[0].data);self.assertNotIn('data:image',json.dumps(body));self.assertNotIn('PRIVATE_SPEECH',json.dumps(body))
 def test_format_repair_cannot_change_titles_or_container_hierarchy(self):
  from course_json import CourseJsonFormatError
  raw=self.raw('img_1');invalid=json.dumps(raw).replace(', "examples"',' "examples"');changed=self.raw('img_1');changed['children'][0]['title']='changed'
  with patch('course_mind_map.request_model_json',side_effect=[CourseJsonFormatError('json_invalid_syntax',invalid),changed]) as send:
   with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,self.images)
  self.assertEqual(send.call_count,2)
 def test_format_and_reference_repairs_share_one_extra_request(self):
  from course_json import CourseJsonFormatError
  raw=self.raw('frame_274021');invalid=json.dumps(raw).replace(', "examples"',' "examples"')
  with patch('course_mind_map.request_model_json',side_effect=[CourseJsonFormatError('json_invalid_syntax',invalid),raw]) as send:
   result=course._deepseek_course_json(self.payload,self.images)
  self.assertEqual(send.call_count,2);self.assertEqual(result,raw)
 def test_invalid_citation_patch_json_cannot_trigger_third_request(self):
  from course_json import CourseJsonFormatError
  raw=self.raw('frame_274021')
  with patch('course_mind_map.request_model_json',side_effect=[raw,CourseJsonFormatError('json_invalid_syntax','{"corrections":[] "other":1}')]) as send:
   result=course._deepseek_course_json(self.payload,self.images)
  self.assertEqual(send.call_count,2);self.assertEqual(result,raw)
 def test_ambiguous_json_does_not_choose_one_or_request_a_rewrite(self):
  from course_json import CourseJsonFormatError
  with patch('course_mind_map.request_model_json',side_effect=CourseJsonFormatError('json_ambiguous_documents','{}{}')) as send:
   with self.assertRaises(CourseJsonFormatError):course._deepseek_course_json(self.payload,self.images)
  self.assertEqual(send.call_count,1)
 def test_real_request_wrapper_recovers_fenced_duplicate_without_another_call(self):
  raw=self.raw('img_1');content='```json\n'+json.dumps(raw)+'\n'+json.dumps(raw)+'\n```';calls=[]
  class Response:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':content}}]}).encode()
  def transport(*a,**kw):calls.append(1);return Response()
  with patch('course_mind_map.urlopen',side_effect=transport):result=course._deepseek_course_json(self.payload,self.images)
  self.assertEqual(result,self.raw('frame_2274021'));self.assertEqual(len(calls),1)
 def duplicate_wire(self,contents,finish='stop'):
  calls=[]
  class Response:
   def __init__(self,text):self.text=text
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self):return json.dumps({'choices':[{'finish_reason':finish,'message':{'content':self.text}}]}).encode()
  def transport(*a,**kw):
   text=contents[len(calls)];calls.append(1);return Response(text)
  return calls,patch('course_mind_map.urlopen',side_effect=transport)
 def test_identical_duplicate_keys_need_no_second_request(self):
  raw=self.raw('img_1');text=json.dumps(raw).replace('"imageIds": ["img_1"]','"imageIds": ["img_1"], "imageIds": ["img_1"]')
  calls,mock=self.duplicate_wire([text])
  with mock:result=course._deepseek_course_json(self.payload,self.images)
  self.assertEqual(result,self.raw('frame_2274021'));self.assertEqual(len(calls),1)
 def test_local_duplicate_recovery_does_not_consume_citation_repair_budget(self):
  raw=self.raw('img_999');text=json.dumps(raw).replace('"imageIds": ["img_999"]','"imageIds": ["img_999"], "imageIds": ["img_999"]')
  correction={'corrections':[dict(path='children[0]',field='imageIds',index=0,**{'from':'img_999','to':'img_1'})]}
  calls,mock=self.duplicate_wire([text,json.dumps(correction)])
  with mock:result=course._deepseek_course_json(self.payload,self.images)
  self.assertEqual(result,self.raw('frame_2274021'));self.assertEqual(len(calls),2)
 def test_conflicting_duplicate_does_not_request_model_rewrite(self):
  from course_json import CourseJsonFormatError
  text=json.dumps(self.raw('img_1')).replace('"imageIds": ["img_1"]','"imageIds": ["img_1"], "imageIds": []')
  calls,mock=self.duplicate_wire([text])
  with mock:
   with self.assertRaisesRegex(CourseJsonFormatError,'root.children'):
    course._deepseek_course_json(self.payload,self.images)
  self.assertEqual(len(calls),1)
 def test_duplicate_recovery_never_salvages_truncated_finish_reason(self):
  calls,mock=self.duplicate_wire(['{"children":[],"children":[]}'],finish='length')
  with mock:
   with self.assertRaisesRegex(ValueError,'finish_reason=length'):course._deepseek_course_json(self.payload,self.images)
  self.assertEqual(len(calls),1)
 def test_real_request_wrapper_repairs_format_with_one_call_and_safe_logs(self):
  raw=self.raw('img_1');contents=[json.dumps(raw).replace(', "examples"',' "examples"'),json.dumps(raw)];calls=[]
  class Response:
   def __init__(self,content):self.content=content
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':self.content}}]}).encode()
  def transport(*a,**kw):value=Response(contents[len(calls)]);calls.append(1);return value
  with patch('course_mind_map.urlopen',side_effect=transport):result=course._deepseek_course_json(self.payload,self.images)
  self.assertEqual(result,self.raw('frame_2274021'));self.assertEqual(len(calls),2)
  text=(self.root/'logs/model-events.jsonl').read_text();self.assertIn('json_repair',text);self.assertNotIn('PRIVATE_METHOD',text);self.assertNotIn('PRIVATE_COURSE',text)
 def test_missing_leaf_citation_is_added_without_modifying_tree(self):
  raw=self.raw('img_1');raw['children'][0].update(sourceIds=[],imageIds=[])
  patch_reply={'corrections':[],'additions':[{'path':'children[0]','sourceIds':['t_1'],'imageIds':['img_1']}]}
  result,calls=self.invoke([raw,patch_reply]);self.assertEqual(result,self.raw('frame_2274021'));self.assertEqual(len(calls),2)
 def test_missing_and_unknown_references_are_fixed_in_one_request(self):
  raw=self.raw('frame_274021');raw['children'].append(dict(title='second',sourceIds=[],imageIds=[]))
  fix={'corrections':[dict(path='children[0]',field='imageIds',index=0,**{'from':'frame_274021','to':'img_1'})],'additions':[dict(path='children[1]',sourceIds=[],imageIds=['img_1'])]}
  result,calls=self.invoke([raw,fix]);self.assertEqual(len(calls),2);self.assertEqual(result['children'][0]['imageIds'],['frame_2274021']);self.assertEqual(result['children'][1]['imageIds'],['frame_2274021'])
 def test_grounded_category_parent_needs_no_extra_request(self):
  raw=self.raw('img_1');raw['children']=[dict(title='module',children=raw['children'])]
  result,calls=self.invoke([raw]);self.assertEqual(len(calls),1);self.assertEqual(result['children'][0]['title'],'module')
 def test_missing_source_patch_rejects_unrelated_path_unknown_id_or_title(self):
  raw=self.raw('img_1');raw['children'][0].update(sourceIds=[],imageIds=[])
  for entry in (dict(path='children[99]',sourceIds=[],imageIds=['img_1']),dict(path='children[0]',sourceIds=[],imageIds=['img_999']),dict(path='children[0]',sourceIds=[],imageIds=['img_1'],title='changed')):
   result,calls=self.invoke([raw,{'corrections':[],'additions':[entry]}]);self.assertEqual(result,raw);self.assertEqual(len(calls),2)
 def test_format_repair_consumed_budget_does_not_start_missing_source_repair(self):
  from course_json import CourseJsonFormatError
  raw=self.raw('img_1');raw['children'][0].update(sourceIds=[],imageIds=[]);invalid=json.dumps(raw).replace(', "examples"',' "examples"')
  with patch('course_mind_map.request_model_json',side_effect=[CourseJsonFormatError('json_invalid_syntax',invalid),raw]) as send:
   result=course._deepseek_course_json(self.payload,self.images)
  self.assertEqual(send.call_count,2);self.assertEqual(result,raw)
if __name__=='__main__':unittest.main()
