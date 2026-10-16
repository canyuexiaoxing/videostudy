import multiprocessing
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
from uuid import uuid4
import cv2
import numpy as np
import slide_grouping
from transcription import transcribe_file
from visual_evidence import analyze_visuals, VisualOcrWorker


class IncrementalMediaTest(unittest.TestCase):
    def test_transcript_callback_arrives_before_next_segment_is_decoded(self):
        seen = []
        def decoded():
            yield SimpleNamespace(start=0, end=1, text=' first ')
            self.assertEqual(seen, [{'id':'t_1','startMs':0,'endMs':1000,'text':'first'}])
            yield SimpleNamespace(start=1, end=2, text='second')
        with tempfile.TemporaryDirectory() as directory:
            file_id = str(uuid4())
            Path(directory, file_id).write_bytes(b'fixture')
            model = Path(directory, 'faster-whisper-base'); model.mkdir()
            (model/'model.bin').write_bytes(b'fixture')
            engine = Mock(); engine.transcribe.return_value = (decoded(), SimpleNamespace(language='en'))
            with patch.dict(os.environ, {'MEDIA_TEMP_DIR':directory,'MODEL_DIR':directory,'WHISPER_MODEL':'base','WHISPER_DEVICE':'cpu','WHISPER_COMPUTE_TYPE':'int8'}), patch('transcription.subprocess.run', return_value=SimpleNamespace(stdout='0')), patch('transcription._get_model', return_value=engine):
                result = transcribe_file(file_id, on_segment=seen.append)
            self.assertEqual(result['segments'], seen)
            self.assertEqual(result['language'], 'en')

    def test_silent_video_needs_no_whisper_model_and_emits_no_segments(self):
        with tempfile.TemporaryDirectory() as directory:
            file_id = str(uuid4()); Path(directory,file_id).write_bytes(b'fixture')
            seen = []
            with patch.dict(os.environ, {'MEDIA_TEMP_DIR':directory,'MODEL_DIR':directory}), patch('transcription.subprocess.run', return_value=SimpleNamespace(stdout='')):
                self.assertEqual(transcribe_file(file_id,on_segment=seen.append), {'language':'und','segments':[]})
            self.assertEqual(seen, [])

    def test_frames_are_published_after_atomic_saved_jpg_and_ocr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root/'media'; path.write_bytes(b'fixture')
            seen = []
            def frames(*_,**kwargs):
                yield 1000, np.full((20, 30, 3), 20, np.uint8)
                yield 2000, np.full((20, 30, 3), 40, np.uint8)
            def ready(frame):
                self.assertIsNotNone(cv2.imread(str(root/f"{frame['frameTimeMs']}.jpg")))
                self.assertEqual(frame['ocrBlocks'][0]['text'], 'ready')
                seen.append(frame)
            with patch('visual_evidence._has_video', return_value=True), patch('frame_stream.sample_frames', side_effect=frames):
                result = analyze_visuals(path, recognize=lambda image:[{'text':'ready'}], keyframe_dir=root, on_frame=ready)
            self.assertEqual(result, seen)

    def test_pages_publish_completed_same_page_group_and_tail_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frames = []
            for time, texts in [(1000,['Original lesson heading','Original lesson formula']), (2000,['Original lesson heading','Original lesson formula','extra']), (3000,['Different subject heading','Different subject formula'])]:
                cv2.imwrite(str(root/f'{time}.jpg'), np.full((180,320,3),100,np.uint8))
                frames.append({'frameTimeMs':time,'ocrBlocks':[{'text':text,'score':1} for text in texts]})
            emitted = []
            pages, _ = slide_grouping.group_pages(frames, root, [], on_page=emitted.append)
            self.assertEqual([p['memberFrameTimesMs'] for p in emitted], [[1000,2000],[3000]])
            self.assertEqual(pages, emitted)
            with patch('slide_grouping._deepseek_boundary_json', side_effect=AssertionError('paid model used')):
                grouper = slide_grouping.IncrementalPageGrouper(root)
                self.assertEqual(grouper.add(frames[0]), [])
                self.assertEqual(grouper.add(frames[1]), [])
                closed = grouper.add(frames[2])
                self.assertEqual([p['memberFrameTimesMs'] for p in closed], [[1000,2000]])
                self.assertEqual(closed[0]['_closedAtMs'], 3000)
                tail = grouper.finish()
                self.assertEqual([p['memberFrameTimesMs'] for p in tail], [[3000]])
                self.assertIsNone(tail[0]['_closedAtMs'])
                self.assertEqual(grouper.finish(), [])

    def test_blank_frame_closes_group_immediately_without_publishing_blank(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for time, color in [(1000, 100), (2000, 255), (3000, 255), (4000, 100)]:
                cv2.imwrite(str(root/f'{time}.jpg'), np.full((180,320,3),color,np.uint8))
            grouper = slide_grouping.IncrementalPageGrouper(root)
            self.assertEqual(grouper.add({'frameTimeMs':1000,'ocrBlocks':[{'text':'Lesson heading','score':1}]}), [])
            closed = grouper.add({'frameTimeMs':2000,'ocrBlocks':[]})
            self.assertEqual([p['memberFrameTimesMs'] for p in closed], [[1000]])
            self.assertEqual(closed[0]['_closedAtMs'], 2000)
            self.assertEqual(grouper.add({'frameTimeMs':3000,'ocrBlocks':[]}), [])
            self.assertEqual(grouper.add({'frameTimeMs':4000,'ocrBlocks':[{'text':'Lesson heading','score':1}]}), [])
            tail = grouper.finish()
            self.assertEqual([p['memberFrameTimesMs'] for p in tail], [[4000]])
            self.assertEqual(tail[0]['pageIndex'], 2)

    def test_incremental_grouping_filters_camera_and_keeps_original_block_indices(self):
        import copy
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frames = []
            for time, camera in [(1000,0),(2000,255)]:
                image=np.full((180,320,3),128,np.uint8);image[90:,240:]=camera
                cv2.imwrite(str(root/f'{time}.jpg'),image)
                frames.append({'frameTimeMs':time,'ocrBlocks':[
                    {'text':str(camera),'score':1,'polygon':[[250,100],[310,100],[310,160],[250,160]]},
                    {'text':'lesson text','score':1,'polygon':[[20,20],[150,20],[150,40],[20,40]]}]})
            original=copy.deepcopy(frames)
            grouper=slide_grouping.IncrementalPageGrouper(root,ignore_region=dict(x=.75,y=.5,width=.25,height=.5))
            with patch('slide_grouping._deepseek_boundary_json',side_effect=AssertionError('paid boundary used')):
                self.assertEqual(grouper.add(frames[0]),[])
                self.assertEqual(grouper.add(frames[1]),[])
                pages=grouper.finish()
            self.assertEqual(pages[0]['memberFrameTimesMs'],[1000,2000])
            self.assertEqual(pages[0]['ocrLines'],[{'text':'lesson text','sourceFrameTimeMs':1000,'sourceBlockIndex':1}])
            self.assertEqual(frames,original)

    def make_worker(self, connection):
        worker = object.__new__(VisualOcrWorker)
        worker.connection = connection; worker.process = None
        worker._closed = False; worker._request_lock = threading.Lock()
        return worker

    def test_worker_consumes_frame_events_before_final_response(self):
        parent, child = multiprocessing.Pipe()
        worker = self.make_worker(parent)
        frame = {'frameTimeMs':1000,'ocrBlocks':[]}
        def server():
            self.assertEqual(child.recv()['op'], 'analyze')
            child.send({'event':'frame','value':frame})
            child.send({'ok':True,'value':[frame]})
            self.assertEqual(child.recv()['op'], 'capture')
            child.send({'ok':True,'value':[]})
        thread = threading.Thread(target=server, daemon=True); thread.start()
        try:
            seen=[]
            self.assertEqual(worker.analyze(on_frame=seen.append), [frame])
            self.assertEqual(seen, [frame])
            self.assertEqual(worker.capture(2000), [])
        finally:
            parent.close(); child.close(); thread.join(timeout=1)

    def test_server_streams_before_error_and_next_capture_has_no_stale_messages(self):
        from visual_evidence import _serve_visual_requests
        parent, child = multiprocessing.Pipe()
        worker = self.make_worker(parent)
        frame = {'frameTimeMs':1000,'ocrBlocks':[{'text':'verified'}]}
        def analysis(*args, **kwargs):
            kwargs['on_frame'](frame)
            raise ValueError('decode failed after first frame')
        with patch('visual_evidence._frame_checkpoint', return_value=None), patch('visual_evidence.analyze_visuals', side_effect=analysis), patch('visual_evidence._frame_at', return_value=(2000,np.zeros((10,10,3),np.uint8))), patch('visual_evidence._recognize', return_value=[{'text':'capture'}]):
            thread = threading.Thread(target=_serve_visual_requests,args=(child,),daemon=True)
            thread.start()
            try:
                worker._request('bind',mediaPath='fixture',keyframePath=None,pageChangeFraction=.02,sampleSeconds=2)
                seen=[]
                with self.assertRaisesRegex(RuntimeError,'decode failed'):
                    worker.analyze(on_frame=seen.append)
                self.assertEqual(seen,[frame])
                self.assertEqual(worker.capture(2000),[{'text':'capture'}])
                parent.send(None);thread.join(timeout=1)
                self.assertFalse(thread.is_alive())
            finally:
                parent.close();child.close()

    def test_callback_exception_and_cancellation_discard_unread_worker_messages(self):
        for failure in (ValueError('callback failed'), KeyboardInterrupt()):
            parent, child = multiprocessing.Pipe()
            worker = self.make_worker(parent)
            child.send({'event':'frame','value':{'frameTimeMs':1000,'ocrBlocks':[]}})
            child.send({'ok':True,'value':[]})
            def callback(_): raise failure
            try:
                with patch('visual_evidence._shared_connection', parent), patch('visual_evidence._shared_process', None):
                    with self.assertRaises(type(failure)):
                        worker.analyze(on_frame=callback)
                    self.assertTrue(parent.closed)
            finally:
                parent.close(); child.close()


if __name__ == '__main__': unittest.main()
