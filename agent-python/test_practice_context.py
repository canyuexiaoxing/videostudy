import unittest,tempfile,copy,json,os
from unittest.mock import patch
from uuid import uuid4
from pathlib import Path
import cv2,numpy as np
from map_conversation import save_map_conversation,load_map_conversation,image_content,map_fingerprint
from practice_materials import related_materials,practice_messages

class ContextTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.id=str(uuid4());self.root=self.base/self.id;self.root.mkdir()
  self.speech=[dict(id='s1',startMs=0,endMs=900,text='增长量公式'),dict(id='s2',startMs=1000,endMs=1900,text='增长量例题'),dict(id='s3',startMs=2000,endMs=2900,text='几何无关')]
  self.visuals=[dict(frameTimeMs=t,ocrBlocks=[]) for t in (0,1000,2000)]
  self.pages=[dict(pageIndex=i+1,firstFrameTimeMs=t,lastFrameTimeMs=t,memberFrameTimesMs=[t],representativeFrameTimesMs=[t]) for i,t in enumerate((0,1000,2000))]
  for i,t in enumerate((0,1000,2000)):cv2.imwrite(str(self.root/f'{t}.jpg'),np.full((40,60,3),100+i*30,np.uint8))
  def ref(t):return dict(sourceType='image',sourceId=f'frame_{t}',startMs=t,endMs=t,quote='课件截图')
  self.node=dict(id='n',title='增长量计算',startMs=0,endMs=0,evidenceRefs=[ref(0)],children=[],details=[])
  self.example=dict(id='e',title='增长量计算例题',startMs=1000,endMs=1000,evidenceRefs=[ref(1000)],children=[],details=[])
  self.other=dict(id='other',title='圆的面积',startMs=2000,endMs=2000,evidenceRefs=[ref(2000)],children=[],details=[])
  self.map=dict(status='completed',promptVersion='test',root=dict(id='course',title='课程',children=[self.node],evidenceRefs=[]),examples=[self.example,self.other])
 def test_snapshot_replays_input_reply_and_images_but_no_key(self):
  payload=dict(sourceEvidence=[],images='all evidence',_visualRegionsByFrame={})
  save_map_conversation(self.root,payload,[(0,self.root/'0.jpg','original')],{'topic':'课程','children':[]},self.map,'original system')
  snapshot=load_map_conversation(self.root,self.map)
  messages=practice_messages('map_context',dict(nodes=[self.node]),snapshot,'practice system')
  self.assertEqual(messages[0]['content'],'original system')
  self.assertEqual(json.loads(messages[2]['content'])['topic'],'课程')
  self.assertEqual(messages[3]['role'],'system');self.assertEqual(len(messages),5)
  self.assertEqual(messages[1]['content'][0]['text'],json.dumps({'sourceEvidence':[],'images':'all evidence'},ensure_ascii=False))
  self.assertEqual(len(list((self.root/'.map-context').glob('*.json'))),1)
 def test_changed_map_or_image_cannot_reuse_context(self):
  save_map_conversation(self.root,{},[(0,self.root/'0.jpg','original')],{},self.map,'system')
  changed=copy.deepcopy(self.map);changed['root']['children'][0]['title']='changed'
  with self.assertRaises(ValueError):load_map_conversation(self.root,changed)
  cv2.imwrite(str(self.root/'0.jpg'),np.full((40,60,3),0,np.uint8))
  with self.assertRaises(ValueError):load_map_conversation(self.root,self.map)
 def test_related_includes_knowledge_and_example_but_excludes_unrelated(self):
  data=related_materials([self.node],self.pages,self.map,self.speech,self.visuals,self.root,'n')
  self.assertEqual([e['id'] for e in data['referenceExamples']],['e'])
  self.assertEqual([image['frameTimeMs'] for image in data['_images']],[0,1000])
  self.assertEqual(data['knowledgeHierarchy']['id'],'n')
  messages=practice_messages('related_materials',{'nodes':[self.node]},data,'system')
  self.assertEqual(len(messages),2);self.assertEqual(sum(c['type']=='image_url' for c in messages[1]['content']),2)
 def test_missing_required_image_fails_without_provider(self):
  (self.root/'1000.jpg').unlink()
  with self.assertRaises(ValueError):related_materials([self.node],self.pages,self.map,self.speech,self.visuals,self.root,'n')
 def test_mask_preserves_resolution_and_dedup_retains_alias_ids(self):
  from base64 import b64decode
  cv2.imwrite(str(self.root/'1000.jpg'),cv2.imread(str(self.root/'0.jpg')))
  data=related_materials([self.node],self.pages,self.map,self.speech,self.visuals,self.root,'n',{'x':0,'y':0,'width':.5,'height':1})
  content=image_content(data['_images'])
  self.assertEqual(sum(c['type']=='image_url' for c in content),1)
  self.assertIn('frame_1000',content[0]['text'])
  encoded=next(c for c in content if c['type']=='image_url')['image_url']['url'].split(',')[1]
  image=cv2.imdecode(np.frombuffer(b64decode(encoded),np.uint8),cv2.IMREAD_COLOR)
  self.assertEqual(image.shape[:2],(40,60));self.assertGreater(image[20,10,0],245);self.assertLess(image[20,50,0],150)

 def test_api_missing_context_never_calls_provider(self):
  import app
  from fastapi import HTTPException
  with patch.dict(os.environ,{'KEYFRAME_DIR':str(self.base)}),patch('practice.ask') as provider:
   with self.assertRaises(HTTPException) as error:app.practice(app.PracticeRequest(nodes=[self.node],mode='map_context',courseId=self.id,mindMap=self.map))
   self.assertIn('practice_map_context_missing',str(error.exception.detail));provider.assert_not_called()
 def test_api_related_sends_two_images_once_and_retains_exam_scope(self):
  import app
  calls=[]
  with patch.dict(os.environ,{'KEYFRAME_DIR':str(self.base)}),patch('practice.ask',side_effect=lambda p:calls.append(p) or {'questions':[]}):
   result=app.practice(app.PracticeRequest(nodes=[self.node],mode='related_materials',courseId=self.id,scopeNodeId='n',mindMap=self.map,sourceSegments=self.speech,pageGroups=self.pages,visualEvidence=self.visuals))
  self.assertEqual(len(calls),2);self.assertEqual(calls[1]['_messages'][:len(calls[0]['_messages'])],calls[0]['_messages']);self.assertEqual(result['practiceMode'],'related_materials');self.assertEqual(result['imageCount'],2)
  self.assertEqual(sum(c['type']=='image_url' for c in calls[0]['_messages'][1]['content']),2)
 def test_completed_direct_map_saves_context_and_java_null_details_match(self):
  from direct_course_map import build_direct_course_map
  response={'topic':'课程','children':[{'title':'增长量','imageIds':['frame_0'],'children':[],'details':[]}],'examples':[],'uncertainties':[]}
  with patch('course_mind_map._deepseek_course_json',return_value=response):result=build_direct_course_map(self.speech,self.pages,self.visuals,self.root)
  self.assertEqual(result['status'],'completed')
  snapshot=load_map_conversation(self.root,result);self.assertEqual(len(snapshot['_images']),3)
  roundtrip=copy.deepcopy(result);roundtrip.pop('mindMapMode',None)
  self.assertEqual(map_fingerprint(result),map_fingerprint(roundtrip))
 def test_out_of_scope_questions_rejected_even_with_full_course_context(self):
  from practice import generate_practice
  save_map_conversation(self.root,{},[],{},self.map,'system');context=load_map_conversation(self.root,self.map)
  q=dict(nodeId='n',sourceIds=['frame_2000'],kind='single',task='concept',title='超出范围',prompt='不相关问题',options=['A','B','C','D'],answerIndex=0,explanation='解释',distractorReasons=['','原因','原因','原因'],takeaway='重点',diagram=None,calculation=None)
  result=generate_practice([self.node],[],3,'basic',lambda _:{'questions':[q]},mode='map_context',context=context,fill_missing=False)
  self.assertEqual(result['rejectedCount'],1);self.assertEqual(result['questions'],[])

 def test_supplementary_frame_is_included_even_when_not_representative(self):
  cv2.imwrite(str(self.root/'500.jpg'),np.full((40,60,3),180,np.uint8))
  self.visuals.append(dict(frameTimeMs=500,ocrBlocks=[]));self.pages[0]['memberFrameTimesMs'].append(500)
  self.node['evidenceRefs'].append(dict(sourceType='image',sourceId='frame_500',startMs=500,endMs=500,quote='课件截图'))
  data=related_materials([self.node],self.pages,self.map,self.speech,self.visuals,self.root,'n')
  self.assertEqual([image['frameTimeMs'] for image in data['_images']],[0,500,1000])
 def test_new_generation_timestamp_cannot_reuse_old_snapshot(self):
  save_map_conversation(self.root,{},[],{},self.map,'system')
  changed=copy.deepcopy(self.map);changed['createdAt']='new-generation'
  with self.assertRaises(ValueError):load_map_conversation(self.root,changed)

 def test_http_transport_replays_messages_without_live_call(self):
  import practice
  class Reply:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'{"questions":[]}'}}]}).encode()
  save_map_conversation(self.root,{'speech':'original input'},[(0,self.root/'0.jpg','original')],{'topic':'原导图'},self.map,'original system')
  context=load_map_conversation(self.root,self.map)
  messages=practice_messages('map_context',{'nodes':[self.node]},context,'practice system');calls=[]
  def transport(request,timeout):calls.append(json.loads(request.data));return Reply()
  with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'TEST_FAKE_KEY'}),patch('practice.urlopen',side_effect=transport):result=practice.ask({'_messages':messages})
  self.assertEqual(result,{'questions':[]});self.assertEqual(len(calls),1)
  self.assertEqual(calls[0]['messages'],messages)
  self.assertNotIn('TEST_FAKE_KEY',next((self.root/'.map-context').glob('*.json')).read_text())
