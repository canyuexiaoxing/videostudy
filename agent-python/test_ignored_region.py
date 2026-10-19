import unittest
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

    def test_changes_outside_region_still_select_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'lesson.avi'
            writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),1,(320,180))
            for i in range(8):
                image=np.full((180,320,3),128,dtype=np.uint8)
                image[:60,:160]=0 if i<4 else 255
                image[90:,240:]=0 if (i//2)%2==0 else 255
                writer.write(image)
            writer.release()
            self.assertEqual(_candidate_times(path,ignore_region=REGION),[2000,6000])

    def test_slow_camera_changes_do_not_trigger_progress_capture(self):
        region=dict(x=.8,y=.8,width=.1,height=.1)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'progress.avi'
            writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),1,(320,180))
            for i in range(36):
                image=np.full((180,320,3),128,dtype=np.uint8)
                image[144:162,256:288]=0 if i<15 else 255
                writer.write(image)
            writer.release()
            self.assertGreater(len(_candidate_times(path)),1)
            self.assertEqual(_candidate_times(path,ignore_region=region),[34000])

    def test_region_reaches_worker_and_grouping_and_separates_cache(self):
        import os
        from unittest.mock import patch
        from uuid import uuid4
        from analysis import analyze_file
        with tempfile.TemporaryDirectory() as directory:
            file_id=str(uuid4());(Path(directory)/file_id).write_bytes(b'fixture')
            with patch.dict(os.environ,{'MEDIA_TEMP_DIR':directory,'KEYFRAME_DIR':str(Path(directory)/'frames')}), patch('analysis.transcribe_file',return_value={'language':'zh','segments':[]}), patch('analysis.VisualOcrWorker') as worker, patch('analysis.media_duration_ms',return_value=10000), patch('analysis.review_visual_coverage',return_value=([],{'status':'not_applicable'})), patch('analysis.group_pages',return_value=([],[])) as grouping, patch('analysis.safe_overview',return_value={'status':'empty'}), patch('analysis.build_mind_map',return_value={'status':'empty'}):
                worker.return_value.__enter__.return_value.analyze.return_value=[]
                analyze_file(file_id,ignore_region=REGION)
                self.assertEqual(worker.call_args.kwargs['ignore_region'],REGION)
                self.assertEqual(grouping.call_args.kwargs['ignore_region'],REGION)
                analyze_file(file_id,ignore_region=REGION)
                self.assertEqual(worker.return_value.__enter__.return_value.analyze.call_count,1)
                analyze_file(file_id,ignore_region=dict(REGION,x=.5))
                self.assertEqual(worker.return_value.__enter__.return_value.analyze.call_count,2)
                analyze_file(file_id)
                self.assertEqual(worker.return_value.__enter__.return_value.analyze.call_count,3)

    def test_no_region_retry_reuses_pre_feature_transcription_checkpoint(self):
        import os
        from unittest.mock import patch
        from uuid import uuid4
        import analysis
        from checkpoints import Checkpoints
        with tempfile.TemporaryDirectory() as directory:
            file_id=str(uuid4());media=Path(directory)/file_id;media.write_bytes(b'fixture')
            metadata=media.stat()
            # The context used by the previously deployed sampling implementation.
            legacy={'size':metadata.st_size,'mtime':metadata.st_mtime_ns,
                'mode':'both','threshold':2.0,'sampleSeconds':2,
                'ocr':analysis.OCR_MODEL_ID,'ocrDevice':os.environ.get('OCR_DEVICE','cpu'),
                'speech':'faster-whisper-base:beam5:vad:int8',
                'model':os.environ.get('DEEPSEEK_MODEL','deepseek-flash'),
                'endpoint':os.environ.get('DEEPSEEK_BASE_URL','https://api.deepseek.com'),
                'prompts':[analysis.MAP_VERSION,analysis.PAGE_PROMPT_VERSION,analysis.REVIEW_VERSION,analysis.GROUPING_VERSION]}
            cache=Checkpoints(Path(directory)/'frames'/file_id/'.analysis',legacy)
            cache.run('transcription',{},lambda:{'language':'zh','segments':[]})
            with patch.dict(os.environ,{'MEDIA_TEMP_DIR':directory,'KEYFRAME_DIR':str(Path(directory)/'frames'),'WHISPER_MODEL':'base','WHISPER_DEVICE':'cpu','WHISPER_COMPUTE_TYPE':'int8','WHISPER_BATCH_SIZE':'0'}), patch('analysis.transcribe_file',side_effect=AssertionError('legacy checkpoint must be reused')), patch('analysis.VisualOcrWorker') as worker, patch('analysis.media_duration_ms',return_value=10000), patch('analysis.review_visual_coverage',return_value=([],{'status':'not_applicable'})), patch('analysis.group_pages',return_value=([],[])), patch('analysis.safe_overview',return_value={'status':'empty'}), patch('analysis.build_mind_map',return_value={'status':'empty'}):
                worker.return_value.__enter__.return_value.analyze.return_value=[]
                result=analysis.analyze_file(file_id,coarse_change_percent=2.0)
                self.assertEqual(result['reusedCheckpoints']['transcription'],1)
