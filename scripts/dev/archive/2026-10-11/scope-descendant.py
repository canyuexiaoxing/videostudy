from pathlib import Path
import sys
root=Path(r'E:\workp\videostudy')
if sys.argv[-1]=='test':
 p=root/'agent-python/test_core_mind_map.py'
 with p.open('a',encoding='utf-8') as f:
  f.write('''
 def test_case_reclassification_includes_descendant_calculation_evidence(self):
  result=build_mind_map([segment(8,'计算'),segment(9,'120减100等于20')],[],lambda _: {'topic':'课程','children':[{'title':'计算方法','sourceIds':['t_9']},{'title':'本题计算','sourceIds':['t_8'],'children':[{'title':'计算步骤','sourceIds':['t_9']}]}],'examples':[],'teachingSourceIds':['t_8','t_9'],'exampleSourceIds':[]})
  self.assertEqual(result['root']['children'],[])
  self.assertEqual([ref['sourceId'] for ref in result['examples'][0]['evidenceRefs']],['t_8','t_9'])
''')
else:
 p=root/'agent-python/mind_map.py';s=p.read_text(encoding='utf-8')
 old='''                    for sid in raw.get('sourceIds', []) if isinstance(raw.get('sourceIds'), list) else []:
                        if isinstance(sid, str) and sid in sources:
                            example_ids.add(sid); teaching_ids.discard(sid)
                    candidates.append(raw)'''
 new='''                    pending, scanned = [raw], 0
                    while pending and scanned < MAX_NODES_PER_CHUNK:
                        item = pending.pop(); scanned += 1
                        if not isinstance(item, dict): continue
                        for sid in item.get('sourceIds', [])[:CHUNK_SEGMENTS] if isinstance(item.get('sourceIds'), list) else []:
                            if isinstance(sid, str) and sid in sources:
                                example_ids.add(sid); teaching_ids.discard(sid)
                        if isinstance(item.get('children'), list): pending.extend(item['children'][:MAX_NODES_PER_CHUNK])
                    candidates.append(raw)'''
 assert old in s;s=s.replace(old,new);p.write_text(s,encoding='utf-8')
