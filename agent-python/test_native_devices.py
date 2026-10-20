"""Native policy tests run without loading optional neural frameworks."""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

class NativeDevicesTests(unittest.TestCase):
 def policy(self):
  import native_devices
  return native_devices
 def test_auto_selects_modules_independently_and_records_fallback(self):
  p=self.policy()
  probes={'whisper':{'gpu':True,'cpu':True},'ocr':{'gpu':False,'cpu':True},'person':{'gpu':True,'cpu':True}}
  state=p.select_devices('auto',probes)
  self.assertEqual(state['devices'],{'whisper':'cuda','ocr':'cpu','person':'cuda'})
  self.assertEqual(state['fallbacks'],['ocr'])
 def test_cpu_requires_working_cpu_and_never_selects_cuda(self):
  p=self.policy(); good={k:{'gpu':True,'cpu':True} for k in p.MODULES}
  self.assertEqual(set(p.select_devices('cpu',good)['devices'].values()),{'cpu'})
  good['ocr']['cpu']=False
  with self.assertRaises(p.DevicePolicyError):p.select_devices('cpu',good)
 def test_gpu_is_strict_and_invalid_mode_rejected(self):
  p=self.policy(); bad={k:{'gpu':False,'cpu':True} for k in p.MODULES}
  with self.assertRaises(p.DevicePolicyError):p.select_devices('gpu',bad)
  with self.assertRaises(ValueError):p.select_devices('invalid',bad)
 def test_probe_timeout_is_bounded_and_output_never_contains_stderr(self):
  p=self.policy()
  with patch.object(p.subprocess,'run',side_effect=subprocess.TimeoutExpired('python',3)):
   result=p.probe_module('ocr',sys.executable,'cuda',3)
  self.assertFalse(result['ok']);self.assertEqual(result['reason'],'timeout')
 def test_probe_runs_actual_operation_and_uses_separate_person_interpreter(self):
  p=self.policy();calls=[]
  def run(args,**kwargs):
   calls.append((args,kwargs));return subprocess.CompletedProcess(args,0,'FRAMEWISE_PROBE_OK\n','secret')
  with patch.object(p.subprocess,'run',side_effect=run):
   report=p.probe_all('auto',sys.executable,'person-python',4)
  self.assertEqual(report['person']['gpu']['ok'],True)
  self.assertEqual([x[0][0] for x in calls][-2:],['person-python']*2)
  self.assertIn('matmul',p.PROBE_SCRIPTS['ocr']);self.assertIn('matmul',p.PROBE_SCRIPTS['person'])
  self.assertIn('Whisper',p.PROBE_SCRIPTS['whisper'])
 def test_dll_directory_handles_retained(self):
  p=self.policy()
  with tempfile.TemporaryDirectory() as d,patch.object(p.os,'add_dll_directory',create=True) as add:
   handle=object();add.return_value=handle;p.configure_dll_directories([d,d])
   self.assertIn(handle,p._DLL_HANDLES);self.assertEqual(add.call_count,1)
   self.assertIn(str(Path(d).resolve()),os.environ['PATH'].split(os.pathsep))
 def test_only_native_auto_allows_oom_retry(self):
  p=self.policy()
  for mode,expected in [('auto',True),('gpu',False),('cpu',False),('',False)]:
   with patch.dict(os.environ,{'FRAMEWISE_DEVICE_MODE':mode}):
    self.assertEqual(p.allow_cpu_fallback(RuntimeError('CUDA out of memory'),'cuda'),expected)
    self.assertFalse(p.allow_cpu_fallback(RuntimeError('invalid model'),'cuda'))

class NativeBootstrapTests(unittest.TestCase):
 def test_environment_is_owned_and_config_rejects_secrets(self):
  import native_bootstrap as b
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{},clear=True):
   config=b.validate_config({'schemaVersion':1,'dataDir':d,'mode':'auto'})
   b.configure_environment(config)
   self.assertEqual(os.environ['WHISPER_MODEL'],'small')
   for key in ('MEDIA_TEMP_DIR','KEYFRAME_DIR','MODEL_LOG_DIR','USERPROFILE','HF_HOME','APPDATA','LOCALAPPDATA'):
    self.assertTrue(Path(os.environ[key]).is_relative_to(Path(d).resolve()))
   with self.assertRaises(ValueError):b.validate_config({'dataDir':d,'apiKey':'secret'})
 def test_atomic_reports_and_device_environment(self):
  import native_bootstrap as b
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{},clear=True):
   config=b.validate_config({'dataDir':d,'mode':'auto'})
   b.configure_environment(config)
   state={'mode':'auto','devices':{'whisper':'cuda','ocr':'cpu','person':'cuda'},'fallbacks':['ocr']}
   b.apply_devices(state);b.atomic_json(Path(d)/'runtime'/'runtime-state.json',state)
   self.assertEqual(os.environ['OCR_DEVICE'],'cpu');self.assertEqual(os.environ['PERSON_DEVICE'],'cuda');self.assertEqual(os.environ['PERSON_SEGMENTATION'],'off')
   self.assertEqual(json.loads((Path(d)/'runtime'/'runtime-state.json').read_text())['fallbacks'],['ocr'])
 def test_native_adjacent_uses_selected_cpu(self):
  from person_selection import settings
  with patch.dict(os.environ,{'FRAMEWISE_DEVICE_MODE':'auto','PERSON_SEGMENTATION':'cpu'}):
   self.assertEqual(settings('adjacent')['mode'],'cpu')



class NativeInferenceFallbackTests(unittest.TestCase):
 def test_transcription_shrinks_batch_then_cpu_before_any_callbacks(self):
  import transcription as t
  from types import SimpleNamespace
  self.assertTrue(hasattr(t,'_transcribe_file_once'),'Missing bounded inference attempt boundary')
  callbacks=[];calls=[]
  def attempt(file_id,on_segment=None,*,_runtime_override=None):
   calls.append(_runtime_override)
   if len(calls)<4:raise RuntimeError('CUDA out of memory')
   on_segment({'id':'t_1'});return {'segments':[{'id':'t_1'}]}
  with patch.dict(os.environ,{'FRAMEWISE_DEVICE_MODE':'auto','WHISPER_DEVICE':'cuda','WHISPER_MODEL':'small','WHISPER_COMPUTE_TYPE':'float16','WHISPER_BATCH_SIZE':'4'}),patch.object(t,'_transcribe_file_once',side_effect=attempt,create=True),patch('native_devices.record_fallback'):
   result=t.transcribe_file('test',callbacks.append)
  self.assertEqual([c[3] for c in calls[1:]],[2,1,0]);self.assertEqual(calls[-1][1],'cpu');self.assertEqual(callbacks,[{'id':'t_1'}])
 def test_transcription_never_retries_after_callback_delivery(self):
  import transcription as t
  self.assertTrue(hasattr(t,'_transcribe_file_once'),'Missing bounded inference attempt boundary')
  def attempt(file_id,on_segment=None,**kwargs):
   on_segment({'id':'t_1'});raise RuntimeError('CUDA out of memory')
  with patch.dict(os.environ,{'FRAMEWISE_DEVICE_MODE':'auto','WHISPER_DEVICE':'cuda'}),patch.object(t,'_transcribe_file_once',side_effect=attempt,create=True) as attempt_mock:
   with self.assertRaises(RuntimeError):t.transcribe_file('test',lambda value:None)
  self.assertEqual(attempt_mock.call_count,1)
 def test_strict_gpu_never_retries(self):
  import transcription as t
  self.assertTrue(hasattr(t,'_transcribe_file_once'),'Missing bounded inference attempt boundary')
  with patch.dict(os.environ,{'FRAMEWISE_DEVICE_MODE':'gpu','WHISPER_DEVICE':'cuda'}),patch.object(t,'_transcribe_file_once',side_effect=RuntimeError('CUDA out of memory'),create=True) as attempt:
   with self.assertRaises(RuntimeError):t.transcribe_file('test')
  self.assertEqual(attempt.call_count,1)
 def test_ocr_cpu_retry_keeps_prediction_input_and_text(self):
  import visual_evidence as v
  from types import SimpleNamespace
  from unittest.mock import Mock
  frame=object();gpu=Mock();gpu.predict.side_effect=RuntimeError('CUDA out of memory');cpu=Mock();cpu.predict.return_value=[SimpleNamespace(json={'res':{'rec_texts':['board'],'rec_scores':[.9],'rec_polys':[[[0,0],[1,0],[1,1]]]}})]
  with patch.dict(os.environ,{'FRAMEWISE_DEVICE_MODE':'auto','OCR_DEVICE':'gpu:0'}),patch.object(v,'_ocr_model',side_effect=[gpu,cpu]),patch('native_devices.record_fallback'):
   result=v._recognize(frame)
  self.assertEqual(result[0]['text'],'board');cpu.predict.assert_called_once_with(frame)


class NativePersonFallbackTests(unittest.TestCase):
 def test_person_retries_same_frame_on_cpu_only_in_auto(self):
  import person_mask_worker as worker
  from unittest.mock import Mock
  from types import SimpleNamespace
  self.assertTrue(hasattr(worker,'predict_with_fallback'))
  model=Mock();expected=object();model.predict.side_effect=[RuntimeError('CUDA out of memory'),[expected]]
  with patch.dict(os.environ,{'FRAMEWISE_DEVICE_MODE':'auto'}),patch.dict(sys.modules,{'torch':SimpleNamespace(cuda=SimpleNamespace(empty_cache=lambda:None))}),patch('native_devices.record_fallback'):
   result,device,fallback=worker.predict_with_fallback(model,object(),'0')
  self.assertIs(result,expected);self.assertEqual(device,'cpu');self.assertTrue(fallback)
  self.assertEqual(model.predict.call_args.kwargs['imgsz'],640);model.to.assert_called_once_with('cpu')

class NativeStartupTests(unittest.TestCase):
 def test_token_guard_covers_health_and_uses_only_header(self):
  import native_bootstrap as b
  import asyncio
  self.assertTrue(hasattr(b,'RuntimeTokenMiddleware'))
  async def exercise(headers):
   replies=[]
   async def app(scope,receive,send):await send({'type':'http.response.start','status':200,'headers':[]})
   async def receive():return {'type':'http.request','body':b''}
   async def send(value):replies.append(value)
   await b.RuntimeTokenMiddleware(app,'test-token')({'type':'http','path':'/health','headers':headers},receive,send)
   return replies[0]['status']
  self.assertEqual(asyncio.run(exercise([])),403)
  self.assertEqual(asyncio.run(exercise([(b'x-framewise-runtime',b'wrong')])),403)
  self.assertEqual(asyncio.run(exercise([(b'x-framewise-runtime',b'test-token')])),200)
 def test_missing_models_are_pending_not_gpu_failure(self):
  import native_devices as p
  with patch.object(p.subprocess,'run',return_value=subprocess.CompletedProcess([],3,'FRAMEWISE_PROBE_MISSING_MODELS\n','')):
   result=p.probe_module('whisper',sys.executable,'cuda')
  self.assertEqual(result['reason'],'missing_models');self.assertFalse(result['ok'])
  probes={name:{'gpu':{'ok':True},'cpu':{'ok':True}} for name in p.MODULES};probes['whisper']['gpu']=result
  state=p.select_devices('auto',probes)
  self.assertEqual(state['devices']['whisper'],'cuda');self.assertIn('whisper',state['pending'])

class NativePipeTests(unittest.TestCase):
 def test_pipe_adapter_never_exposes_windows_seek_or_tell(self):
  import frame_stream as fs
  from unittest.mock import Mock
  self.assertTrue(hasattr(fs,'NonSeekablePipe'))
  pipe=Mock();pipe.read.return_value=b'frame';reader=fs.NonSeekablePipe(pipe)
  self.assertEqual(reader.read(5),b'frame');self.assertFalse(reader.seekable())
  self.assertFalse(hasattr(reader,'seek'));self.assertFalse(hasattr(reader,'tell'))
  pipe.seek.assert_not_called();pipe.tell.assert_not_called()




class NativePrepareTests(unittest.TestCase):
 def test_pending_model_boot_reports_missing_files_without_secret(self):
  import native_bootstrap as b
  import native_devices as p
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'FRAMEWISE_RUNTIME_TOKEN':'never-write-this-token'}):
   probes={name:{'gpu':{'ok':True},'cpu':{'ok':True}} for name in p.MODULES}
   probes['whisper']['gpu']={'ok':False,'reason':'missing_models'}
   with patch.object(b,'probe_all',return_value=probes):report=b.prepare(b.validate_config({'dataDir':d,'mode':'auto'}))
   self.assertFalse(report['available']);self.assertEqual(report['modules']['whisper']['reason'],'missing_models')
   self.assertEqual(report['modules']['whisper']['device'],'cuda')
   self.assertEqual(set(report['pending']),{'whisper','ocr','person'})
   output=(Path(d)/'runtime/hardware-report.json').read_text();self.assertNotIn('never-write-this-token',output)




class NativeCallbackTests(unittest.TestCase):
 def test_callback_adds_runtime_header_only_for_native_launch(self):
  import subtitle_delivery as delivery
  from unittest.mock import MagicMock
  response=MagicMock();response.__enter__.return_value.read.return_value=b'{}'
  for runtime,expected in [('native-private-token','native-private-token'),('',None)]:
   with patch.dict(os.environ,{'FRAMEWISE_RUNTIME_TOKEN':runtime}),patch.object(delivery,'urlopen',return_value=response) as send:
    self.assertTrue(delivery._deliver_source('http://127.0.0.1/callback','subtitle-token',b'{}'))
   request=send.call_args.args[0]
   self.assertEqual(request.get_header('X-framewise-runtime'),expected)
   self.assertEqual(request.get_header('X-subtitle-token'),'subtitle-token')



class NativeHiddenMediaTests(unittest.TestCase):
 def test_visual_probe_hides_windows_console(self):
  import visual_evidence as v
  from types import SimpleNamespace
  with patch.object(v.subprocess,'run',return_value=SimpleNamespace(stdout='0')) as run:v._has_video(Path('fixture'))
  self.assertEqual(run.call_args.kwargs.get('creationflags',0),getattr(subprocess,'CREATE_NO_WINDOW',0))
 def test_audio_probe_hides_windows_console(self):
  import transcription as t
  from types import SimpleNamespace
  from uuid import uuid4
  with tempfile.TemporaryDirectory() as d:
   file_id=str(uuid4());Path(d,file_id).touch()
   with patch.dict(os.environ,{'MEDIA_TEMP_DIR':d,'WHISPER_DEVICE':'cpu','WHISPER_COMPUTE_TYPE':'int8'}),patch.object(t.subprocess,'run',return_value=SimpleNamespace(stdout='')) as run:t.transcribe_file(file_id)
  self.assertEqual(run.call_args.kwargs.get('creationflags',0),getattr(subprocess,'CREATE_NO_WINDOW',0))

if __name__=='__main__':unittest.main()


