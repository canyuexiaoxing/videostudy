import json,os,tempfile,unittest
from concurrent.futures import CancelledError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from uuid import uuid4
import numpy as np
import transcription as module
from model_diagnostics import close_logs

class BatchTranscriptionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.id=str(uuid4());(self.root/self.id).write_bytes(b'fixture')
  model=self.root/'faster-whisper-small';model.mkdir();(model/'model.bin').write_bytes(b'fixture')
  self.env=patch.dict(os.environ,{'MEDIA_TEMP_DIR':str(self.root),'MODEL_DIR':str(self.root),'MODEL_LOG_DIR':str(self.root/'logs'),'WHISPER_MODEL':'small','WHISPER_DEVICE':'cuda','WHISPER_COMPUTE_TYPE':'float16','WHISPER_BATCH_SIZE':'4'})
  self.env.start();self.addCleanup(self.env.stop);self.addCleanup(close_logs)
 def test_defaults_and_invalid_sizes(self):
  with patch.dict(os.environ,{},clear=True):
   self.assertEqual(module.transcription_batch_size('cuda'),4);self.assertEqual(module.transcription_batch_size('cpu'),0)
  for value in ('-1','bad','64'):
   with patch.dict(os.environ,{'WHISPER_BATCH_SIZE':value}):
    with self.assertRaises(ValueError):module.transcription_batch_size('cuda')
 def test_batch_size_changes_checkpoint_and_standard_override_preserves_old_key(self):
  key=module.speech_checkpoint_key();self.assertIn(':batch4:segment-timestamps',key)
  with patch.dict(os.environ,{'WHISPER_BATCH_SIZE':'8'}):self.assertNotEqual(key,module.speech_checkpoint_key())
  with patch.dict(os.environ,{'WHISPER_BATCH_SIZE':'0'}):self.assertEqual(module.speech_checkpoint_key(),'faster-whisper-small:beam5:vad:float16:cuda')
 def test_pipeline_is_fresh_for_each_course(self):
  factory=Mock(side_effect=[object(),object()]);model=object()
  with patch.dict('sys.modules',{'faster_whisper':SimpleNamespace(BatchedInferencePipeline=factory)}):
   self.assertIsNot(module._get_batch_pipeline(model),module._get_batch_pipeline(model));self.assertEqual(factory.call_count,2)
 def test_batch4_preserves_segment_times_and_callback_schema(self):
  audio=np.zeros(4*16000,dtype=np.float32);engine=Mock()
  engine.transcribe.return_value=(iter([SimpleNamespace(start=1.2,end=2.3,text='  公式条件  '),SimpleNamespace(start=2.5,end=3.1,text='第二段')]),SimpleNamespace(language='zh'))
  callbacks=[]
  def on_segment(item):callbacks.append(dict(item));item['text']='changed callback copy'
  with patch('transcription.subprocess.run',return_value=SimpleNamespace(stdout='0')),patch('transcription._decode_audio',return_value=audio),patch('transcription._get_model') as model,patch('transcription._get_batch_pipeline',return_value=engine):
   result=module.transcribe_file(self.id,on_segment)
  self.assertIs(engine.transcribe.call_args.args[0],audio)
  self.assertEqual(engine.transcribe.call_args.kwargs,dict(beam_size=5,vad_filter=True,batch_size=4,without_timestamps=False,vad_parameters={'min_silence_duration_ms':2000}))
  self.assertEqual(result['segments'][0],dict(id='t_1',startMs=1200,endMs=2300,text='公式条件'))
  self.assertEqual(callbacks,result['segments']);self.assertEqual(result['language'],'zh')
 def test_oom_logs_reason_without_silent_model_or_batch_fallback(self):
  engine=Mock();engine.transcribe.side_effect=RuntimeError('CUDA out of memory')
  with patch('transcription.subprocess.run',return_value=SimpleNamespace(stdout='0')),patch('transcription._decode_audio',return_value=np.zeros(16000,dtype=np.float32)),patch('transcription._get_model') as model,patch('transcription._get_batch_pipeline',return_value=engine),self.assertLogs('uvicorn.error.model_diagnostics',level='INFO') as logs:
   with self.assertRaises(RuntimeError):module.transcribe_file(self.id)
  self.assertEqual(engine.transcribe.call_count,1);self.assertEqual(model.call_count,1)
  self.assertIn('out_of_memory','\n'.join(logs.output))
 def test_invalid_time_is_rejected(self):
  engine=Mock();engine.transcribe.return_value=(iter([SimpleNamespace(start=2,end=1,text='bad')]),SimpleNamespace(language='zh'))
  with patch('transcription.subprocess.run',return_value=SimpleNamespace(stdout='0')),patch('transcription._decode_audio',return_value=np.zeros(3*16000,dtype=np.float32)),patch('transcription._get_model'),patch('transcription._get_batch_pipeline',return_value=engine):
   with self.assertRaises(ValueError):module.transcribe_file(self.id)

 def test_cancellation_propagates_and_is_logged(self):
  engine=Mock();engine.transcribe.return_value=(iter([SimpleNamespace(start=0,end=1,text='PRIVATE')]),SimpleNamespace(language='zh'))
  with patch('transcription.subprocess.run',return_value=SimpleNamespace(stdout='0')),patch('transcription._decode_audio',return_value=np.zeros(16000,dtype=np.float32)),patch('transcription._get_model'),patch('transcription._get_batch_pipeline',return_value=engine):
   with self.assertRaises(CancelledError):module.transcribe_file(self.id,Mock(side_effect=CancelledError()))
  rows=[json.loads(line) for line in (self.root/'logs/model-events.jsonl').read_text().splitlines()]
  self.assertEqual(rows[-1]['status'],'cancelled');self.assertEqual(rows[-1]['batch_size'],4)
  self.assertEqual(rows[-1]['device'],'cuda');self.assertEqual(rows[-1]['compute_type'],'float16')
  self.assertNotIn('PRIVATE',json.dumps(rows))
 def test_silent_video_skips_model(self):
  with patch('transcription.subprocess.run',return_value=SimpleNamespace(stdout='')),patch('transcription._get_model') as model:
   self.assertEqual(module.transcribe_file(self.id),{'language':'und','segments':[]})
   model.assert_not_called()
