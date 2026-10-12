import unittest
from mind_map import build_mind_map
from test_mind_map import segment

class CoreMapTest(unittest.TestCase):
 def test_examples_separate_from_formulas_and_times_are_evidence_derived(self):
  result=build_mind_map([segment(1,'增长量等于现期减基期'),segment(8,'例题一，现期120，基期100'),segment(10,'增长量为20')],[],lambda _: {'topic':'增长量','children':[{'title':'增长量公式','sourceIds':['t_1']},{'title':'例题一','kind':'example','sourceIds':['t_8'],'children':[{'title':'代入120减100','sourceIds':['t_10']}]}],'examples':[{'title':'增长量计算例题','sourceIds':['t_10','invented','t_8'],'startMs':999999}]})
  self.assertEqual([n['title'] for n in result['root']['children'][0]['children']],['增长量公式'])
  self.assertEqual(result['examples'][0]['startMs'],8000)
  self.assertTrue(all(e['endMs']==10900 for e in result['examples']))
  self.assertTrue(all(e['children']==[] for e in result['examples']))
  self.assertTrue(all(ref['sourceId']!='invented' for e in result['examples'] for ref in e['evidenceRefs']))

 def test_example_only_course_is_empty_core_with_usable_timeline(self):
  result=build_mind_map([segment(1,'例题一')],[],lambda _: {'topic':'例题讲解','children':[],'examples':[{'title':'例题一','sourceIds':['t_1']}]})
  self.assertEqual(result['status'],'empty');self.assertEqual(result['root']['children'],[])
  self.assertEqual(result['examples'][0]['startMs'],1000)

 def test_unsupported_examples_are_omitted_and_policy_sent_to_same_request(self):
  calls=[]
  def ask(payload):
   calls.append(payload)
   return {'topic':'概念','children':[{'title':'公式','sourceIds':['t_1']}],'examples':[{'title':'编造例题','sourceIds':['unknown']}]}
  result=build_mind_map([segment(1)],[],ask)
  self.assertEqual(result['examples'],[]);self.assertEqual(len(calls),1)
  self.assertIn('contentPolicy',calls[0])

 def test_general_formula_from_example_remains_core(self):
  result=build_mind_map([segment(1,'通用公式')],[],lambda _: {'topic':'公式','children':[{'title':'例题中的通用公式','kind':'knowledge','sourceIds':['t_1']}],'examples':[]})
  self.assertEqual(result['status'],'completed')
  self.assertEqual(result['root']['children'][0]['children'][0]['title'],'例题中的通用公式')
  self.assertEqual(result['examples'],[])

 def test_valid_examples_survive_invalid_core(self):
  result=build_mind_map([segment(1,'例题一')],[],lambda _: {'topic':'课程','children':[{'title':'概念','sourceIds':['unknown']}],'examples':[{'title':'例题一','sourceIds':['t_1']}]})
  self.assertEqual(result['status'],'failed')
  self.assertEqual(len(result['examples']),1)

 def test_formula_application_is_only_example_and_earlier_teaching_is_jump(self):
  result=build_mind_map([segment(1,'先讲增长量公式'),segment(8,'例题开始'),segment(9,'利用增长量公式'),segment(10,'答案20')],[],lambda _: {'topic':'增长量','children':[{'title':'增长量公式','sourceIds':['t_1','t_9']},{'title':'增长量计算方法','sourceIds':['t_9']}],'examples':[{'title':'增长量例题','sourceIds':['t_8','t_10']}]})
  nodes=result['root']['children'][0]['children']
  self.assertEqual([n['title'] for n in nodes],['增长量公式'])
  self.assertEqual([r['sourceId'] for r in nodes[0]['evidenceRefs']],['t_1'])
  self.assertEqual(len(result['examples']),1)

 def test_explicit_application_is_not_core_even_without_example_range(self):
  result=build_mind_map([segment(1,'根据公式代入计算')],[],lambda _: {'topic':'计算','children':[{'title':'公式','teachingRole':'application','sourceIds':['t_1']}],'examples':[{'title':'计算例题','sourceIds':['t_1']}]})
  self.assertEqual(result['status'],'empty')
  self.assertEqual(result['root']['children'],[])
  self.assertEqual(len(result['examples']),1)

 def test_new_knowledge_explained_in_example_can_remain_core(self):
  result=build_mind_map([segment(8,'例题开始'),segment(9,'这里首次推导新公式'),segment(10,'答案')],[],lambda _: {'topic':'新方法','children':[{'title':'新公式推导','teachingRole':'new_knowledge','sourceIds':['t_9']}],'examples':[{'title':'例题','sourceIds':['t_8','t_10']}],'teachingSourceIds':['t_9'],'exampleSourceIds':['t_8','t_10']})
  self.assertEqual(result['status'],'completed')
  self.assertEqual(result['root']['children'][0]['children'][0]['startMs'],9000)
  self.assertNotIn('_teachingRole',str(result))

 def test_example_range_prunes_empty_groups_without_losing_other_chunks(self):
  speech=[segment(i) for i in range(1,82)]
  def ask(payload):
   if payload['segments'][0]['id']=='t_1':
    return {'topic':'讲题','children':[{'title':'知识分组','children':[{'title':'旧公式应用','sourceIds':['t_79']}]}],'examples':[{'title':'完整例题','sourceIds':['t_75','t_80']}]}
   return {'topic':'讲解','children':[{'title':'知识点','sourceIds':['t_81']}],'examples':[]}
  result=build_mind_map(speech,[],ask)
  self.assertEqual(len(result['root']['children']),1)
  self.assertEqual(result['root']['children'][0]['title'],'讲解')
  self.assertEqual(result['examples'][0]['startMs'],75000)

 def test_inherited_ancestor_jump_is_rebuilt_after_application_removed(self):
  result=build_mind_map([segment(1,'专门讲知识'),segment(8,'应用知识')],[],lambda _: {'topic':'课程','children':[{'title':'分组','children':[{'title':'应用','teachingRole':'application','sourceIds':['t_8']},{'title':'知识','sourceIds':['t_1']}]}],'examples':[]})
  root=result['root'];chapter=root['children'][0];group=chapter['children'][0]
  self.assertEqual([n['startMs'] for n in (root,chapter,group)],[1000,1000,1000])

 def test_dedicated_parent_survives_removal_of_application_children(self):
  result=build_mind_map([segment(1,'专门讲公式'),segment(8,'应用公式')],[],lambda _: {'topic':'公式','children':[{'title':'公式定义','sourceIds':['t_1'],'children':[{'title':'代入计算','teachingRole':'application','sourceIds':['t_8']}]}],'examples':[]})
  self.assertEqual(result['status'],'completed')
  node=result['root']['children'][0]['children'][0]
  self.assertEqual(node['startMs'],1000);self.assertEqual(node['children'],[])

 def test_example_review_after_short_range_is_not_new_core_knowledge(self):
  speech=[segment(1,'前面专门讲过公式'),segment(8,'例题开始'),segment(9,'计算得出答案'),segment(10,'2017年同比增长比的是2016年')]
  result=build_mind_map(speech,[],lambda _: {'topic':'课程','children':[{'title':'公式','sourceIds':['t_1']},{'title':'比较基础','teachingRole':'new_knowledge','sourceIds':['t_10']}],'examples':[{'title':'例题','sourceIds':['t_8','t_9']}],'teachingSourceIds':['t_1'],'exampleSourceIds':['t_8','t_9','t_10']})
  self.assertEqual([n['title'] for n in result['root']['children'][0]['children']],['公式'])
  self.assertEqual(result['examples'][0]['endMs'],10900)

 def test_new_knowledge_label_alone_does_not_override_example_evidence(self):
  result=build_mind_map([segment(8,'例题'),segment(9,'本题结果为整数')],[],lambda _: {'topic':'课程','children':[{'title':'本题整数','teachingRole':'new_knowledge','sourceIds':['t_9']}],'examples':[{'title':'例题','sourceIds':['t_8','t_9']}]})
  self.assertEqual(result['status'],'empty')

 def test_independent_teaching_during_example_requires_segment_level_evidence(self):
  result=build_mind_map([segment(8,'例题'),segment(9,'现在单独推导新方法'),segment(10,'回到刚才的题')],[],lambda _: {'topic':'课程','children':[{'title':'新方法推导','teachingRole':'new_knowledge','sourceIds':['t_9']}],'examples':[{'title':'例题','sourceIds':['t_8','t_10']}],'teachingSourceIds':['t_9'],'exampleSourceIds':['t_8','t_10']})
  self.assertEqual(result['status'],'completed')
  self.assertEqual(result['root']['children'][0]['children'][0]['startMs'],9000)

 def test_conflicting_role_ids_prioritize_example_and_fake_ids_are_ignored(self):
  result=build_mind_map([segment(1,'讲解'),segment(8,'解题')],[],lambda _: {'topic':'课程','children':[{'title':'公式','sourceIds':['t_1','t_8']}],'examples':[{'title':'例题','sourceIds':['t_8']}],'teachingSourceIds':['t_1','t_8','fake'],'exampleSourceIds':['t_8','fake']})
  self.assertEqual([r['sourceId'] for r in result['root']['children'][0]['children'][0]['evidenceRefs']],['t_1'])

 def test_example_review_continues_across_chunk_boundary(self):
  def ask(payload):
   if payload['segments'][0]['id']=='t_1':
    return {'topic':'课程','children':[{'title':'公式','sourceIds':['t_1']}],'examples':[{'title':'例题','sourceIds':['t_79','t_80']}],'teachingSourceIds':['t_1'],'exampleSourceIds':['t_79','t_80']}
   return {'topic':'讲评','children':[],'examples':[],'teachingSourceIds':[],'exampleSourceIds':['t_81']}
  result=build_mind_map([segment(i) for i in range(1,82)],[],ask)
  self.assertEqual(result['examples'][0]['endMs'],81900)
  self.assertEqual(result['examples'][0]['evidenceRefs'][-1]['sourceId'],'t_81')

 def test_case_specific_leaf_cannot_be_whitelisted_as_teaching(self):
  result=build_mind_map([segment(1,'先讲公式'),segment(8,'这一道题要注意2014年开头')],[],lambda _: {'topic':'课程','children':[{'title':'公式','sourceIds':['t_1']},{'title':'本题2014年开头要验证基期','kind':'knowledge','sourceIds':['t_8']}],'examples':[],'teachingSourceIds':['t_1','t_8'],'exampleSourceIds':[]})
  self.assertEqual([n['title'] for n in result['root']['children'][0]['children']],['公式'])
  self.assertEqual(len(result['examples']),1)

 def test_case_specific_quote_is_filtered_even_under_general_title(self):
  result=build_mind_map([segment(1,'先讲公式'),segment(8,'这道题算出来是20')],[],lambda _: {'topic':'课程','children':[{'title':'公式','sourceIds':['t_1','t_8']}],'examples':[],'teachingSourceIds':['t_1','t_8'],'exampleSourceIds':[]})
  self.assertEqual([ref['sourceId'] for ref in result['root']['children'][0]['children'][0]['evidenceRefs']],['t_1'])

 def test_case_reclassification_does_not_depend_on_node_order(self):
  general={'title':'增长量比较','kind':'knowledge','sourceIds':['t_8']}
  case={'title':'本题2014年增长量','kind':'knowledge','sourceIds':['t_8']}
  for nodes in ([general,case],[case,general]):
   result=build_mind_map([segment(8,'2014年比2013年多20')],[],lambda _: {'topic':'课程','children':nodes,'examples':[],'teachingSourceIds':['t_8'],'exampleSourceIds':[]})
   self.assertEqual(result['root']['children'],[])
   self.assertEqual(len(result['examples']),1)

 def test_basic_question_types_are_not_a_reference_to_this_question(self):
  result=build_mind_map([segment(1,'增长量计算的基本题型有两种')],[],lambda _: {'topic':'课程','children':[{'title':'基本题型','kind':'knowledge','sourceIds':['t_1']}],'examples':[],'teachingSourceIds':['t_1'],'exampleSourceIds':[]})
  self.assertEqual(result['status'],'completed')
  self.assertEqual(result['examples'],[])

 def test_case_reclassification_includes_descendant_calculation_evidence(self):
  result=build_mind_map([segment(8,'计算'),segment(9,'120减100等于20')],[],lambda _: {'topic':'课程','children':[{'title':'计算方法','sourceIds':['t_9']},{'title':'本题计算','sourceIds':['t_8'],'children':[{'title':'计算步骤','sourceIds':['t_9']}]}],'examples':[],'teachingSourceIds':['t_8','t_9'],'exampleSourceIds':[]})
  self.assertEqual(result['root']['children'],[])
  self.assertEqual([ref['sourceId'] for ref in result['examples'][0]['evidenceRefs']],['t_8','t_9'])

class MisclassifiedExampleTest(unittest.TestCase):
 def test_teaching_label_cannot_turn_formula_reuse_in_question_into_core(self):
  result=build_mind_map([segment(1,'先独立讲公式'),segment(8,'例题开始'),segment(9,'使用前面的公式化简'),segment(10,'答案')],[],lambda _: {'topic':'课程','children':[{'title':'公式','sourceIds':['t_1']},{'title':'公式使用','sourceIds':['t_9']}],'examples':[{'title':'例题','sourceIds':['t_8','t_10']}],'teachingSourceIds':['t_1','t_9'],'exampleSourceIds':['t_8','t_10']})
  self.assertEqual([n['title'] for n in result['root']['children'][0]['children']],['公式'])

 def test_cross_chunk_concepts_merge_without_an_extra_provider_request(self):
  calls=[]
  def ask(payload):
   source=payload['segments'][0]['id'];calls.append(source)
   return {'topic':'极限','children':[{'title':'洛必达法则的条件','conceptKey':'洛必达法则','subject':'极限计算','sourceIds':[source]}]}
  result=build_mind_map([segment(i,'洛必达法则的适用条件') for i in range(81)],[],ask)
  self.assertEqual(calls,['t_0','t_80']);self.assertEqual(len(result['root']['children']),1)
  concept=result['root']['children'][0]['children'][0]
  self.assertEqual(concept['title'],'洛必达法则');self.assertEqual([r['sourceId'] for r in concept['evidenceRefs']],['t_0','t_80'])
  self.assertEqual(concept['children'][0]['title'],'洛必达法则的条件')
