from pathlib import Path
p=Path(r'E:\workp\videostudy\agent-python\test_region_timeline.py')
with p.open('a',encoding='utf-8') as f:
 f.write('''
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
''')
