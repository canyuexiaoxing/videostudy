"""Build self-contained Windows runtimes from official, integrity-checked releases. No Docker."""
from pathlib import Path
import argparse,urllib.request,json,hashlib,tarfile,zipfile,shutil,subprocess,os,time,concurrent.futures,sys
ROOT=Path(__file__).resolve().parents[3];STAGE=ROOT/'.local/native';CACHE=ROOT/'.local/dev/native-runtime/downloads';CACHE.mkdir(parents=True,exist_ok=True);RUNTIME=STAGE/'runtime';RUNTIME.mkdir(parents=True,exist_ok=True)
p=argparse.ArgumentParser();p.add_argument('--bootstrap-only',action='store_true');p.add_argument('--deps-only',action='store_true');a=p.parse_args()
PROXY='http://127.0.0.1:7897'
ASSETS=[{'id':'python','name':'python311.tar.gz','url':'https://github.com/astral-sh/python-build-standalone/releases/download/20261013/cpython-3.11.17%2B20261013-x86_64-pc-windows-msvc-install_only_stripped.tar.gz','sha256':'54a38c5e7cc1a5fd2b0182b495f29606dc1455d18ebfd3b5bf0a3c09253b5031'}, {'id':'java','name':'java21.zip','url':'https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jre_x64_windows_hotspot_21.0.12.1_1.zip','sha256':'d35f31e712f0fcf6ac5a093edc90204fbff22f720ba3950bd09d331d5e621636'}, {'id':'inno','name':'innosetup.exe','url':'https://github.com/jrsoftware/issrc/releases/download/is-7_1_0/innosetup-7.1.0-x64.exe','sha256':'0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f'}]
def log(event,**kw):print(json.dumps({'stage':event,'time':time.time(),**kw}),flush=True)
def opener(url):return urllib.request.build_opener(urllib.request.ProxyHandler({'https':PROXY,'http':PROXY} if 'github' in url else {}))
def metadata(url):
 for attempt in range(4):
  try:
   with opener(url).open(urllib.request.Request(url,headers={'User-Agent':'Framewise-native-builder'}),timeout=30) as response:return json.load(response)
  except Exception:
   if attempt==3:raise
   time.sleep(attempt+1)
def sha(file):
 digest=hashlib.sha256()
 with file.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
 return digest.hexdigest()
def download(asset):
 file=CACHE/asset['name'];part=file.with_suffix(file.suffix+'.part');start=time.monotonic()
 if file.exists() and sha(file)==asset['sha256']:return file
 for attempt in range(6):
  try:
   offset=part.stat().st_size if part.exists() else 0;headers={'User-Agent':'Framewise-native-builder'}
   if offset:headers['Range']='bytes='+str(offset)+'-'
   with opener(asset['url']).open(urllib.request.Request(asset['url'],headers=headers),timeout=45) as response:
    resume=offset and response.status==206
    with part.open('ab' if resume else 'wb') as output:
     while block:=response.read(1024*1024):output.write(block)
   if sha(part)!=asset['sha256']:part.unlink();raise RuntimeError('download_hash_mismatch_'+asset['id'])
   part.replace(file);log('download_complete',asset=asset['id'],bytes=file.stat().st_size,elapsedSeconds=round(time.monotonic()-start,2));return file
  except Exception as e:
   log('download_retry',asset=asset['id'],attempt=attempt+1,error=type(e).__name__)
   if attempt==5:raise
   time.sleep(min(attempt+1,5))
def extract(file,destination):
 if destination.exists():return
 temp=destination.with_name(destination.name+'.extract');temp.mkdir(parents=True,exist_ok=True)
 if zipfile.is_zipfile(file):
  with zipfile.ZipFile(file) as z:
   for name in z.namelist():
    target=(temp/name).resolve();target.relative_to(temp.resolve())
   z.extractall(temp)
 else:
  with tarfile.open(file,'r:gz') as t:t.extractall(temp,filter='data')
 folders=list(temp.iterdir());source=folders[0] if len(folders)==1 and folders[0].is_dir() else temp
 shutil.move(str(source),str(destination))
 if temp.exists() and temp!=source:shutil.rmtree(temp)
 log('extracted',component=destination.name)
def run(command,**kwargs):
 stage=kwargs.pop('stageName','build');log('command',program=Path(command[0]).name,stageName=stage)
 with (ROOT/'.local/qa/native-delivery'/('build-'+stage+'.log')).open('a',encoding='utf8') as output:
  return subprocess.run(command,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),stdout=output,stderr=subprocess.STDOUT,**kwargs)
if not a.deps_only:
 assets_file=STAGE/'assets.lock.json'
 if assets_file.exists():assets=json.loads(assets_file.read_text())
 else:
  release=metadata('https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest');asset=next(x for x in release['assets'] if x['name']=='ffmpeg-master-latest-win64-lgpl.zip');assets=ASSETS+[{'id':'ffmpeg','name':'ffmpeg-lgpl.zip','url':asset['browser_download_url'],'sha256':asset['digest'].split(':')[1]}];assets_file.write_text(json.dumps(assets,indent=2))
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:files=list(pool.map(download,assets))
 for asset,file in zip(assets,files):
  if asset['id']=='inno':continue
  extract(file,RUNTIME/asset['id'])
 for target in ['person']:
  if not (RUNTIME/target).exists():shutil.copytree(RUNTIME/'python',RUNTIME/target)
 inno=ROOT/'.local/dev/native-runtime/inno'
 if not (inno/'ISCC.exe').exists():run([str(CACHE/'innosetup.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER','/DIR='+str(inno)],stageName='installer_tools')
if a.bootstrap_only:raise SystemExit(0)
env={**os.environ,'PIP_DISABLE_PIP_VERSION_CHECK':'1','PIP_NO_INPUT':'1','PIP_DEFAULT_TIMEOUT':'20','PIP_RETRIES':'2','PYTHONIOENCODING':'utf-8','PIP_CACHE_DIR':str(ROOT/'.local/dev/native-runtime/pip-cache')}
base=RUNTIME/'python/python.exe';person=RUNTIME/'person/python.exe'
requirements=STAGE/'requirements-native.txt';requirements.write_text('numpy==1.26.4\nfastapi>=0.115,<1\npypinyin>=0.55,<1\nuvicorn>=0.34,<1\nfaster-whisper>=1.1,<2\npaddleocr>=3.7,<3.8\nopencv-contrib-python==4.10.0.84\nav>=18,<19\n')
run([str(base),'-m','pip','install','--only-binary=:all:','-r',str(requirements)],env=env,stageName='python_dependencies')
run([str(base),'-m','pip','install','paddlepaddle-gpu==3.2.1','--index-url','https://www.paddlepaddle.org.cn/packages/stable/cu126/','--extra-index-url','https://pypi.org/simple'],env=env,stageName='paddle_gpu')
run([str(person),'-m','pip','install','torch==2.6.0','torchvision==0.21.0','--index-url','https://download.pytorch.org/whl/cu126'],env={**env,'HTTPS_PROXY':PROXY},stageName='torch_gpu')
run([str(person),'-m','pip','install','numpy==1.26.4','ultralytics==8.4.4','opencv-python==4.10.0.84'],env=env,stageName='yolo_dependencies')
for name,python in [('python',base),('person',person)]:
 freeze=subprocess.check_output([str(python),'-m','pip','freeze'],env=env,text=True);(STAGE/(name+'-requirements.lock.txt')).write_text(freeze)
log('runtime_ready',root=str(RUNTIME))
