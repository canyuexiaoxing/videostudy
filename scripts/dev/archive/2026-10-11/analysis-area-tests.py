from pathlib import Path
p=Path('E:/workp/videostudy')
files={
'docs/superpowers/plans/2026-10-11-analysis-area.md':'''# 分析区域与忽略区域叠加
User authorized implementation. Green analysis frame selects visible content; blue ignore frame subtracts overlappingportion; both independenttimelines. Ignoredrectangle outsideanalysis hasnoeffect and UIhint. Existing ignoredRegion payload supports backwardcompatible {analysisRegion,ignoredRegion} composite, legacy static/timelineunchanged. Original screenshots retained; OCR and modelvisualinput respectvisiblemask, audio unchanged. Empty effective area rejected.
Tasks: helpertests→Pythonmask/OCR/image/FFmpeg/grouping→Javawirevalidation→Appstorage/workspace modes→regression/browser/review/localdeployment/handoff. No paidmodels or unsolicitedcommits.
''',
'agent-python/test_analysis_region.py':'''import unittest,copy,cv2,numpy as np,tempfile
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
'''
}
for name,body in files.items():(p/name).write_text(body,encoding='utf-8')
