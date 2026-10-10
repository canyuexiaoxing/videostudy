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
  result=build_mind_map([segment(8,'例题开始'),segment(9,'这里首次推导新公式'),segment(10,'答案')],[],lambda _: {'topic':'新方法','children':[{'title':'新公式推导','teachingRole':'new_knowledge','sourceIds':['t_9']}],'examples':[{'title':'例题','sourceIds':['t_8','t_10']}]})
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
