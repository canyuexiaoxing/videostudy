from pathlib import Path
p=Path('E:/workp/videostudy/agent-python/test_analysis_region.py')
with p.open('a',encoding='utf-8') as out:out.write('''
 def test_actual_vision_payload_only_contains_effective_pixels(self):
  import base64,json,io
  from unittest.mock import patch
  from page_understanding import _deepseek_page_json
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'0.jpg';original=np.zeros((100,100,3),dtype=np.uint8);cv2.imwrite(str(path),original);saved=path.read_bytes()
   reply={'title':'test','content':'test','visualElements':[],'uncertainties':[],'occlusion':{'hasOcclusion':False,'criticalContentMissing':False,'speechCoversMissing':False},'confirmedContent':'test','inferences':[],'unresolvedPoints':[],'corrections':[],'conflicts':[],'calculationChecks':[]}
   def provider(request,timeout):
    payload=json.loads(request.data);content=payload['messages'][1]['content'];image_url=next(item['image_url']['url'] for item in content if item['type']=='image_url')
    image=cv2.imdecode(np.frombuffer(base64.b64decode(image_url.split(',')[1]),dtype=np.uint8),cv2.IMREAD_COLOR)
    self.assertGreater(image[5,5].mean(),240);self.assertLess(image[30,30].mean(),20);self.assertGreater(image[65,65].mean(),240)
    self.assertNotIn('_visualRegions',content[0]['text'])
    return io.BytesIO(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(reply)}}]}).encode())
   with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'test'}),patch('page_understanding.urlopen',side_effect=provider):
    _deepseek_page_json({'route':'both','_visualRegions':self.setting(dict(x=.6,y=.6,width=.2,height=.2))},[(0,path)])
   self.assertEqual(path.read_bytes(),saved)
 def test_actual_ocr_input_is_masked_without_modifying_saved_frame(self):
  from unittest.mock import patch
  from visual_evidence import analyze_visuals
  frame=np.zeros((100,100,3),dtype=np.uint8);inputs=[]
  with patch('visual_evidence._has_video',return_value=True),patch('visual_evidence._candidate_times',return_value=[0]),patch('visual_evidence._frames_at',return_value=[(0,frame)]):
   analyze_visuals(Path('unused'),recognize=lambda image:inputs.append(image.copy()) or [],ignore_region=self.setting())
  self.assertEqual(inputs[0][5,5,0],255);self.assertEqual(inputs[0][30,30,0],0);self.assertFalse(frame.any())
''')
