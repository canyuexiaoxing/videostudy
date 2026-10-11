from pathlib import Path
p=Path('E:/workp/videostudy/agent-python/test_region_timeline.py')
s=p.read_text(encoding='utf-8')+'''
 def test_mask_hiding_all_text_does_not_create_blank_transition(self):
  import tempfile,cv2,numpy as np,copy
  from pathlib import Path
  from slide_grouping import group_pages
  with tempfile.TemporaryDirectory() as directory:
   image=np.full((180,320),255,dtype=np.uint8);image[10:30,5:110]=0
   blocks=[{'text':'fundamental algebra chapter','polygon':[[5,10],[110,10],[110,30],[5,30]]}]
   frames=[{'frameTimeMs':t,'ocrBlocks':copy.deepcopy(blocks)} for t in [0,6000,12000]]
   for frame in frames:cv2.imwrite(str(Path(directory)/f'{frame["frameTimeMs"]}.jpg'),image)
   right=dict(x=.6,y=0,width=.4,height=.8);left=dict(x=0,y=0,width=.4,height=.8)
   pages,transitions=group_pages(frames,Path(directory),[],ask_json=lambda _: {'samePage':True},ignore_region={'nodes':[{'timeMs':0,'region':right},{'timeMs':6000,'region':left},{'timeMs':12000,'region':right}]})
   self.assertEqual(transitions,[])
   self.assertEqual(len(pages),1)
   self.assertEqual(pages[0]['memberFrameTimesMs'],[0,6000,12000])
'''
p.write_text(s,encoding='utf-8')
