from pathlib import Path
p=Path('E:/workp/videostudy/agent-python/test_region_timeline.py')
s=p.read_text(encoding='utf-8')+'''
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
'''
p.write_text(s,encoding='utf-8')
