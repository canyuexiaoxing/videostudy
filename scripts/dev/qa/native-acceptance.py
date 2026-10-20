"""Actual bundled inference acceptance with development tools removed from PATH."""
from pathlib import Path
import argparse,json,os,sys,time,subprocess,traceback,faulthandler
faulthandler.dump_traceback_later(45,repeat=True)
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'agent-python'))
parser=argparse.ArgumentParser();parser.add_argument('--module',choices=['person','speech','playback'],required=True);parser.add_argument('--device',choices=['cpu','cuda','auto'],required=True);parser.add_argument('--image');args=parser.parse_args()
QA=ROOT/'.local/qa/native-delivery/python-native';QA.mkdir(parents=True,exist_ok=True)
from native_bootstrap import configure_environment,validate_config
from native_devices import configure_dll_directories
configure_environment(validate_config({'dataDir':str(QA/'data'),'modelDir':str(ROOT/'.local/native/model-seed'),'mode':'gpu' if args.device=='cuda' else 'cpu','ffmpegDir':str(ROOT/'.local/native/runtime/ffmpeg/bin')}))
os.environ['PATH']=str(ROOT/'.local/native/runtime/ffmpeg/bin')+os.pathsep+os.environ.get('SystemRoot','C:/Windows')+'/System32'
configure_dll_directories()
started=time.monotonic();result={'module':args.module,'device':args.device,'startedAt':time.time(),'strippedPath':True}
try:
 if args.module=='person':
  import numpy as np,torch
  from ultralytics import YOLO
  torch.set_num_threads(4)
  model=YOLO(str(ROOT/'.local/native/model-seed/yolo26/yolo26n-seg.pt'))
  import cv2
  image=cv2.imread(args.image) if args.image else np.zeros((360,640,3),np.uint8)
  assert image is not None,'image_unreadable'
  inference=model.predict(image,classes=[0],retina_masks=True,device='0' if args.device=='cuda' else 'cpu',verbose=False)[0]
  result.update(detections=len(inference.boxes),runtimeDevice=str(next(model.model.parameters()).device),maskPixels=int(inference.masks.data.sum().item()) if inference.masks is not None else 0)
  if args.image:assert result['detections']>0 and result['maskPixels']>0,'person_mask_missing'
 elif args.module=='speech':
  from faster_whisper import WhisperModel
  model=WhisperModel(str(ROOT/'.local/native/model-seed/faster-whisper-small'),device=args.device,compute_type='float16' if args.device=='cuda' else 'int8')
  segments,info=model.transcribe(str(QA/'speech.wav'),language='en',beam_size=3,vad_filter=False)
  text=' '.join(x.text for x in segments)
  result.update(transcript=text,language=info.language)
  assert ('five' in text.lower() or '5' in text) and ('three' in text.lower() or '3' in text),'speech_content_missing'
 else:
  import compatible_playback as playback
  os.environ['FRAMEWISE_DEVICE_MODE']='gpu' if args.device=='cuda' else args.device
  encoder=playback.choose_encoder();output=QA/('playback-'+args.device+'.mp4')
  cmd=['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=320x180:r=10:d=2','-i',str(QA/'speech.wav'),'-t','2','-c:v',encoder,'-c:a','aac',str(output)]
  proc=subprocess.run(cmd,capture_output=True,text=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
  assert proc.returncode==0,proc.stderr[-1000:]
  data=playback.probe(output);result.update(encoder=encoder,duration=data['format']['duration'],bytes=output.stat().st_size)
  import shutil,threading,uuid
  identity=str(uuid.uuid4());directory=QA/identity;directory.mkdir();shutil.copy2(output,directory/'input')
  playback.active[identity]={'cancel':threading.Event(),'process':None};playback.slot.acquire()
  playback.encode(identity,directory,playback.active[identity]['cancel'])
  state=json.loads((directory/'status.json').read_text(encoding='utf-8'))
  assert state['status']=='completed',state
  assert not (directory/'input').exists()
  result.update(productionEncoder=state['encoder'],productionProgress=state['progress'])
 result['ok']=True
except Exception as error:
 result.update(ok=False,errorType=type(error).__name__,error=str(error)[:300]);traceback.print_exc()
finally:
 result['elapsedSeconds']=round(time.monotonic()-started,3)
 (QA/(args.module+'-'+args.device+('-real-image' if args.image else '')+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
 print('FRAMEWISE_RESULT '+json.dumps(result,ensure_ascii=False),flush=True)
