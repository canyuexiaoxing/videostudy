from pathlib import Path
root=Path('E:/workp/videostudy')
(root/'agent-python/test_ignored_region.py').write_text('''import unittest
import tempfile
import copy
from pathlib import Path
import cv2
import numpy as np
from ignored_region import normalize_region, valid_mask, grouping_frame
from visual_evidence import _candidate_times
from slide_grouping import group_pages
from app import TranscribeRequest

REGION = dict(x=.75,y=.5,width=.25,height=.5)

class IgnoredRegionTests(unittest.TestCase):
    def test_validation(self):
        self.assertIsNone(normalize_region(None))
        self.assertEqual(normalize_region(REGION),REGION)
        for value in [{},dict(REGION,x=-.1),dict(REGION,width=.3),dict(REGION,y=float('nan')),dict(REGION,x=True),dict(REGION,width='0.25'),dict(x=0,y=0,width=1,height=1),dict(REGION,extra=1)]:
            with self.subTest(value=value),self.assertRaises(ValueError): normalize_region(value)
            with self.assertRaises(ValueError): TranscribeRequest(fileId='fixture',ignoredRegion=value)

    def test_ocr_filter_keeps_original_indices_and_source(self):
        frame={'frameTimeMs':0,'ocrBlocks':[{'text':'camera','polygon':[[80,60],[99,60],[99,99],[80,99]]},{'text':'lesson','polygon':[[0,0],[50,0],[50,20],[0,20]]},{'text':'unknown'}]}
        original=copy.deepcopy(frame)
        result=grouping_frame(frame,REGION,100,100)
        self.assertEqual([b['text'] for b in result['ocrBlocks']],['lesson','unknown'])
        self.assertEqual(result['ocrBlocks'][0]['_sourceBlockIndex'],1)
        self.assertEqual(frame,original)

    def test_mask_keeps_only_visible_pixels(self):
        mask=valid_mask(100,100,REGION)
        self.assertEqual(mask.sum(),8750)
        self.assertFalse(mask[99,99]);self.assertTrue(mask[0,0])

    def test_real_camera_changes_are_ignored_wide_and_portrait(self):
        for width,height in [(320,180),(180,320)]:
            with self.subTest(shape=(width,height)),tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'camera.avi'
                writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),1,(width,height))
                self.assertTrue(writer.isOpened())
                mask=valid_mask(width,height,REGION)
                for i in range(8):
                    image=np.full((height,width,3),128,dtype=np.uint8)
                    image[~mask]=0 if (i//2)%2==0 else 255
                    writer.write(image)
                writer.release()
                self.assertGreater(len(_candidate_times(path)),1)
                self.assertEqual(_candidate_times(path,ignore_region=REGION),[6000])

    def test_grouping_does_not_split_on_camera_and_preserves_raw(self):
        with tempfile.TemporaryDirectory() as directory:
            frames=[]
            for i in range(2):
                image=np.full((180,320),128,dtype=np.uint8)
                image[90:,240:]=i*255
                cv2.imwrite(str(Path(directory)/f'{i*2000}.jpg'),image)
                frames.append({'frameTimeMs':i*2000,'ocrBlocks':[{'text':f'camera changing {i}','score':1,'polygon':[[250,100],[310,100],[310,160],[250,160]]},{'text':'lesson text','score':1,'polygon':[[20,20],[150,20],[150,40],[20,40]]}]})
            original=copy.deepcopy(frames)
            pages,_=group_pages(frames,Path(directory),[],ignore_region=REGION,ask_json=lambda _:self.fail('camera must not trigger model review'))
            self.assertEqual(len(pages),1)
            self.assertEqual(pages[0]['ocrLines'][0]['sourceBlockIndex'],1)
            self.assertEqual(frames,original)
''',encoding='utf-8')
