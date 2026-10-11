from pathlib import Path
p=Path(r'E:\workp\videostudy\agent-python\test_core_mind_map.py')
with p.open('a',encoding='utf-8') as f:
 f.write('''
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
''')
# Earlier new-knowledge fixture now requires independent speech classification.
s=p.read_text(encoding='utf-8').replace("'examples':[{'title':'例题','sourceIds':['t_8','t_10']}]})", "'examples':[{'title':'例题','sourceIds':['t_8','t_10']}],'teachingSourceIds':['t_9'],'exampleSourceIds':['t_8','t_10']})")
p.write_text(s,encoding='utf-8')
