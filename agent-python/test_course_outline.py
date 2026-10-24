import copy,tempfile,unittest
from pathlib import Path
import cv2,numpy as np
from course_outline import normalize_reply,outline_hints,audit_outline
from course_mind_map import finalize_course_reply

class OutlineTests(unittest.TestCase):
 def test_independent_formula_details_become_children_with_original_sources(self):
  raw={'topic':'课','children':[{'title':'增长量公式','details':[{'title':'公式一：增长量=现期-基期（已知现期、基期）','sourceIds':['s'],'imageIds':[]}],'children':[]}],'examples':[],'uncertainties':[]}
  original=copy.deepcopy(raw);value=normalize_reply(raw);node=value['children'][0]
  self.assertEqual(len(node['children']),1);self.assertEqual(node['children'][0]['sourceIds'],['s'])
  self.assertIn('已知现期',node['children'][0]['details'][0]['title']);self.assertEqual(raw,original)
 def test_conditions_remain_details_and_typed_methods_become_children(self):
  raw={'children':[{'title':'计算','children':[],'details':[{'kind':'method','title':'先减再加','sourceIds':['s']},{'kind':'condition','title':'量纲保持一致','sourceIds':['s']}]}]}
  node=normalize_reply(raw)['children'][0]
  self.assertEqual([n['title'] for n in node['children']],['先减再加']);self.assertEqual([n['title'] for n in node['details']],['量纲保持一致'])
 def test_explicit_classification_cannot_be_silently_omitted(self):
  hints=[{'imageId':'frame_1','parentLabels':['增长量计算'],'headings':['1.给基期、增长率','2.给现期、基期','3.给现期、增长率']}]
  self.assertTrue(audit_outline({'children':[{'title':'增长量计算','imageIds':['frame_1'],'children':[],'details':[]}]},hints))
  children=[{'title':t,'children':[]} for t in hints[0]['headings']]
  self.assertEqual(audit_outline({'children':[{'title':'增长量计算','imageIds':['frame_1'],'children':children}]},hints),[])
 def test_detail_calculation_in_an_example_is_not_promoted(self):
  raw={'children':[{'title':'本题分析','details':[{'title':'公式一：本题代入结果20','sourceIds':['s']}],'children':[]}],'examples':[{'title':'例题'}]}
  self.assertEqual(normalize_reply(raw)['children'][0]['children'],[])
 def test_no_minimum_node_count_and_shared_finalizer_preserves_citations(self):
  payload=dict(concepts=[],examples=[],connections=[],sourceEvidence=[dict(sourceType='transcript',sourceId='s',startMs=100,endMs=200,quote='条件')],imageEvidence=[],firstHandSourceIds=['s'],firstHandImageIds=[],uncertainties=[],_directEvidence=True)
  raw=dict(topic='课',children=[dict(title='独立概念',sourceIds=['s'],children=[],details=[])],examples=[],uncertainties=[])
  value=finalize_course_reply(raw,payload,'test');self.assertEqual(value['status'],'completed');self.assertEqual(len(value['root']['children']),1)
 def test_numbered_ocr_hints_are_filtered_and_bound_to_real_frames(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);cv2.imwrite(str(root/'1.jpg'),np.full((30,50,3),150,np.uint8))
   visuals=[dict(frameTimeMs=1,ocrBlocks=[dict(text=t) for t in ['增长量计算','1.给基期、增长率','2.给现期、基期','3.给现期、增长率']])]
   hints=outline_hints(visuals,root,{})
   self.assertEqual(hints[0]['imageId'],'frame_1');self.assertEqual(len(hints[0]['headings']),3)

 def test_both_modes_use_identical_hierarchy_and_keep_examples_separate(self):
  import course_mind_map as course
  from direct_course_map import build_direct_course_map
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);cv2.imwrite(str(root/'1.jpg'),np.full((30,50,3),150,np.uint8))
   visuals=[dict(frameTimeMs=1,ocrBlocks=[dict(text=t) for t in ['增长量计算','1.给基期、增长率','2.给现期、基期','3.给现期、增长率']])]
   segments=[dict(id='s',startMs=0,endMs=10,text='课程知识')]
   pages=[dict(pageIndex=0,firstFrameTimeMs=1,lastFrameTimeMs=1,memberFrameTimesMs=[1],representativeFrameTimesMs=[1])]
   raw=dict(topic='课',children=[dict(title='增长量计算',imageIds=['frame_1'],children=[dict(title=t,imageIds=['frame_1'],children=[]) for t in ['给基期、增长率','给现期、基期','给现期、增长率']])],examples=[dict(title='独立例题',imageIds=['frame_1'])],uncertainties=[])
   grouped=course.build_course_mind_map(segments,pages,visuals,root,ask_json=lambda *_:copy.deepcopy(raw))
   direct=build_direct_course_map(segments,pages,visuals,root,ask_json=lambda *_:copy.deepcopy(raw))
   self.assertEqual(grouped['status'],'completed');self.assertEqual(direct['status'],'completed')
   self.assertEqual(grouped['root']['children'],direct['root']['children'])
   self.assertEqual(len(direct['root']['children'][0]['children']),3);self.assertEqual(len(direct['examples']),1)
   incomplete=copy.deepcopy(raw);incomplete['children'][0]['children']=[]
   result=build_direct_course_map(segments,pages,visuals,root,ask_json=lambda *_:incomplete)
   self.assertEqual(result['status'],'completed');self.assertTrue(any('缺少子节点' in x and '仅供核对' in x for x in result['uncertainties']))

 def test_formula_parentheses_are_preserved(self):
  raw={'children':[{'title':'公式','children':[],'details':[{'title':'公式三：增长量=现期/(1+r)×r（已知现期、增长率）','sourceIds':['s']}]}]}
  title=normalize_reply(raw)['children'][0]['children'][0]['title']
  self.assertEqual(title,'公式三：增长量=现期/(1+r)×r')


class SameFrameClassificationAuditTests(unittest.TestCase):
 def fixture(self):
  headings=['1.给基期、增长率','2.给现期、基期','3.给现期、增长率']
  small={'title':'方法二：先加再减','imageIds':['frame_1182000'],'children':[{'title':'总的增长量=总现期-总基期','children':[]}]}
  categories=[{'title':title,'children':[]} for title in headings]
  categories[1]['children']=[{'title':'主体为多个数加和','children':[small]}]
  raw={'children':[{'title':'增长量计算方法','children':categories}]}
  hints=[{'imageId':'frame_1182000','parentLabels':['方法二：先加再减'],'headings':headings}]
  return raw,hints
 def test_same_frame_submethod_does_not_own_three_main_categories(self):
  raw,hints=self.fixture()
  self.assertEqual(audit_outline(raw,hints),[])
 def test_real_missing_category_is_still_reported_once_for_course_branch(self):
  raw,hints=self.fixture();raw['children'][0]['children'].pop()
  errors=audit_outline(raw,hints)
  self.assertEqual(len(errors),1)
  self.assertIn('3.给现期、增长率',errors[0])
  self.assertNotIn('1.给基期、增长率',errors[0])
  self.assertNotIn('先加再减 缺少',errors[0])
 def test_similarly_named_node_in_unrelated_branch_does_not_hide_omission(self):
  raw,hints=self.fixture();missing=raw['children'][0]['children'].pop()
  raw['children'].append({'title':'不相关课程分支','children':[missing]})
  self.assertTrue(audit_outline(raw,hints))
 def test_details_or_examples_are_not_substitutes_for_category_nodes(self):
  for target in ('details','examples'):
   raw,hints=self.fixture();missing=raw['children'][0]['children'].pop()
   if target=='details':raw['children'][0]['details']=[missing]
   else:raw['examples']=[missing]
   self.assertTrue(audit_outline(raw,hints))
 def test_checker_never_moves_or_mutates_nodes(self):
  raw,hints=self.fixture();before=copy.deepcopy((raw,hints))
  audit_outline(raw,hints)
  self.assertEqual((raw,hints),before)
 def test_parent_label_without_image_binding_does_not_trigger_check(self):
  raw,hints=self.fixture();hints[0]['imageId']='frame_other'
  raw['children'][0]['children'].pop()
  self.assertEqual(audit_outline(raw,hints),[])
 def test_multiple_labels_on_one_slide_do_not_duplicate_missing_reports(self):
  raw,hints=self.fixture();raw['children'][0]['children'].pop()
  node=raw['children'][0]['children'][1]['children'][0]
  node['children'].append({'title':'方法一：先减再加','imageIds':['frame_1182000'],'children':[]})
  hints[0]['parentLabels'].append('方法一：先减再加')
  self.assertEqual(len(audit_outline(raw,hints)),1)
