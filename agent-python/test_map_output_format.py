import json,unittest
from course_map_format import FORMAT_RULES,FORMAT_EXAMPLE,format_instructions

class MapFormatTests(unittest.TestCase):
 def test_example_is_valid_json_with_nested_fields_and_escaped_math(self):
  encoded=json.dumps(FORMAT_EXAMPLE,ensure_ascii=False)
  self.assertEqual(json.loads(encoded),FORMAT_EXAMPLE)
  node=FORMAT_EXAMPLE['children'][0]
  self.assertIn('children',node);self.assertIn('details',node)
  self.assertIn('\\',node['details'][0]['title'])
 def test_only_grammar_examples_are_replaced(self):
  import course_mind_map as course
  from course_outline import STRUCTURE_INSTRUCTIONS
  self.assertIn('Organize the whole course once',course.INSTRUCTIONS)
  self.assertIn('One complete concept or',course.INSTRUCTIONS)
  self.assertIn('12 levels',course.INSTRUCTIONS)
  self.assertIn('JSON_OUTPUT_FORMAT_V2',course.INSTRUCTIONS)
  self.assertNotIn('Return JSON {topic, children:',course.INSTRUCTIONS)
  self.assertNotIn('children:[{title:模块',course.INSTRUCTIONS)
  semantic=STRUCTURE_INSTRUCTIONS.split('递归结构示意')[0]
  self.assertIn(semantic,course.INSTRUCTIONS)
 def test_spec_does_not_request_simplification_or_extra_nodes(self):
  self.assertIn('do not determine the number',FORMAT_RULES)
  self.assertIn('Do not omit',FORMAT_RULES)
  self.assertIn('backslash',FORMAT_RULES)
 def test_nested_good_reply_is_returned_unchanged(self):
  from course_reply_repair import parse_map_reply
  raw={'topic':'t','children':[{'title':'parent','children':[{'title':'formula','kind':'formula','sourceIds':['t_1'],'details':[{'title':'condition','kind':'condition','imageIds':['frame_1']}],'children':[]}],'sourceIds':[],'imageIds':[]}],'examples':[{'title':'worked example','sourceIds':['t_2']}],'uncertainties':[]}
  self.assertEqual(parse_map_reply(json.dumps(raw)),raw)

class ParserReasonTests(unittest.TestCase):
 def test_missing_comma_has_safe_reason_and_exact_position(self):
  from course_reply_repair import parse_map_reply,ReplyStructureError
  text='{"topic":"PRIVATE" "children":[],"examples":[]}'
  with self.assertRaises(ReplyStructureError) as failure:parse_map_reply(text)
  issue=failure.exception.issues[0]
  self.assertEqual(issue['syntaxReason'],'syntax_expected_comma')
  self.assertEqual(issue['position'],text.index('"children"'))
  self.assertNotIn('PRIVATE',json.dumps(issue));self.assertIn('syntax_expected_comma',str(failure.exception))
 def test_trailing_text_has_distinct_reason(self):
  from course_reply_repair import parse_map_reply,ReplyStructureError
  with self.assertRaises(ReplyStructureError) as failure:parse_map_reply('{"topic":"t","children":[],"examples":[]} PRIVATE')
  self.assertEqual(failure.exception.issues[0]['syntaxReason'],'syntax_trailing_content')
 def test_unterminated_string_is_not_reported_as_missing_comma(self):
  from course_reply_repair import parse_map_reply,ReplyStructureError
  with self.assertRaises(ReplyStructureError) as failure:parse_map_reply('{"topic":"PRIVATE')
  self.assertEqual(failure.exception.issues[0]['syntaxReason'],'syntax_unterminated_string')


class ExistingHierarchyExampleTests(unittest.TestCase):
 def test_same_three_levels_and_conditions_are_preserved(self):
  from course_map_format import HIERARCHY_EXAMPLE
  import course_mind_map as course
  module=HIERARCHY_EXAMPLE['children'][0];method=module['children'][0];formula=method['children'][0]
  self.assertEqual([module['title'],method['title'],formula['title']],['模块','分类方法','独立公式'])
  self.assertEqual([module['kind'],method['kind'],formula['kind']],['category','method','formula'])
  self.assertEqual(method['details'][0]['title'],'条件')
  from course_map_format import UNIFIED_EXAMPLE
  self.assertEqual(UNIFIED_EXAMPLE['children'],HIERARCHY_EXAMPLE['children'])
  self.assertIn(json.dumps(UNIFIED_EXAMPLE,ensure_ascii=False,indent=2),course.INSTRUCTIONS)


class SyntaxClassificationTests(unittest.TestCase):
 def test_decoder_categories_remain_distinct_and_content_free(self):
  from course_reply_repair import parse_map_reply,ReplyStructureError
  cases=[('{"topic" "PRIVATE"}','syntax_expected_colon'),('{PRIVATE}','syntax_expected_property'),('{"topic":}','syntax_expected_value'),('{"topic":"' + chr(92) + 'q"}','syntax_invalid_escape'),('{"topic":"' + chr(92) + 'uZZZZ"}','syntax_invalid_unicode'),('{"topic":"PRIVATE' + chr(1) + '"}','syntax_invalid_control')]
  for text,reason in cases:
   with self.subTest(reason=reason):
    with self.assertRaises(ReplyStructureError) as failure:parse_map_reply(text)
    self.assertEqual(failure.exception.issues[0]['syntaxReason'],reason)
    self.assertNotIn('PRIVATE',json.dumps(failure.exception.issues))

class CompletionBoundaryTests(unittest.TestCase):
 def test_initial_prompt_checks_one_complete_root_without_changing_outline(self):
  import course_mind_map as course
  self.assertIn('JSON_COMPLETION_CHECK_V2',course.INSTRUCTIONS)
  self.assertIn('Do not close the root object',course.INSTRUCTIONS)
  self.assertIn('Do not truncate',course.INSTRUCTIONS)
  self.assertIn('Do not omit, merge, shorten or reclassify',course.INSTRUCTIONS)

class UnifiedFormatContractTests(unittest.TestCase):
 def test_single_complete_example_and_recursive_schema(self):
  import course_mind_map as course
  from course_map_format import OUTPUT_SCHEMA,UNIFIED_EXAMPLE
  self.assertEqual(course.INSTRUCTIONS.count('BEGIN_COMPLETE_JSON_EXAMPLE'),1)
  example=json.loads(course.INSTRUCTIONS.split('BEGIN_COMPLETE_JSON_EXAMPLE\n')[1].split('\nEND_COMPLETE_JSON_EXAMPLE')[0])
  self.assertEqual(example,UNIFIED_EXAMPLE)
  self.assertEqual(set(example),{'topic','children','examples','uncertainties'})
  self.assertEqual(OUTPUT_SCHEMA['$defs']['node']['properties']['children']['items'],{'$ref':'#/$defs/node'})
  self.assertTrue(OUTPUT_SCHEMA['additionalProperties'])
  self.assertNotIn('maxItems',json.dumps(OUTPUT_SCHEMA))
  self.assertNotIn('maxLength',json.dumps(OUTPUT_SCHEMA))
 def test_repair_context_is_bounded_and_untrusted(self):
  from course_reply_repair import parse_map_reply,repair_instruction
  text='{"topic":"PRIVATE","children":[],"examples":[]}'+' ,'+('PRIVATE_TAIL'*200)
  try:parse_map_reply(text)
  except ValueError as error:instruction=repair_instruction(error)
  context=instruction['formatErrorContext']
  self.assertTrue(context['untrustedData'])
  self.assertLessEqual(len(context['before']),160);self.assertLessEqual(len(context['after']),160)
  self.assertIn('Do not return the unchanged',instruction['task'])
 def test_repair_reports_unclosed_required_root_fields_without_content(self):
  from course_reply_repair import parse_map_reply,repair_instruction
  text='{"topic":"PRIVATE","children":[]} , {"title":"PRIVATE_TAIL"}'
  try:parse_map_reply(text)
  except ValueError as error:info=repair_instruction(error)['trailingContentRepair']
  self.assertEqual(info['completedRootFields'],['topic','children'])
  self.assertIn('examples',info['missingRootFields'])
  self.assertNotIn('PRIVATE',json.dumps(info))
