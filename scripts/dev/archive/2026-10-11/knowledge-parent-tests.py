from pathlib import Path
p=Path(r'E:\workp\videostudy\agent-python\test_core_mind_map.py')
with p.open('a',encoding='utf-8') as f:
 f.write('''
 def test_inherited_ancestor_jump_is_rebuilt_after_application_removed(self):
  result=build_mind_map([segment(1,'专门讲知识'),segment(8,'应用知识')],[],lambda _: {'topic':'课程','children':[{'title':'分组','children':[{'title':'应用','teachingRole':'application','sourceIds':['t_8']},{'title':'知识','sourceIds':['t_1']}]}],'examples':[]})
  root=result['root'];chapter=root['children'][0];group=chapter['children'][0]
  self.assertEqual([n['startMs'] for n in (root,chapter,group)],[1000,1000,1000])

 def test_dedicated_parent_survives_removal_of_application_children(self):
  result=build_mind_map([segment(1,'专门讲公式'),segment(8,'应用公式')],[],lambda _: {'topic':'公式','children':[{'title':'公式定义','sourceIds':['t_1'],'children':[{'title':'代入计算','teachingRole':'application','sourceIds':['t_8']}]}],'examples':[]})
  self.assertEqual(result['status'],'completed')
  node=result['root']['children'][0]['children'][0]
  self.assertEqual(node['startMs'],1000);self.assertEqual(node['children'],[])
''')
