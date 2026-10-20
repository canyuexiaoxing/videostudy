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
  self.assertIn('JSON_OUTPUT_FORMAT_V1',course.INSTRUCTIONS)
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
  self.assertIn(json.dumps(HIERARCHY_EXAMPLE,ensure_ascii=False),course.INSTRUCTIONS)


class SyntaxClassificationTests(unittest.TestCase):
 def test_decoder_categories_remain_distinct_and_content_free(self):
  from course_reply_repair import parse_map_reply,ReplyStructureError
  cases=[('{"topic" "PRIVATE"}','syntax_expected_colon'),('{PRIVATE}','syntax_expected_property'),('{"topic":}','syntax_expected_value'),('{"topic":"' + chr(92) + 'q"}','syntax_invalid_escape'),('{"topic":"' + chr(92) + 'uZZZZ"}','syntax_invalid_unicode'),('{"topic":"PRIVATE' + chr(1) + '"}','syntax_invalid_control')]
  for text,reason in cases:
   with self.subTest(reason=reason):
    with self.assertRaises(ReplyStructureError) as failure:parse_map_reply(text)
    self.assertEqual(failure.exception.issues[0]['syntaxReason'],reason)
    self.assertNotIn('PRIVATE',json.dumps(failure.exception.issues))
