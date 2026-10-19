from pathlib import Path
import io,tarfile,subprocess,time
ROOT=Path(__file__).resolve().parents[3]
DOCKER='D:/mytools/deskdocker/resources/bin/docker.exe'
folder='/tmp/delivery-qa-'+str(int(time.time()))
runner='''import os,socket,unittest
if __name__=='__main__':
 for key in list(os.environ):
  if any(word in key.upper() for word in ('API_KEY','TOKEN','SECRET')):os.environ.pop(key,None)
 def blocked(*args,**kwargs):raise RuntimeError('delivery_qa_external_network_blocked')
 socket.create_connection=blocked
 original_connect=socket.socket.connect
 def connect(sock,address):
  if isinstance(address,tuple) and address[0] not in ('127.0.0.1','::1','localhost'):raise RuntimeError('delivery_qa_external_network_blocked')
  return original_connect(sock,address)
 socket.socket.connect=connect
 suite=unittest.defaultTestLoader.discover('.',pattern='test_*.py')
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 raise SystemExit(not result.wasSuccessful())
'''
buffer=io.BytesIO()
with tarfile.open(fileobj=buffer,mode='w') as archive:
 for file in (ROOT/'agent-python').glob('*.py'):archive.add(file,arcname=file.name)
 data=runner.encode();info=tarfile.TarInfo('delivery_runner.py');info.size=len(data);archive.addfile(info,io.BytesIO(data))
subprocess.run([DOCKER,'exec','videostudy-agent-python-1','mkdir','-p',folder],check=True)
subprocess.run([DOCKER,'exec','-i','videostudy-agent-python-1','tar','-xf','-','-C',folder],input=buffer.getvalue(),check=True)
result=subprocess.run([DOCKER,'exec','-w',folder,'-e','PYTHONPATH='+folder,'-e','KEYFRAME_DIR='+folder+'/keyframes','-e','MEDIA_TEMP_DIR='+folder+'/media','-e','MODEL_LOG_DIR='+folder+'/logs','videostudy-agent-python-1','python','delivery_runner.py'],capture_output=True,timeout=180)
(ROOT/'.local/qa/delivery-python-full.log').write_bytes(result.stdout+result.stderr)
print((result.stdout+result.stderr).decode(errors='replace')[-2500:]);raise SystemExit(result.returncode)
