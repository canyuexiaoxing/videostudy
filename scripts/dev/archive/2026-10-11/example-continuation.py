from pathlib import Path
import sys
root=Path(r'E:\workp\videostudy')
if sys.argv[-1]=='test':
 p=root/'agent-python/test_core_mind_map.py'
 with p.open('a',encoding='utf-8') as f:
  f.write('''
 def test_example_review_continues_across_chunk_boundary(self):
  def ask(payload):
   if payload['segments'][0]['id']=='t_1':
    return {'topic':'课程','children':[{'title':'公式','sourceIds':['t_1']}],'examples':[{'title':'例题','sourceIds':['t_79','t_80']}],'teachingSourceIds':['t_1'],'exampleSourceIds':['t_79','t_80']}
   return {'topic':'讲评','children':[],'examples':[],'teachingSourceIds':[],'exampleSourceIds':['t_81']}
  result=build_mind_map([segment(i) for i in range(1,82)],[],ask)
  self.assertEqual(result['examples'][0]['endMs'],81900)
  self.assertEqual(result['examples'][0]['evidenceRefs'][-1]['sourceId'],'t_81')
''')
else:
 p=root/'agent-python/mind_map.py';s=p.read_text(encoding='utf-8')
 s=s.replace("            examples.sort(key=lambda item: item['startMs'])\n            for sid", "            examples.sort(key=lambda item: item['startMs'])\n            continuations = []\n            for sid")
 s=s.replace("                if not preceding:\n                    continue", "                if not preceding:\n                    continuations.append(dict(sourceType='transcript', sourceId=sid,\n                        startMs=source['startMs'], endMs=source['endMs'], quote=source['text']))\n                    continue")
 s=s.replace('return {"examples": examples, "chapter":', 'return {"examples": examples, "continuations": continuations, "chapter":')
 s=s.replace('"failed": True, "examples": examples}', '"failed": True, "examples": examples, "continuations": continuations}')
 s=s.replace('"failed": False, "examples": examples}', '"failed": False, "examples": examples, "continuations": continuations}')
 anchor='    # Verified example intervals'
 block='''    # A review may continue in a later chunk without introducing a new question.
    for ref in sorted([ref for result in results for ref in result.get('continuations', [])], key=lambda ref: ref['startMs']):
        preceding = [example for example in examples if example['startMs'] <= ref['startMs']]
        if not preceding:
            continue
        target = preceding[-1]
        if not any(existing['sourceId'] == ref['sourceId'] for existing in target['evidenceRefs']):
            target['evidenceRefs'].append(ref)
            target['evidenceRefs'].sort(key=lambda evidence: evidence['startMs'])
            target['endMs'] = max(evidence['endMs'] for evidence in target['evidenceRefs'])
'''
 assert anchor in s;s=s.replace(anchor,block+anchor);p.write_text(s,encoding='utf-8')
