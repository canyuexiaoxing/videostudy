"""Offline contract tests for the opt-in output-pagination experiment."""
import copy,unittest
from experimental_batched_map import validate_plan,assemble_batches,run_batched
class BatchMapTests(unittest.TestCase):
 def plan(self):return {'topic':'课程','nodes':[{'id':'n1','parentId':None,'title':'模块','kind':'category'},{'id':'n2','parentId':'n1','title':'公式','kind':'formula'}],'examples':[{'id':'e1','title':'例题'}],'uncertainties':[]}
 def item(self,id):return {'id':id,'sourceIds':['t_1'],'imageIds':[],'details':[]}
 def batches(self):return [{'batchId':'b1','items':[self.item('n1'),self.item('n2')],'uncertainties':[]},{'batchId':'b2','items':[self.item('e1')],'uncertainties':[]}]
 def test_plan_rejects_duplicate_ids(self):
  p=self.plan();p['examples'][0]['id']='n1'
  with self.assertRaises(ValueError):validate_plan(p)
 def test_plan_rejects_unbound_or_cyclic_parents(self):
  for parent in ['missing','n2']:
   p=self.plan();p['nodes'][0]['parentId']=parent
   with self.assertRaises(ValueError):validate_plan(p)
 def test_assembly_freezes_hierarchy_and_order_without_mutating_inputs(self):
  p=self.plan();b=self.batches();before=copy.deepcopy((p,b));raw=assemble_batches(p,b)
  self.assertEqual(raw['children'][0]['title'],'模块');self.assertEqual(raw['children'][0]['children'][0]['title'],'公式');self.assertEqual(raw['examples'][0]['title'],'例题');self.assertEqual((p,b),before)
 def test_missing_extra_duplicate_or_wrong_parent_records_are_rejected(self):
  for change in ['missing','extra','duplicate','parent']:
   b=self.batches()
   if change=='missing':b[0]['items'].pop()
   if change=='extra':b[0]['items'].append(self.item('n99'))
   if change=='duplicate':b[0]['items'].append(self.item('n1'))
   if change=='parent':b[0]['items'][1]['parentId']=None
   with self.assertRaises(ValueError):assemble_batches(self.plan(),b)
 def test_empty_leaf_citations_and_unknown_sources_are_rejected(self):
  for field,value in [('sourceIds',[]),('sourceIds',['t_unknown']),('imageIds',['img_unknown'])]:
   b=self.batches();b[0]['items'][1][field]=value
   with self.assertRaises(ValueError):assemble_batches(self.plan(),b,allowed_sources={'t_1'},allowed_images={'img_1'})
 def test_full_input_and_history_survive_every_output_batch(self):
  base={'messages':[{'role':'system','content':'original instructions'},{'role':'user','content':[{'type':'text','text':'FULL_TRANSCRIPT'},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,TEST'}}]}],'max_tokens':393216};before=copy.deepcopy(base);calls=[]
  def send(body,phase,index):
   calls.append(copy.deepcopy(body))
   if phase=='plan':return self.plan()
   ids=['n1','n2'] if index==1 else ['e1'];return {'batchId':'b'+str(index),'items':[self.item(id) for id in ids],'uncertainties':[]}
  raw,report=run_batched(base,send,batch_size=2,allowed_sources={'t_1'},allowed_images={'img_1'})
  self.assertEqual(len(calls),3);self.assertEqual(base,before);self.assertEqual(report['batches'],2)
  for body in calls:self.assertEqual(body['messages'][:2],base['messages'])
  self.assertGreater(len(calls[-1]['messages']),len(calls[0]['messages']));self.assertEqual(raw['children'][0]['children'][0]['title'],'公式')
 def test_wrong_batch_id_does_not_get_assembled(self):
  def send(body,phase,index):
   return self.plan() if phase=='plan' else {'batchId':'wrong','items':[],'uncertainties':[]}
  with self.assertRaises(ValueError):run_batched({'messages':[]},send,batch_size=2)
 def test_short_parts_still_keep_formula_text_and_references(self):
  b=self.batches();formula=r'条件：x>0，\\(\\frac{a}{b}\\)';b[0]['items'][1]['details']=[{'title':formula,'kind':'condition','sourceIds':['t_1'],'imageIds':[]}]
  raw=assemble_batches(self.plan(),b,allowed_sources={'t_1'},allowed_images=set())
  self.assertEqual(raw['children'][0]['children'][0]['details'][0]['title'],formula)
 def test_nonpositive_batch_size_fails_before_provider(self):
  with self.assertRaises(ValueError):run_batched({'messages':[]},lambda *args: self.fail('provider called'),batch_size=0)
if __name__=='__main__':unittest.main()
