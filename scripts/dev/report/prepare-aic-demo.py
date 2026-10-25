"""Create authored teaching images/video and deterministic UI data; no model calls."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import subprocess,json,hashlib,os,shutil,os,shutil,os,shutil
ROOT=Path(__file__).resolve().parents[3];q=ROOT/'.local/qa/aic-open-release-2026-10-25';q.mkdir(exist_ok=True)
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
texts=[
['增长量与增长率','从实际数值到数量关系','基期量：100 件','现期量：120 件','增长量 = 现期量 - 基期量'],
['增长率的计算','沿用课程符号，先求增长量','增长量 = 120 - 100 = 20 件','增长率 = 增长量 / 基期量','20 / 100 = 20%'],
['练习与核对','基期不同，分母也不同','从 80 件增加到 100 件','增长量 = 20 件','增长率 = 20 / 80 = 25%']]
for i,lines in enumerate(texts):
 im=Image.new('RGB',(1280,720),'#f7f9fc');d=ImageDraw.Draw(im)
 d.rectangle((0,0,1280,15),fill='#365cda')
 d.text((74,62),lines[0],font=font(49),fill='#172741')
 d.text((76,142),lines[1],font=font(25),fill='#64758e')
 for j,line in enumerate(lines[2:]):d.text((76,225+j*83),line,font=font(34),fill='#203652')
 for x,val,label in [(850,100,'基期'),(1025,120,'现期')]:
  d.rounded_rectangle((x,550-val*2,x+110,550),radius=10,fill='#4f73e8' if val==120 else '#9eb5f4')
  d.text((x+20,566),label,font=font(23),fill='#50627e')
  d.text((x+24,510-val*2),str(val),font=font(25),fill='#203652')
 d.line((810,552,1195,552),fill='#a7b5cc',width=2)
 d.text((76,658),'Framewise 自制教学样例 · 界面交互核验素材',font=font(20),fill='#7b8ba4')
 im.save(q/f'slide{i}.png')
video=q/'Framewise-demo.mp4'
ff=os.environ.get('FRAMEWISE_FFMPEG') or shutil.which('ffmpeg') or str(ROOT/'.local/tools/ffmpeg-9.0.2-full_build/bin/ffmpeg.exe')
r=subprocess.run([str(ff),'-y','-v','error','-framerate','1/10','-i',str(q/'slide%d.png'),'-t','30','-r','10','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',str(video)],capture_output=True,text=True)
if r.returncode:raise RuntimeError(r.stderr[:300])
raw=video.read_bytes();identity=hashlib.sha256(len(raw).to_bytes(8,'big')+raw[:65536]+raw[max(0,len(raw)-65536):]).hexdigest()
id='00000000-0000-4000-8000-000000000025'
segments=[{'id':f's{i+1}','startMs':i*10000,'endMs':(i+1)*10000,'text':'；'.join(t[2:])} for i,t in enumerate(texts)]
refs=lambda i:[{'sourceType':'transcript','sourceId':f's{i+1}','startMs':i*10000,'endMs':(i+1)*10000,'quote':segments[i]['text']},{'sourceType':'image','sourceId':f'frame_{i*10000}','startMs':i*10000,'endMs':i*10000,'quote':'自制课程截图'}]
def node(n,title,i,children=None,details=None):return {'id':n,'title':title,'startMs':i*10000,'endMs':(i+1)*10000,'evidenceRefs':refs(i),'children':children or [],'details':details or []}
tree=node('root','增长量与增长率',0,[node('n1','增长量',0,details=[node('d1','增长量 = 现期量 - 基期量',0)]),node('n2','增长率',1,details=[node('d2','增长率 = 增长量 / 基期量',1),node('d3','先求增长量，再除以基期量',1)]),node('n3','基期选择',2,details=[node('d4','从80到100的增长率为25%',2)])])
visuals=[{'frameTimeMs':i*10000,'ocrBlocks':[{'text':line,'score':1,'polygon':[[76,225+j*83],[740,225+j*83],[740,275+j*83],[76,275+j*83]]} for j,line in enumerate(t[2:])]} for i,t in enumerate(texts)]
pages=[{'pageIndex':i+1,'firstFrameTimeMs':i*10000,'lastFrameTimeMs':(i+1)*10000,'memberFrameTimesMs':[i*10000],'representativeFrameTimesMs':[i*10000],'decision':'new','decisionReason':'authored demo page','ocrLines':[{'text':x['text'],'sourceFrameTimeMs':i*10000,'sourceBlockIndex':j} for j,x in enumerate(visuals[i]['ocrBlocks'])]} for i in range(3)]
data={'id':id,'status':'completed','result':{'language':'zh','segments':segments,'visualEvidence':visuals,'pageGroups':pages,'mindMap':{'status':'completed','provider':'demo-fixture','modelId':'preloaded-demo-not-model-output','promptVersion':'authored-interface-demo-v1','createdAt':'2026-10-25T00:00:00Z','root':tree,'examples':[]},'review':{'status':'not_applicable','resampledTimesMs':[],'concerns':[]}}}
(q/'ui-fixture.json').write_text(json.dumps({'identity':{'size':len(raw),'fingerprint':identity},'job':data},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'videoBytes':len(raw),'paidModelCalls':0,'fixture':'authored interface demonstration, not end-to-end model result'}))
