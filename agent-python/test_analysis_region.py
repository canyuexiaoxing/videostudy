import unittest,copy,cv2,numpy as np,tempfile
from pathlib import Path
from ignored_region import normalize_setting,effective_mask,prepare_image,filter_frame
class AnalysisRegionTest(unittest.TestCase):
 def setting(self,ignore=None):return {'analysisRegion':dict(x=.2,y=.2,width=.5,height=.5),'ignoredRegion':ignore}
 def test_outside_overlap_and_legacy(self):
  outside=dict(x=.8,y=.8,width=.1,height=.1)
  self.assertTrue(np.array_equal(effective_mask(100,100,self.setting(),0),effective_mask(100,100,self.setting(outside),0)))
  overlap=dict(x=.6,y=.6,width=.2,height=.2);mask=effective_mask(100,100,self.setting(overlap),0)
  self.assertFalse(mask[65,65]);self.assertTrue(mask[30,30]);self.assertFalse(mask[10,10])
  self.assertTrue(effective_mask(100,100,None,0).all())
 def test_full_analysis_and_empty_overlap_rejected(self):
  value={'analysisRegion':dict(x=0,y=0,width=1,height=1),'ignoredRegion':None};self.assertEqual(normalize_setting(value),value)
  with self.assertRaises(ValueError):normalize_setting(self.setting(dict(x=.1,y=.1,width=.8,height=.8)))
 def test_image_masks_do_not_change_original_and_ocr_only_keeps_visible(self):
  image=np.zeros((100,100,3),dtype=np.uint8);copy_image=image.copy();filtered=prepare_image(image,self.setting(),0)
  self.assertTrue((filtered[0,0]==255).all());self.assertTrue((filtered[30,30]==0).all());self.assertTrue(np.array_equal(image,copy_image))
  frame={'frameTimeMs':0,'ocrBlocks':[{'text':'inside','polygon':[[25,25],[35,25],[35,35],[25,35]]},{'text':'outside','polygon':[[0,0],[10,0],[10,10],[0,10]]}]}
  self.assertEqual([b['text'] for b in filter_frame(frame,self.setting(),0,100,100)['ocrBlocks']],['inside']);self.assertEqual(len(frame['ocrBlocks']),2)
 def test_time_changes_select_different_analysis_regions(self):
  value={'analysisRegion':{'nodes':[{'timeMs':0,'region':dict(x=0,y=0,width=.3,height=.3)},{'timeMs':5000,'region':dict(x=.7,y=.7,width=.3,height=.3)}]},'ignoredRegion':None}
  self.assertTrue(effective_mask(100,100,value,0)[10,10]);self.assertFalse(effective_mask(100,100,value,5000)[10,10])
 def test_coarse_selector_ignores_changes_outside_board(self):
  from visual_evidence import _candidate_times
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'board.avi';writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),1,(320,180))
   for i in range(12):
    image=np.full((180,320,3),128,dtype=np.uint8);image[0:25,0:50]=(i//2)%2*255;writer.write(image)
   writer.release();self.assertEqual(_candidate_times(path,ignore_region=self.setting()),[10000])

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
