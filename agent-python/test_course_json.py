"""Lossless course JSON recovery; never rewrite the outline."""
import json,unittest,tempfile,os
from unittest.mock import patch
from pathlib import Path
from model_diagnostics import close_logs,request_model_json
from urllib.request import Request
from course_json import parse_course_json,CourseJsonFormatError,same_format_content
class CourseJsonTests(unittest.TestCase):
 def setUp(self):
  self.value={'topic':'PRIVATE_COURSE','children':[{'title':'formula \\frac{a}{b}','children':[{'title':'method','imageIds':['img_1']}]}],'examples':[],'uncertainties':[]}
  self.text=json.dumps(self.value,ensure_ascii=False)
 def test_plain_reply_preserves_every_node_value_and_order(self):self.assertEqual(parse_course_json(self.text),self.value)
 def test_known_wrappers_and_bom_do_not_change_tree(self):
  for text in ('\ufeff'+self.text,'```json\n'+self.text+'\n```','以下是JSON结果：\n'+self.text,self.text+'\n以上为JSON结果。'):
   self.assertEqual(parse_course_json(text),self.value)
 def test_identical_repeated_objects_are_recovered_without_merging_nodes(self):
  self.assertEqual(parse_course_json(self.text+'\n'+self.text),self.value)
 def test_distinct_complete_objects_are_never_silently_dropped_or_merged(self):
  other=dict(self.value,topic='other')
  with self.assertRaises(CourseJsonFormatError):parse_course_json(self.text+json.dumps(other))
 def test_truncated_suffix_is_not_silently_ignored(self):
  with self.assertRaises(CourseJsonFormatError):parse_course_json(self.text+' {"children":[')
 def test_duplicate_keys_and_nonfinite_values_rejected(self):
  for text in ('{"children":[],"children":[1]}','{"a":NaN}','{"a":1e999}','[{}]'):
   with self.assertRaises(CourseJsonFormatError):parse_course_json(text)
 def test_identical_duplicate_fields_recover_nested_values_without_changing_order(self):
  text='{"topic":"course","children":[{"title":"method","title":"method","imageIds":["img_1"],"imageIds":["img_1"],"details":[{"title":"formula"}]}],"children":[{"title":"method","imageIds":["img_1"],"details":[{"title":"formula"}]}],"examples":[]}'
  result=parse_course_json(text)
  self.assertEqual(list(result),['topic','children','examples'])
  self.assertEqual(list(result['children'][0]),['title','imageIds','details'])
  self.assertEqual(result['children'][0]['details'],[{'title':'formula'}])
 def test_conflicting_duplicates_are_located_and_never_merged(self):
  for first,second in [('true','1'),('-0.0','0.0'),('9007199254740992.0','9007199254740993.0'),('1e-400','2e-400'),('1','1.0'),('[1,2]','[2,1]'),('[]','[1]'),('{"a":1,"b":2}','{"b":2,"a":1}')]:
   with self.subTest(first=first,second=second):
    with self.assertRaises(CourseJsonFormatError) as error:
     parse_course_json('{"children":[{"details":[{"imageIds":'+first+',"imageIds":'+second+'}]}]}')
    self.assertEqual(error.exception.code,'json_duplicate_key')
    self.assertIn('root.children[0].details[0].imageIds',str(error.exception))
 def test_identical_float_duplicates_return_standard_json_types(self):
  result=parse_course_json('{"value":1.25,"value":1.25}')
  self.assertIs(type(result['value']),float);self.assertEqual(result,{'value':1.25})
 def test_distinct_numeric_documents_are_not_collapsed_by_float_rounding(self):
  with self.assertRaises(CourseJsonFormatError):parse_course_json('{"value":1e-400}{"value":2e-400}')
 def test_duplicate_recovery_does_not_hide_other_document_errors(self):
  for suffix in (' {"other":1}',' {"broken":',' EXTRA'):
   with self.assertRaises(CourseJsonFormatError):parse_course_json('{"children":[],"children":[]}'+suffix)
 def test_repeated_key_in_different_objects_is_not_duplicate(self):
  self.assertEqual(parse_course_json('{"children":[{"title":"a"},{"title":"b"}]}')['children'],[{'title':'a'},{'title':'b'}])
 def test_duplicate_diagnostics_are_private_and_include_safe_path(self):
  with tempfile.TemporaryDirectory() as d:
   try:
    with patch.dict(os.environ,{'MODEL_LOG_DIR':d}):
     parse_course_json('{"children":[{"title":"PRIVATE","title":"PRIVATE"}]}')
     with self.assertRaises(CourseJsonFormatError):parse_course_json('{"children":[{"PRIVATE_KEY":1,"PRIVATE_KEY":2}]}')
    text=(Path(d)/'model-events.jsonl').read_text()
    self.assertIn('json_identical_key',text);self.assertIn('duplicate_key_count',text)
    self.assertIn('root.children[0].field',text);self.assertNotIn('PRIVATE',text)
   finally:close_logs()
 def test_repair_verifier_allows_commas_but_not_content_or_hierarchy_changes(self):
  missing=self.text.replace(', "examples"',' "examples"')
  self.assertTrue(same_format_content(missing,self.text))
  self.assertFalse(same_format_content(self.text,self.text.replace('method','different')))
  self.assertFalse(same_format_content('{"children":[{"title":"x"}]}','{"children":{"title":"x"}}'))
 def test_unknown_prose_and_extra_brackets_remain_errors(self):
  for text in (self.text+'PRIVATE_EXPLANATION',self.text+'}',self.text+'\n{"additional":"PRIVATE"}'):
   with self.assertRaises(CourseJsonFormatError):parse_course_json(text)
 def test_diagnostic_logs_only_recovery_kind_not_body(self):
  with tempfile.TemporaryDirectory() as d:
   try:
    with patch.dict(os.environ,{'MODEL_LOG_DIR':d}):parse_course_json('```json\n'+self.text+'\n```',task='unbound')
    text=(Path(d)/'model-events.jsonl').read_text();self.assertIn('json_recovery',text);self.assertNotIn('PRIVATE_COURSE',text);self.assertNotIn('frac',text)
   finally:close_logs()
if __name__=='__main__':unittest.main()
