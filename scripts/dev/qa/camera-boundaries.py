"""Offline regression against existing course screenshots; never calls the model."""
from pathlib import Path
import sys,cv2
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'agent-python'))
from auto_region import refine_region
folder=root/'.local/keyframes/65894cb5-9404-4bdd-a10b-a4bdcdd4d5fc'
estimates=(dict(x=.75,y=.75,width=.24,height=.25),dict(x=.73,y=.8,width=.24,height=.2),dict(x=.71,y=.75,width=.18,height=.25))
for name in ('880000.jpg','1750000.jpg','2612000.jpg'):
 image=cv2.imread(str(folder/name))
 if image is None:raise RuntimeError('Existing local course screenshots required')
 corrected=[]
 for region in estimates:
  actual,refined=refine_region(image,region)
  assert refined,(name,region)
  assert abs(actual['x']-.732)<.004 and abs(actual['width']-.154)<.004,(name,actual)
  corrected.append(actual)
 assert max(r['x'] for r in corrected)-min(r['x'] for r in corrected)<.004
 if name=='1750000.jpg':
  h,w=image.shape[:2]
  for r,color in ((estimates[0],(0,0,255)),(corrected[0],(0,180,0))):
   cv2.rectangle(image,(round(r['x']*w),round(r['y']*h)),(round((r['x']+r['width'])*w)-1,round((r['y']+r['height'])*h)-1),color,2)
  output=root/'.local/qa/camera-boundaries.jpg';output.parent.mkdir(parents=True,exist_ok=True);cv2.imwrite(str(output),image)
print('Three real screenshots x three biased estimates recover consistent background borders. No AI calls.')
