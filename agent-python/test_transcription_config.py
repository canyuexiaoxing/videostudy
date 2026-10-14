import os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
from uuid import uuid4
from transcription import transcription_config,speech_checkpoint_key,transcribe_file
class TranscriptionConfigTest(unittest.TestCase):
 def test_small_cuda_config_changes_checkpoint_identity(self):
  with patch.dict(os.environ,{'WHISPER_MODEL':'small','WHISPER_DEVICE':'cuda','WHISPER_COMPUTE_TYPE':'float16'}):
   self.assertEqual(transcription_config(),('small','cuda','float16'))
   self.assertEqual(speech_checkpoint_key(),'faster-whisper-small:beam5:vad:float16:cuda:batch4:segment-timestamps:vad-minsilence2000')
 def test_cpu_default_retains_legacy_cache(self):
  with patch.dict(os.environ,{},clear=True):
   self.assertEqual(transcription_config(),('base','cpu','int8'))
   self.assertEqual(speech_checkpoint_key(),'faster-whisper-base:beam5:vad:int8')
 def test_invalid_model_and_device_are_rejected(self):
  for setting in ({'WHISPER_MODEL':'../secret'},{'WHISPER_DEVICE':'bad'}):
   with patch.dict(os.environ,setting):
    with self.assertRaises(ValueError):transcription_config()
 def test_gpu_model_receives_existing_decode_parameters(self):
  with tempfile.TemporaryDirectory() as directory:
   media_id=str(uuid4());Path(directory,media_id).write_bytes(b'fixture');model=Path(directory,'faster-whisper-small');model.mkdir();(model/'model.bin').write_bytes(b'fixture')
   engine=Mock();engine.transcribe.return_value=(iter([SimpleNamespace(start=1.2,end=2.3,text='  洛必达法则  ')]),SimpleNamespace(language='zh'))
   with patch.dict(os.environ,{'MEDIA_TEMP_DIR':directory,'MODEL_DIR':directory,'WHISPER_BATCH_SIZE':'0','WHISPER_MODEL':'small','WHISPER_DEVICE':'cuda','WHISPER_COMPUTE_TYPE':'float16'}),patch('transcription.subprocess.run',return_value=SimpleNamespace(stdout='0')),patch('transcription._get_model',return_value=engine) as load:
    result=transcribe_file(media_id)
   load.assert_called_once_with(str(model.resolve()),'cuda','float16');engine.transcribe.assert_called_once_with(str(Path(directory,media_id).resolve()),beam_size=5,vad_filter=True)
   self.assertEqual(result['segments'][0],dict(id='t_1',startMs=1200,endMs=2300,text='洛必达法则'))

 def test_same_model_configuration_is_loaded_once(self):
  from transcription import _get_model,_load_model
  _load_model.cache_clear()
  try:
   initialize=Mock()
   with patch.dict('sys.modules',{'faster_whisper':SimpleNamespace(WhisperModel=initialize)}):
    first=_get_model('/test/model','cuda','float16');second=_get_model('/test/model','cuda','float16')
    self.assertIs(first,second);initialize.assert_called_once_with('/test/model',device='cuda',compute_type='float16')
  finally:_load_model.cache_clear()
