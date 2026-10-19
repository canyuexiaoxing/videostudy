"""Generated-fixture integration checks for the throwaway collection probe."""
import copy,importlib.util,sys,tempfile,unittest
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
s=importlib.util.spec_from_file_location('versions',Path(__file__).with_name('page-versions-probe.py'));p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
class Integration(unittest.TestCase):
 def fixture(self,lines):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);frames=[]
  for t,texts in enumerate(lines):
   image=np.zeros((400,640),np.uint8);blocks=[]
   for i,text in enumerate(texts):
    x,y=30,50+i*65;cv2.putText(image,text,(x,y),cv2.FONT_HERSHEY_SIMPLEX,.55,255,1)
    (w,h),_=cv2.getTextSize(text,cv2.FONT_HERSHEY_SIMPLEX,.55,1)
    blocks.append({'text':text,'score':1.,'polygon':[[x,y-h-2],[x+w,y-h-2],[x+w,y+3],[x,y+3]]})
   self.assertTrue(cv2.imwrite(str(root/f'{t}.jpg'),image));frames.append({'frameTimeMs':t,'ocrBlocks':blocks})
  pages=[{'pageIndex':i+1,'memberFrameTimesMs':[i],'representativeFrameTimesMs':[i]} for i in range(len(lines))]
  return root,frames,pages
 def base(self):return ['fixed condition of this exact problem','second fixed statement for this problem','y = x - 10']
 def test_collect_preserves_originals_and_inputs(self):
  root,frames,pages=self.fixture([self.base(),self.base()[:2]+['y = x + 10']]);old=copy.deepcopy((frames,pages))
  result=p.collect(pages,frames,root,protect=True)
  self.assertEqual(result['selected'],[0,1]);self.assertEqual(len(result['collections']),1);self.assertEqual((frames,pages),old)
 def test_novel_candidate_is_added_without_replacing_old(self):
  root,frames,pages=self.fixture([self.base(),self.base()+['new final formula z = x + 20']]);pages=pages[:1];pages[0]['memberFrameTimesMs']=[0,1]
  result=p.collect(pages,frames,root,protect=True)
  self.assertEqual(result['selected'],[0,1]);self.assertEqual(result['extra_read'],1)
 def test_missing_ocr_never_proves_redundancy(self):
  root,frames,pages=self.fixture([self.base(),[]]);result=p.collect(pages,frames,root,protect=True)
  self.assertEqual(result['selected'],[0,1]);self.assertEqual(len(result['collections']),2)
 def test_different_problem_same_title_is_separate(self):
  root,frames,pages=self.fixture([['common course title','evaluate integral x dx'],['common course title','solve differential equation']]);result=p.collect(pages,frames,root)
  self.assertEqual(len(result['collections']),2)
 def test_corrupt_source_is_explicit_error_in_probe(self):
  root,frames,pages=self.fixture([self.base()]);(root/'0.jpg').write_bytes(b'broken')
  with self.assertRaises(FileNotFoundError):p.collect(pages,frames,root)
 def test_unknown_visibility_never_claimed_clear(self):
  root,frames,pages=self.fixture([self.base(),self.base()]);result=p.collect(pages,frames,root)
  self.assertTrue(all(c['visibility']=='unknown' for c in result['collections']))
if __name__=='__main__':unittest.main()
