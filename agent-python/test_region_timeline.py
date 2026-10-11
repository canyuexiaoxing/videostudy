import unittest
from ignored_region import normalize_setting, region_at
from app import TranscribeRequest
A=dict(x=.7,y=.6,width=.2,height=.3)
B=dict(x=.1,y=.1,width=.2,height=.2)
TIMELINE={'nodes':[{'timeMs':0,'region':A},{'timeMs':5000,'region':B}]}
class TimelineTest(unittest.TestCase):
 def test_boundaries_and_static_compatibility(self):
  self.assertEqual(region_at(normalize_setting(TIMELINE),4999),A)
  self.assertEqual(region_at(TIMELINE,5000),B)
  self.assertEqual(region_at(A,99000),A)
  self.assertEqual(TranscribeRequest(fileId='fixture',ignoredRegion=TIMELINE).ignoredRegion,TIMELINE)
 def test_rejects_invalid_timeline(self):
  for v in [{'nodes':[]},{'nodes':[{'timeMs':1,'region':A}]},{'nodes':[{'timeMs':0,'region':A},{'timeMs':0,'region':B}]},{'nodes':[{'timeMs':0,'region':A},{'timeMs':True,'region':B}]},{'nodes':[{'timeMs':0,'region':A},{'timeMs':5000,'region':{'nodes':[]}}]}]:
   with self.subTest(value=v),self.assertRaises(ValueError):normalize_setting(v)
 def test_disabled_segment(self):
  self.assertIsNone(region_at({'nodes':[{'timeMs':0,'region':A},{'timeMs':5000,'region':None}]},5000))

 def test_real_moving_camera_does_not_select_every_frame(self):
  import tempfile,cv2,numpy as np
  from pathlib import Path
  from ignored_region import valid_mask
  from visual_evidence import _candidate_times
  timeline={'nodes':[{'timeMs':0,'region':A},{'timeMs':6000,'region':B}]}
  for width,height in [(320,180),(180,320)]:
   with self.subTest(size=(width,height)),tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'camera.avi'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),1,(width,height))
    self.assertTrue(writer.isOpened())
    for i in range(12):
     image=np.full((height,width,3),128,dtype=np.uint8)
     image[~valid_mask(width,height,A if i<6 else B)]=0 if (i//2)%2==0 else 255
     writer.write(image)
    writer.release()
    self.assertEqual(_candidate_times(path,ignore_region=timeline),[10000])

 def test_actual_lesson_change_outside_timed_region_is_retained(self):
  import tempfile,cv2,numpy as np
  from pathlib import Path
  from ignored_region import valid_mask
  from visual_evidence import _candidate_times
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'lesson.avi';writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),1,(320,180))
   for i in range(12):
    image=np.full((180,320,3),128,dtype=np.uint8)
    image[~valid_mask(320,180,A if i<6 else B)]=i%2*255
    if i>=8:image[70:110,130:190]=255
    writer.write(image)
   writer.release()
   self.assertGreater(len(_candidate_times(path,ignore_region={'nodes':[{'timeMs':0,'region':A},{'timeMs':6000,'region':B}]})),1)

 def test_grouping_uses_each_frame_region_and_preserves_raw_ocr(self):
  import tempfile,cv2,numpy as np,copy
  from pathlib import Path
  from ignored_region import valid_mask
  from slide_grouping import group_pages
  with tempfile.TemporaryDirectory() as directory:
   frames=[]
   for time in [0,2000,6000,8000]:
    region=A if time<6000 else B
    image=np.full((180,320),128,dtype=np.uint8);image[~valid_mask(320,180,region)]=(time//2000)%2*255
    cv2.imwrite(str(Path(directory)/f'{time}.jpg'),image)
    x,y=region['x']*320,region['y']*180
    frames.append({'frameTimeMs':time,'ocrBlocks':[{'text':'稳定课件内容','polygon':[[130,60],[200,60],[200,80],[130,80]]},{'text':f'camera{time}','polygon':[[x+2,y+2],[x+20,y+2],[x+20,y+20],[x+2,y+20]]}]})
   original=copy.deepcopy(frames)
   pages,_=group_pages(frames,Path(directory),[],ask_json=lambda _: {'samePage':True},ignore_region={'nodes':[{'timeMs':0,'region':A},{'timeMs':6000,'region':B}]})
   self.assertEqual(len(pages),1)
   self.assertEqual([line['text'] for line in pages[0]['ocrLines']],['稳定课件内容'])
   self.assertEqual(frames,original)

 def test_moving_mask_does_not_split_identical_ocr_page(self):
  import tempfile,cv2,numpy as np,copy
  from pathlib import Path
  from slide_grouping import group_pages
  with tempfile.TemporaryDirectory() as directory:
   blocks=[{'text':'fundamental algebra chapter','polygon':[[5,10],[110,10],[110,30],[5,30]]},
           {'text':'geometry proof of triangles','polygon':[[210,10],[315,10],[315,30],[210,30]]}]
   frames=[{'frameTimeMs':t,'ocrBlocks':copy.deepcopy(blocks)} for t in [0,6000]]
   for t in [0,6000]:cv2.imwrite(str(Path(directory)/f'{t}.jpg'),np.full((180,320),128,dtype=np.uint8))
   reviews=[]
   pages,_=group_pages(frames,Path(directory),[],ask_json=lambda value:reviews.append(value),ignore_region={'nodes':[{'timeMs':0,'region':dict(x=0,y=0,width=.4,height=.8)},{'timeMs':6000,'region':dict(x=.6,y=0,width=.4,height=.8)}]})
   self.assertEqual(len(pages),1)
   self.assertEqual(reviews,[])
   self.assertEqual(len(pages[0]['ocrLines']),2)

 def test_mask_hiding_all_text_does_not_create_blank_transition(self):
  import tempfile,cv2,numpy as np,copy
  from pathlib import Path
  from slide_grouping import group_pages
  with tempfile.TemporaryDirectory() as directory:
   image=np.full((180,320),255,dtype=np.uint8);image[10:30,5:110]=0
   blocks=[{'text':'fundamental algebra chapter','polygon':[[5,10],[110,10],[110,30],[5,30]]}]
   frames=[{'frameTimeMs':t,'ocrBlocks':copy.deepcopy(blocks)} for t in [0,6000,8000,12000]]
   for frame in frames:cv2.imwrite(str(Path(directory)/f'{frame["frameTimeMs"]}.jpg'),image)
   right=dict(x=.6,y=0,width=.4,height=.8);left=dict(x=0,y=0,width=.4,height=.8)
   pages,transitions=group_pages(frames,Path(directory),[],ask_json=lambda _: {'samePage':True},ignore_region={'nodes':[{'timeMs':0,'region':right},{'timeMs':6000,'region':left},{'timeMs':12000,'region':right}]})
   self.assertEqual(transitions,[])
   self.assertEqual(len(pages),1)
   self.assertEqual(pages[0]['memberFrameTimesMs'],[0,6000,8000,12000])

 def test_real_blank_transition_survives_mask_move(self):
  import tempfile,cv2,numpy as np
  from pathlib import Path
  from slide_grouping import group_pages
  with tempfile.TemporaryDirectory() as directory:
   frames=[]
   for t in [0,6000,12000]:
    image=np.full((180,320),255,dtype=np.uint8)
    if t!=6000:image[80:100,135:180]=0
    cv2.imwrite(str(Path(directory)/f'{t}.jpg'),image)
    frames.append({'frameTimeMs':t,'ocrBlocks':[] if t==6000 else [{'text':'central lesson content','polygon':[[135,80],[180,80],[180,100],[135,100]]}]})
   right=dict(x=.6,y=0,width=.4,height=.8);left=dict(x=0,y=0,width=.4,height=.8)
   pages,transitions=group_pages(frames,Path(directory),[],ask_json=lambda _: {'samePage':True},ignore_region={'nodes':[{'timeMs':0,'region':right},{'timeMs':6000,'region':left}]})
   self.assertEqual(transitions,[6000])
   self.assertEqual(len(pages),2)
