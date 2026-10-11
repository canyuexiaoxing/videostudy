from pathlib import Path
root=Path(r'E:\workp\videostudy')
p=root/'agent-python/test_core_mind_map.py'
with p.open('a',encoding='utf-8') as f:
 f.write('''
 def test_case_reclassification_does_not_depend_on_node_order(self):
  general={'title':'增长量比较','kind':'knowledge','sourceIds':['t_8']}
  case={'title':'本题2014年增长量','kind':'knowledge','sourceIds':['t_8']}
  for nodes in ([general,case],[case,general]):
   result=build_mind_map([segment(8,'2014年比2013年多20')],[],lambda _: {'topic':'课程','children':nodes,'examples':[],'teachingSourceIds':['t_8'],'exampleSourceIds':[]})
   self.assertEqual(result['root']['children'],[])
   self.assertEqual(len(result['examples']),1)
''')
