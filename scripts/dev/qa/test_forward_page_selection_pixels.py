"""Real pixel-path checks for forward selector using generated page fixtures."""
import importlib.util,unittest,tempfile,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
s=importlib.util.spec_from_file_location('forward',Path(__file__).with_name('forward-page-selection-probe.py'));p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
class PixelTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name);self.frames=[];index=[];masks={}
  for t in range(6):
   image=np.zeros((360,640),np.uint8);blocks=[]
   lines=[('course topic',30,50),('condition x greater than zero',30,100),('y = x - 10' if t!=4 else 'y = x + 11',30,170)]
   if t in (1,2,3,5):lines.append(('answer z = x + 20',330,250))
   if t==5:lines=[item for item in lines if item[2]!=170]
   mask=np.zeros((360,640),np.uint8)
   for text,x,y in lines:
    cv2.putText(image,text,(x,y),cv2.FONT_HERSHEY_SIMPLEX,.7,255,1,cv2.LINE_AA);(w,h),_=cv2.getTextSize(text,cv2.FONT_HERSHEY_SIMPLEX,.7,1)
    if t!=2 or y!=170:blocks.append({'text':text,'score':1.,'polygon':[[x,y-h-2],[x+w,y-h-2],[x+w,y+3],[x,y+3]]})
   if t==2:
    cv2.rectangle(image,(20,140),(240,185),100,-1);cv2.rectangle(mask,(17,137),(243,188),1,-1)
   path=self.root/f'{t}.jpg';self.assertTrue(cv2.imwrite(str(path),image,[cv2.IMWRITE_JPEG_QUALITY,98]));raw=path.read_bytes();import hashlib
   index.append({'time_ms':t,'width':640,'height':360,'sha256':hashlib.sha256(raw).hexdigest(),'person_pixels':int(mask.sum()),'detections':int(mask.any())});masks[str(t)]=np.packbits(cv2.resize(mask,(320,180),interpolation=cv2.INTER_NEAREST).astype(bool));self.frames.append({'frameTimeMs':t,'ocrBlocks':blocks})
  (self.root/'fixture-mask-index.json').write_text(json.dumps({'frames':index}));np.savez_compressed(self.root/'fixture-masks.npz',**masks)
  self.store=p.Store('fixture',self.frames,self.root,None,self.root)
 def test_actual_pixels_allow_added_content(self):self.assertTrue(self.store.covers(0,1));self.assertFalse(self.store.covers(1,0))
 def test_actual_pixels_keep_new_content_when_old_is_blocked(self):
  r=p.forward([0,2],self.store);self.assertEqual(r['selected'],[0,2])
 def test_actual_lookup_finds_complete_unblocked_frame(self):
  r=p.forward([0,2],self.store,{2:[3]},2);self.assertEqual(r['selected'],[3])
 def test_changed_operator_and_number_cannot_replace(self):self.assertFalse(self.store.covers(0,4))
 def test_erasure_and_new_answer_need_both_versions(self):self.assertEqual(p.forward([0,5],self.store)['selected'],[0,5])
class TolerantPixelTests(PixelTests):
 def setUp(self):
  super().setUp();self.store.policy='tolerant'
if __name__=='__main__':unittest.main()
