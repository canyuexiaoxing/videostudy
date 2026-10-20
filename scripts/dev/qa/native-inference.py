"""Native framework verification; isolated data and no provider calls."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time,traceback
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'agent-python'))
parser=argparse.ArgumentParser();parser.add_argument('--module',choices=['whisper','ocr'],required=True);parser.add_argument('--device',choices=['cpu','cuda'],required=True);parser.add_argument('--inference',action='store_true');args=parser.parse_args()
QA=ROOT/'.local/qa/native-inference';QA.mkdir(parents=True,exist_ok=True)
from native_bootstrap import configure_environment,validate_config
from native_devices import configure_dll_directories,PROBE_SCRIPTS
configure_environment(validate_config({'dataDir':str(QA/'data'),'modelDir':str(ROOT/'.local/native/model-seed'),'mode':'gpu' if args.device=='cuda' else 'cpu','ffmpegDir':str(ROOT/'.local/native/runtime/ffmpeg/bin')}))
os.environ['PATH']=str(ROOT/'.local/native/runtime/ffmpeg/bin')+os.pathsep+os.environ.get('SystemRoot','C:/Windows')+'/System32'
configure_dll_directories()
started=time.monotonic();result={'module':args.module,'device':args.device,'inference':args.inference}
try:
 if not args.inference:
  exec(PROBE_SCRIPTS[args.module],{'device':args.device,'os':os,'sys':sys})
 elif args.module=='ocr':
  import numpy as np,cv2
  from visual_evidence import _recognize
  os.environ['OCR_DEVICE']='gpu:0' if args.device=='cuda' else 'cpu'
  image=np.full((240,1000,3),255,np.uint8)
  cv2.putText(image,'FRAMEWISE TEST 123',(25,130),cv2.FONT_HERSHEY_SIMPLEX,2,(0,0,0),4,cv2.LINE_AA)
  lines=_recognize(image)
  result['texts']=[line['text'] for line in lines]
  assert any('123' in line['text'] for line in lines),'synthetic_ocr_text_missing'
 else:
  from uuid import uuid4
  from transcription import transcribe_file
  import av
  identifier=str(uuid4());video=Path(os.environ['MEDIA_TEMP_DIR'])/identifier
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=white:s=320x180:r=5:d=2','-f','lavfi','-i','anullsrc=r=16000:cl=mono','-t','2','-c:v','libx264','-c:a','aac','-f','mp4',str(video)],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
  with av.open(str(video)) as source:result['videoFrames']=len(list(source.decode(video=0)))
  os.environ.update(WHISPER_DEVICE=args.device,WHISPER_COMPUTE_TYPE='float16' if args.device=='cuda' else 'int8',WHISPER_BATCH_SIZE='0')
  transcript=transcribe_file(identifier)
  result['segments']=len(transcript['segments']);assert not transcript['segments'],'silence_transcript_not_empty'
 result['ok']=True
except Exception as error:
 result.update(ok=False,errorType=type(error).__name__,error=str(error)[:300])
 traceback.print_exc()
finally:
 result['elapsedSeconds']=round(time.monotonic()-started,3)
 print('FRAMEWISE_RESULT '+json.dumps(result,ensure_ascii=False),flush=True)
