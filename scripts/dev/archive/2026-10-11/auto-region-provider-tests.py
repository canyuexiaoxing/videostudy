from pathlib import Path
p=Path('E:/workp/videostudy/agent-python/test_auto_region.py')
with p.open('a',encoding='utf-8') as out:out.write('''
 def test_vision_request_uses_existing_provider_and_strict_json(self):
  import json,io
  from unittest.mock import patch
  from auto_region import ask_region
  class Reply(io.BytesIO):pass
  sent=[]
  def answer(request,timeout):
   sent.append(json.loads(request.data));self.assertEqual(timeout,45)
   return Reply(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'{"status":"absent","region":null}'}}]}).encode())
  with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'test-only','DEEPSEEK_MODEL':'vision-test','DEEPSEEK_BASE_URL':'http://provider.test'}),patch('auto_region.urlopen',side_effect=answer):
   self.assertEqual(ask_region(self.image())['status'],'absent')
  self.assertEqual(sent[0]['model'],'vision-test')
  self.assertEqual(sent[0]['messages'][1]['content'][0]['type'],'image_url')
  self.assertEqual(sent[0]['response_format']['type'],'json_object')
 def test_endpoint_binds_results_and_rejects_bad_frame(self):
  from app import video_region_detections,RegionFramesRequest
  from fastapi import HTTPException
  from unittest.mock import patch
  with patch('auto_region.ask_region',return_value={'status':'absent','region':None}) as ask:
   result=video_region_detections(RegionFramesRequest(frames=[dict(timeMs=1234,image=self.image())]))
   self.assertEqual(result['detections'][0]['timeMs'],1234);self.assertEqual(ask.call_count,1)
   with self.assertRaises(HTTPException) as caught:video_region_detections(RegionFramesRequest(frames=[dict(timeMs=0,image='invalid')]))
   self.assertEqual(caught.exception.status_code,422);self.assertEqual(ask.call_count,1)
''')
