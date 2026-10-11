from pathlib import Path
p=Path('E:/workp/videostudy/agent-python/test_ignored_region.py')
with p.open('a',encoding='utf-8') as f:
    f.write('''
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
            with patch.dict(os.environ,{'MEDIA_TEMP_DIR':directory,'KEYFRAME_DIR':str(Path(directory)/'frames')}), patch('analysis.transcribe_file',side_effect=AssertionError('legacy checkpoint must be reused')), patch('analysis.VisualOcrWorker') as worker, patch('analysis.media_duration_ms',return_value=10000), patch('analysis.review_visual_coverage',return_value=([],{'status':'not_applicable'})), patch('analysis.group_pages',return_value=([],[])), patch('analysis.safe_overview',return_value={'status':'empty'}), patch('analysis.build_mind_map',return_value={'status':'empty'}):
                worker.return_value.__enter__.return_value.analyze.return_value=[]
                result=analysis.analyze_file(file_id)
                self.assertEqual(result['reusedCheckpoints']['transcription'],1)
''')
