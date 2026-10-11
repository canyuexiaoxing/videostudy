from pathlib import Path
p=Path(r'E:\workp\videostudy\agent-python\test_core_mind_map.py')
with p.open('a',encoding='utf-8') as f:
 f.write('''
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

 def test_example_range_filters_other_chunks_and_empty_groups(self):
  speech=[segment(i) for i in range(1,82)]
  def ask(payload):
   if payload['segments'][0]['id']=='t_1':
    return {'topic':'讲题','children':[{'title':'知识分组','children':[{'title':'旧公式应用','sourceIds':['t_79']}]}],'examples':[{'title':'完整例题','sourceIds':['t_75','t_80']}]}
   return {'topic':'讲解','children':[{'title':'知识点','sourceIds':['t_81']}],'examples':[]}
  result=build_mind_map(speech,[],ask)
  self.assertEqual(len(result['root']['children']),1)
  self.assertEqual(result['root']['children'][0]['title'],'讲解')
  self.assertEqual(result['examples'][0]['startMs'],75000)
''')
