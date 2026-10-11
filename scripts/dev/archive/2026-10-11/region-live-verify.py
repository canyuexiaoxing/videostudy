import subprocess,json,time
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
for attempt in range(10):
    try:
        with urlopen('http://127.0.0.1:18080/api/transcriptions/nonexistent',timeout=2) as response: pass
    except HTTPError as error:
        if error.code==404: break
        raise
    except (URLError,TimeoutError):
        if attempt==9: raise
        time.sleep(1)
boundary='region-qa-boundary'
body=(f'--{boundary}\r\nContent-Disposition: form-data; name="ignoredRegion"\r\n\r\n{{"x":0,"y":0,"width":1,"height":1}}\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="qa.mp4"\r\nContent-Type: video/mp4\r\n\r\nqa\r\n--{boundary}--\r\n').encode()
try:
    urlopen(Request('http://127.0.0.1:18080/api/transcriptions',data=body,headers={'Content-Type':f'multipart/form-data; boundary={boundary}'},method='POST'),timeout=10)
    raise AssertionError('Invalid region accepted')
except HTTPError as error:
    assert error.code==400
    assert json.load(error)['error']=='invalid_ignored_region'
print('Live Java upload rejects invalid regions before analysis')
code='''import cv2,numpy as np,tempfile
from pathlib import Path
from ignored_region import valid_mask
from visual_evidence import _candidate_times
from app import TranscribeRequest
region=dict(x=.75,y=.5,width=.25,height=.5)
assert TranscribeRequest(fileId='fixture',ignoredRegion=region).ignoredRegion==region
for w,h in [(320,180),(180,320)]:
 with tempfile.TemporaryDirectory() as d:
  path=Path(d)/'camera.avi';writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),1,(w,h))
  assert writer.isOpened()
  mask=valid_mask(w,h,region)
  for i in range(8):
   image=np.full((h,w,3),128,np.uint8);image[~mask]=0 if (i//2)%2==0 else 255;writer.write(image)
  writer.release()
  assert len(_candidate_times(path))>1
  assert _candidate_times(path,ignore_region=region)==[6000]
print('Live Python wide and portrait camera filtering passed; no OCR or model calls')
'''
subprocess.run(['docker','exec','-i','videostudy-agent-python-1','python','-B','-'],input=code,text=True,check=True)
query="SELECT version,success FROM flyway_schema_history WHERE version='11'"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
result=subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',command],text=True).strip()
assert result=='11\t1',result
print('Live database V11 migration passed')
