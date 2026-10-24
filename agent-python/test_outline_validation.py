"""Regression tests for conservative, non-mutating OCR classification validation."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import course_outline as outline
from course_mind_map import finalize_course_reply
from model_diagnostics import close_logs
class OutlineValidationTests(unittest.TestCase):
 def raw(self,title='存储器分类',children=()):return {'topic':'课','children':[{'title':title,'imageIds':['frame_1'],'sourceIds':[],'children':[{'title':t,'imageIds':['frame_1'],'children':[],'details':[]} for t in children],'details':[]}],'examples':[],'uncertainties':[]}
 def hint(self,parent='存储器分类',headings=None):return {'imageId':'frame_1','parentLabels':[parent],'headings':headings or ['1.半导体存储器','2.磁表面存储器：磁盘、磁带']}
 def report(self,raw,hints):return outline.audit_outline_report(raw,hints)
 def payload(self,hints):return dict(concepts=[],examples=[],connections=[],sourceEvidence=[],imageEvidence=[dict(sourceType='image',sourceId='frame_1',startMs=1,endMs=1,quote='课件')],firstHandSourceIds=[],firstHandImageIds=['frame_1'],uncertainties=[],_directEvidence=True,outlineHints=hints)
 def test_decimal_and_intermediate_calculations_are_not_categories(self):
  raw=self.raw('浮点数的计算');hint=self.hint('浮点数的计算',['9.85211×10^{12+','19.96007×1010','0.0996007×10^12','9.9517107 × 10^{12 → 9.95171 × 10^{12'])
  self.assertEqual(outline.audit_outline(raw,[hint]),[])
 def test_colon_explanation_does_not_require_literal_heading(self):
  raw=self.raw(children=['半导体存储器','磁表面存储器'])
  self.assertEqual(outline.audit_outline(raw,[self.hint()]),[])
 def test_enumerated_members_in_same_branch_cover_descriptive_label(self):
  raw=self.raw(children=['半导体存储器','磁盘','磁带'])
  self.assertEqual(outline.audit_outline(raw,[self.hint()]),[])
 def test_similar_text_in_other_branch_cannot_cover_missing_category(self):
  raw=self.raw(children=['半导体存储器']);raw['children'].append({'title':'其他课程','children':[{'title':'磁盘'},{'title':'磁带'}]})
  report=self.report(raw,[self.hint()]);self.assertEqual(len(report['errors']),1)
 def test_uncertain_ocr_marks_review_without_failing_usable_map(self):
  hint=self.hint('存储系统基础',['1.半导体存储器','3.磁表面存储器：磁盘、磁带']);raw=self.raw('存储系统基础',['半导体存储器'])
  result=finalize_course_reply(raw,self.payload([hint]),'test')
  self.assertEqual(result['status'],'completed');self.assertTrue(any('待核对' in s for s in result['uncertainties']))
 def test_confirmed_sequence_under_explicit_classification_still_fails_on_missing(self):
  raw=self.raw(children=['半导体存储器']);hint=self.hint()
  report=self.report(raw,[hint]);self.assertEqual(len(report['errors']),1);self.assertEqual(report['warnings'],[])
  result=finalize_course_reply(raw,self.payload([hint]),'test');self.assertEqual(result['status'],'failed')
 def test_ocr_corruption_is_review_only_and_not_guessed(self):
  raw=self.raw(children=['半导体存储器']);hint=self.hint(headings=['1.半导体存储器','2.磁??存储器'])
  report=self.report(raw,[hint]);self.assertEqual(report['errors'],[]);self.assertTrue(report['warnings'])
 def test_details_and_examples_do_not_replace_real_classifications(self):
  for target in ['details','examples']:
   raw=self.raw(children=['半导体存储器'])
   if target=='details':raw['children'][0]['details']=[{'title':'磁表面存储器','imageIds':['frame_1']}]
   else:raw['examples']=[{'title':'磁表面存储器','imageIds':['frame_1']}]
   self.assertTrue(self.report(raw,[self.hint()])['errors'])
 def test_raw_and_hints_are_not_mutated_and_nodes_are_not_rewritten(self):
  raw=self.raw(children=['半导体存储器','磁盘','磁带']);hints=[self.hint()];before=copy.deepcopy((raw,hints))
  self.report(raw,hints);self.assertEqual((raw,hints),before)
 def test_audit_diagnostics_record_counts_without_ocr_or_titles(self):
  raw=self.raw('PRIVATE分类',['半导体存储器']);hint=self.hint('PRIVATE分类');task='11111111-1111-1111-1111-111111111111'
  with tempfile.TemporaryDirectory() as tmp:
   try:
    with patch.dict(os.environ,{'MODEL_LOG_DIR':tmp}):
     payload=self.payload([hint]);payload['_diagnosticTaskId']=task;finalize_course_reply(raw,payload,'test')
    logs=(Path(tmp)/'model-events.jsonl').read_text();self.assertIn('outline_validation',logs);self.assertIn('outline_missing_count',logs);self.assertNotIn('PRIVATE',logs)
   finally:close_logs()
if __name__=='__main__':unittest.main()
