import unittest
from knowledge_outline import organize_chapters

def unit(i,key='洛必达法则'):
 ref=dict(sourceType='transcript',sourceId='t_'+str(i),startMs=i*1000,endMs=i*1000+900,quote='洛必达法则的适用条件')
 return dict(id='n_'+str(i),title='洛必达法则的说明',startMs=ref['startMs'],endMs=ref['endMs'],evidenceRefs=[ref],children=[],_conceptKey=key,_subject='极限计算')
class KnowledgeOutlineTest(unittest.TestCase):
 def test_same_concept_in_multiple_chunks_is_merged_locally_with_all_quotes(self):
  result=organize_chapters([dict(id='a',title='前段',children=[unit(1)]),dict(id='b',title='后段',children=[unit(8)])])
  self.assertEqual(len(result),1);node=result[0]['children'][0]
  self.assertEqual(node['title'],'洛必达法则');self.assertEqual([r['sourceId'] for r in node['evidenceRefs']],['t_1','t_8'])
  self.assertNotIn('_conceptKey',str(result))
 def test_unknown_or_overbroad_key_does_not_merge_different_topics(self):
  result=organize_chapters([dict(id='a',title='知识',children=[unit(1,'不存在的公式'),unit(8,'公式')])])
  self.assertEqual(len(result[0]['children']),2)
 def test_missing_labels_preserve_legacy_chapter_structure(self):
  n=unit(1);n.pop('_conceptKey');result=organize_chapters([dict(id='a',title='原主题',children=[n])])
  self.assertEqual(result[0]['id'],'a');self.assertEqual(result[0]['children'][0]['title'],'洛必达法则的说明')

 def test_merged_leaf_conditions_are_retained_as_concept_details(self):
  first=unit(1);second=unit(8)
  first['title']='洛必达法则要求导数分母非零';second['title']='洛必达法则适用于零比零或无穷比无穷型'
  result=organize_chapters([dict(id='a',title='极限计算',children=[first,second])]);node=result[0]['children'][0]
  self.assertEqual([c['title'] for c in node['children']],[first['title'],second['title']])
  self.assertEqual(node['children'][0]['evidenceRefs'][0]['sourceId'],'t_1')
