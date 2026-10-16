"""Deployed parser/provider smoke, mocked network only."""
import json,os,tempfile
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
import course_mind_map as course
from course_json import CourseJsonFormatError
with tempfile.TemporaryDirectory() as d:
 root=Path(d);img=root/'1000.jpg';cv2.imwrite(str(img),np.zeros((20,30,3),np.uint8))
 payload=dict(_directEvidence=True,sourceEvidence=[],imageEvidence=[dict(sourceId='frame_1000',sourceType='image',startMs=1000,endMs=1000,quote='slide')],concepts=[],examples=[],connections=[],firstHandSourceIds=[],firstHandImageIds=['frame_1000'],uncertainties=[],outlineHints=[])
 raw=dict(topic='course',children=[dict(title='original formula',imageIds=['img_1'],sourceIds=[],children=[],details=[])],examples=[],uncertainties=[])
 text=json.dumps(raw).replace('"imageIds": ["img_1"]','"imageIds": ["img_1"],"imageIds": ["img_1"]')
 class Response:
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def read(self):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':text}}]}).encode()
 with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'MOCK_ONLY','MODEL_LOG_DIR':str(root/'logs')}),patch('course_mind_map.urlopen',return_value=Response()) as call:
  reply=course._deepseek_course_json(payload,[(1000,img,'original')]);result=course.finalize_course_reply(reply,payload,'smoke')
  assert call.call_count==1 and result['status']=='completed'
  assert reply['children'][0]['title']=='original formula' and reply['children'][0]['imageIds']==['frame_1000']
  text=text.replace('"imageIds": ["img_1"],"imageIds": ["img_1"]','"imageIds": ["img_1"],"imageIds": []')
  try:course._deepseek_course_json(payload,[(1000,img,'original')])
  except CourseJsonFormatError as error:assert error.path=='root.children[0].imageIds'
  else:raise AssertionError('Conflict was not rejected')
  assert call.call_count==2
 print(json.dumps({'healthyDuplicateRecovery':True,'conflictLocated':True,'mockRequestsPerAttempt':1,'paidCalls':0,'titleAndTreePreserved':True}))
