"""Offline known-reference normalization, refusal and privacy regressions."""
import json,os,tempfile,unittest,copy
from pathlib import Path
from unittest.mock import patch
from course_mind_map import finalize_course_reply
from model_diagnostics import close_logs
class CitationRepairTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  env=patch.dict(os.environ,{'MODEL_LOG_DIR':str(self.root/'logs')});env.start();self.addCleanup(env.stop);self.addCleanup(close_logs)
  self.payload=dict(_diagnosticTaskId='11111111-1111-4111-8111-111111111111',_directEvidence=True,concepts=[],examples=[],connections=[],sourceEvidence=[dict(sourceType='transcript',sourceId='t_1',startMs=100,endMs=200,quote='PRIVATE_COURSE')],imageEvidence=[dict(sourceType='image',sourceId='frame_1000',startMs=1000,endMs=1000,quote='课件截图')],firstHandSourceIds=['t_1'],firstHandImageIds=['frame_1000'],uncertainties=[],outlineHints=[])
 def reply(self):return dict(topic='课',children=[dict(title='PRIVATE_TITLE',sourceIds=['t_1'],imageIds=['frame_1000'],children=[],details=[])],examples=[],uncertainties=[])
 def finish(self,raw):return finalize_course_reply(raw,self.payload,'test',diagnostic_root=self.root)
 def report(self):return json.loads((self.root/'.map-validation/latest.json').read_text())
 def test_exact_known_ids_in_wrong_fields_and_whitespace_are_repaired(self):
  raw=self.reply();raw['children'][0].update(sourceIds=[' frame_1000 '],imageIds=['t_1'])
  saved=copy.deepcopy(raw);result=self.finish(raw)
  self.assertEqual(result['status'],'completed');self.assertEqual(raw,saved)
  refs=result['root']['children'][0]['evidenceRefs'];self.assertEqual({r['sourceId'] for r in refs},{'t_1','frame_1000'})
  self.assertEqual([r['startMs'] for r in refs],[100,1000]);self.assertGreater(self.report()['repaired_count'],0)
 def test_works_for_detail_and_example_references(self):
  raw=self.reply();raw['children'][0]['details']=[dict(title='条件',sourceIds=['frame_1000'])];raw['examples']=[dict(title='例题',imageIds=['t_1'])]
  result=self.finish(raw);self.assertEqual(result['status'],'completed');self.assertEqual(len(result['examples']),1)
 def test_unknown_id_is_not_guessed_or_silently_dropped(self):
  raw=self.reply();raw['children'].append(dict(title='未证实',imageIds=['frame_1001'],children=[]))
  result=self.finish(raw);self.assertEqual(result['status'],'failed');self.assertEqual(len(result['root']['children']),1)
  issue=self.report()['issues'][0];self.assertEqual(issue['node_path'],'children[1]');self.assertEqual(issue['reference_id'],'frame_1001');self.assertEqual(issue['reason'],'reference_unknown')
 def test_true_knowledge_example_scope_error_still_rejected(self):
  self.payload.update(firstHandSourceIds=[],firstHandImageIds=[],concepts=[dict(id='page_1_knowledge_1',title='核心',kind='concept',sourceIds=['t_1'],imageIds=[],details=[])],examples=[dict(id='page_2_example_1',title='题',sourceIds=[],imageIds=['frame_1000'])])
  raw=self.reply();raw['children'][0]['candidateIds']=['page_1_knowledge_1'];raw['examples']=[dict(title='题',candidateIds=['page_2_example_1'],imageIds=['frame_1000'])]
  result=self.finish(raw);self.assertEqual(result['status'],'failed');self.assertTrue(any(i['reason']=='reference_disallowed' for i in self.report()['issues']))
 def test_invalid_list_shape_and_private_unknown_ids_are_safe(self):
  raw=self.reply();raw['children'][0]['sourceIds']='t_1';self.assertEqual(self.finish(raw)['status'],'failed')
  raw=self.reply();raw['children'][0]['imageIds']=['SECRET_KEY_PRIVATE_REPLY'];self.finish(raw)
  text=(self.root/'.map-validation/latest.json').read_text()+(self.root/'logs/model-events.jsonl').read_text()
  for private in ['PRIVATE_COURSE','PRIVATE_TITLE','SECRET_KEY_PRIVATE_REPLY']:self.assertNotIn(private,text)
 def test_diagnostic_write_failure_does_not_destroy_good_map(self):
  with patch('course_citations.save_report',side_effect=OSError('disk full')):
   self.assertEqual(self.finish(self.reply())['status'],'completed')
 def test_oversized_ids_are_redacted_in_report_messages_and_logger(self):
  from model_diagnostics import record_event
  oversized='t_'+'9'*100000
  raw=self.reply();raw['children'][0]['sourceIds']=[oversized];result=self.finish(raw)
  record_event('diagnostic_check',operation='course_map',stage='validation',reference_id=oversized)
  report=(self.root/'.map-validation/latest.json').read_text();logs=(self.root/'logs/model-events.jsonl').read_text()
  self.assertNotIn(oversized,report+logs+json.dumps(result));self.assertLess(len(report),4000);self.assertLess(len(logs),6000)
 def test_report_rows_are_bounded_and_mixed_valid_unknown_node_still_rejects(self):
  raw=self.reply();raw['children'][0]['imageIds']=['frame_1000']+[f'frame_{i+2000}' for i in range(300)]
  result=self.finish(raw);self.assertEqual(result['status'],'failed');self.assertEqual(result['root']['children'],[])
  report=self.report();self.assertEqual(len(report['issues']),128);self.assertEqual(report['issue_count'],300);self.assertEqual(report['omitted_count'],172)
 def test_missing_knowledge_source_has_exact_path_in_report_and_result(self):
  raw=self.reply();raw['children'].append(dict(title='PRIVATE_MISSING',sourceIds=[],imageIds=[],children=[],details=[]))
  result=self.finish(raw);self.assertEqual(result['status'],'failed')
  issue=self.report()['issues'][0];self.assertEqual(issue['node_path'],'children[1]');self.assertEqual(issue['reason'],'reference_missing')
  self.assertTrue(any('children[1]' in x and 'PRIVATE_MISSING' in x for x in result['uncertainties']))
  self.assertNotIn('PRIVATE_MISSING',json.dumps(self.report()))
 def test_missing_detail_and_example_are_located_without_flagging_grounded_parent(self):
  raw=self.reply();raw['children'][0]['details']=[dict(title='detail',sourceIds=[],imageIds=[])];raw['examples']=[dict(title='example',sourceIds=[],imageIds=[])]
  result=self.finish(raw);self.assertEqual(result['status'],'failed')
  paths={x['node_path'] for x in self.report()['issues']};self.assertIn('children[0].details[0]',paths);self.assertIn('examples[0]',paths)
 def test_parent_can_inherit_grounded_child_without_missing_source_warning(self):
  raw=self.reply();raw['children']=[dict(title='module',sourceIds=[],imageIds=[],children=raw['children'])]
  self.assertEqual(self.finish(raw)['status'],'completed');self.assertEqual(self.report()['issue_count'],0)
if __name__=='__main__':unittest.main()
