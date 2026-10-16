"""Full-file decode to null: no sampling, selection, image save, OCR or provider."""
import subprocess,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];video=ROOT/'30MIN.mp4'
info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,r_frame_rate:format=duration','-of','json',str(video)]))
started=time.perf_counter()
subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-i',str(video),'-map','0:v:0','-an','-sn','-dn','-fps_mode','passthrough','-f','null','-'],check=True)
result={'video':info,'decodeOnlySeconds':round(time.perf_counter()-started,3),'decoder':'CPU FFmpeg default threading','scope':'decode all video frames to null; excludes sampling, BGR conversion, selection, save, OCR, grouping, audio','paidCalls':0}
folder=ROOT/'.local/qa/decode-only';folder.mkdir(parents=True,exist_ok=True);(folder/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
