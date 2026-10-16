"""Run through deployed service stdin. Mock provider only, never a paid call."""
import tempfile,json,os
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
import course_mind_map as course
import direct_course_map
with tempfile.TemporaryDirectory() as d:
 root=Path(d);img=root/'2274021.jpg';cv2.imwrite(str(img),np.zeros((20,30,3),np.uint8))
 payload=dict(_directEvidence=True,sourceEvidence=[],imageEvidence=[dict(sourceId='frame_2274021',sourceType='image',startMs=2274021,endMs=2274021,quote='slide')],concepts=[],examples=[],connections=[],firstHandSourceIds=[],firstHandImageIds=['frame_2274021'],uncertainties=[],outlineHints=[])
 raw=dict(topic='course',children=[dict(title='original method',imageIds=[],sourceIds=[],children=[],details=[])],examples=[],uncertainties=[])
 correction={'corrections':[],'additions':[dict(path='children[0]',sourceIds=[],imageIds=['img_1'])]}
 with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'MOCK_ONLY','MODEL_LOG_DIR':str(root/'logs')}),patch('course_mind_map.request_model_json',side_effect=[raw,correction]) as call:
  reply=course._deepseek_course_json(payload,[(2274021,img,'original')]);result=course.finalize_course_reply(reply,payload,'smoke')
  assert call.call_count==2 and result['status']=='completed'
  assert reply['children'][0]['title']=='original method' and reply['children'][0]['imageIds']==['frame_2274021']
 print(json.dumps({'healthyCitationRepair':True,'groupedVersion':course.PROMPT_VERSION,'directVersion':direct_course_map.PROMPT_VERSION,'mockRequests':2,'paidCalls':0,'titleAndTreePreserved':True}))
