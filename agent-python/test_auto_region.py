import base64,unittest,cv2,numpy as np
from auto_region import detect_frames,normalize_detection
class AutoRegionTest(unittest.TestCase):
 def image(self):
  ok,image=cv2.imencode('.jpg',np.full((80,100,3),255,dtype=np.uint8));return 'data:image/jpeg;base64,'+base64.b64encode(image).decode()
 def test_coordinates_and_timestamp_are_validated(self):
  r=normalize_detection({'status':'detected','region':dict(x=.7,y=.6,width=.2,height=.3)},42)
  self.assertEqual(r['timeMs'],42)
  self.assertEqual(normalize_detection({'status':'detected','region':dict(x=2,y=0,width=.1,height=.1)},42)['status'],'uncertain')
  self.assertEqual(normalize_detection({'status':'absent','region':None},42)['status'],'absent')
 def test_batch_preserves_times_and_does_not_call_on_invalid_images(self):
  calls=[]
  result=detect_frames([dict(timeMs=t,image=self.image()) for t in [0,2000]],ask=lambda image: calls.append(image) or {'status':'absent','region':None})
  self.assertEqual([r['timeMs'] for r in result],[0,2000]);self.assertEqual(len(calls),2)
  for frames in [[],[dict(timeMs=0,image='bad')],[dict(timeMs=-1,image=self.image())],[dict(timeMs=0,image=self.image())]*2]:
   with self.assertRaises(ValueError):detect_frames(frames,ask=lambda _: self.fail('invalid input must not call provider'))

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
