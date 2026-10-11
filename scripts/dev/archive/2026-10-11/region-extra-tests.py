from pathlib import Path
root=Path('E:/workp/videostudy')
p=root/'agent-python/test_ignored_region.py'
p.write_text(p.read_text(encoding='utf-8')+'''
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
''',encoding='utf-8')
p=root/'agent-python/ignored_region.py';s=p.read_text().replace('if x<0 or y<0 or w<=0','if x<0 or y<0 or x>=1 or y>=1 or w<=0');p.write_text(s)
p=root/'backend-java/src/main/java/cn/videostudy/api/IgnoreRegion.java';s=p.read_text().replace('|| x < 0 || y < 0 || width <= 0','|| x < 0 || y < 0 || x >= 1 || y >= 1 || width <= 0');p.write_text(s)
