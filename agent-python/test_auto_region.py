import base64,unittest,cv2,numpy as np
from auto_region import detect_frames,normalize_detection,refine_region
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

 def test_border_refinement_recovers_full_fixed_window_despite_person_motion(self):
  expected=dict(x=704/960,y=432/540,width=146/960,height=108/540)
  for center in (745,790,815):
   image=np.full((540,960,3),255,dtype=np.uint8);image[432:540,704:850]=(170,190,180)
   cv2.circle(image,(center,488),18,(20,20,20),-1)
   region,refined=refine_region(image,dict(x=.71,y=.75,width=.18,height=.25))
   self.assertTrue(refined)
   for name in expected:self.assertAlmostEqual(region[name],expected[name],delta=.004)
 def test_no_rectangular_boundary_preserves_estimate_instead_of_inventing_precision(self):
  region=dict(x=.7,y=.7,width=.15,height=.3)
  actual,refined=refine_region(np.full((540,960,3),255,dtype=np.uint8),region)
  self.assertFalse(refined);self.assertEqual(actual,region)

 def test_inset_boundary_is_searched_even_when_estimate_touches_frame(self):
  image=np.full((540,960,3),255,dtype=np.uint8);image[432:540,15:161]=(170,190,180)
  actual,refined=refine_region(image,dict(x=0,y=.8,width=161/960,height=.2))
  self.assertTrue(refined);self.assertAlmostEqual(actual['x'],15/960,delta=.004)

 def test_oversized_estimate_recovers_window_instead_of_retaining_blank_margin(self):
  image=np.full((540,960,3),255,dtype=np.uint8);image[432:540,704:850]=(170,190,180)
  cv2.circle(image,(790,488),18,(20,20,20),-1)
  for estimate in (dict(x=.75,y=.75,width=.24,height=.25),dict(x=.73,y=.8,width=.24,height=.2)):
   actual,refined=refine_region(image,estimate)
   self.assertTrue(refined)
   for name,value in dict(x=704/960,y=.8,width=146/960,height=.2).items():
    self.assertAlmostEqual(actual[name],value,delta=.004)

 def test_near_window_edge_wins_over_distant_dark_person_outline(self):
  image=np.full((540,960,3),255,dtype=np.uint8);image[432:540,704:850]=(170,190,180)
  image[432:540,754:789]=(10,10,10)
  actual,refined=refine_region(image,dict(x=.73,y=.8,width=.24,height=.2))
  self.assertTrue(refined);self.assertAlmostEqual(actual['x'],704/960,delta=.004)

 def test_weak_internal_line_does_not_replace_complete_window_border(self):
  image=np.full((540,960,3),255,dtype=np.uint8);image[432:540,704:850]=170
  image[432:540,730:748]=150
  actual,refined=refine_region(image,dict(x=.75,y=.75,width=.24,height=.25))
  self.assertTrue(refined);self.assertAlmostEqual(actual['x'],704/960,delta=.004)

 def test_near_bottom_internal_line_does_not_cut_off_window_touching_frame(self):
  image=np.full((540,960,3),255,dtype=np.uint8);image[432:540,704:850]=170
  image[530:535,704:850]=30
  actual,refined=refine_region(image,dict(x=704/960,y=.8,width=146/960,height=.2))
  self.assertTrue(refined);self.assertAlmostEqual(actual['y']+actual['height'],1,delta=.001)
 def test_real_inset_bottom_is_not_extended_to_frame(self):
  image=np.full((540,960,3),255,dtype=np.uint8);image[432:535,704:850]=170
  actual,refined=refine_region(image,dict(x=704/960,y=.8,width=146/960,height=.2))
  self.assertTrue(refined);self.assertLess(actual['y']+actual['height'],.996)

 def test_bottom_continuation_also_handles_window_touching_left_or_right_frame(self):
  for left,right in ((704,960),(0,256)):
   image=np.full((540,960,3),255,dtype=np.uint8);image[432:540,left:right]=170
   image[530:535,left:right]=30
   actual,refined=refine_region(image,dict(x=left/960,y=.8,width=(right-left)/960,height=.2))
   self.assertTrue(refined);self.assertAlmostEqual(actual['y']+actual['height'],1,delta=.001)
