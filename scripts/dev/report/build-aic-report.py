from pathlib import Path
import json, re, csv, hashlib, importlib.metadata as md, datetime, subprocess, textwrap
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT,TA_CENTER,TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph,Table,TableStyle,Spacer,Frame,Image,Flowable
ROOT=Path(__file__).resolve().parents[3]; QA=ROOT/'.local/qa/aic-report';OUT=ROOT/'cailiao';OUT.mkdir(exist_ok=True)
BODY=json.loads((QA/'report-content.json').read_text(encoding='utf8'))
TITLE='Framewise课程循证学习助手'; assert len(TITLE)<=20
pdfmetrics.registerFont(TTFont('Song','C:/Windows/Fonts/simsun.ttc',subfontIndex=0))
pdfmetrics.registerFont(TTFont('Hei','C:/Windows/Fonts/simhei.ttf'))
ST={
 'p':ParagraphStyle('p',fontName='Song',fontSize=11,leading=18.5,firstLineIndent=22,spaceAfter=9,wordWrap='CJK',alignment=TA_JUSTIFY,textColor=colors.black),
 'h':ParagraphStyle('h',fontName='Hei',fontSize=12.5,leading=21,spaceBefore=5,spaceAfter=7,textColor=colors.black,wordWrap='CJK'),
 'cell':ParagraphStyle('cell',fontName='Song',fontSize=9,leading=13,wordWrap='CJK',textColor=colors.black),
 'th':ParagraphStyle('th',fontName='Hei',fontSize=9,leading=13,wordWrap='CJK',textColor=colors.black),
 'caption':ParagraphStyle('caption',fontName='Song',fontSize=9,leading=14,alignment=TA_CENTER,spaceBefore=5,spaceAfter=10,textColor=colors.HexColor('#444444'),wordWrap='CJK'),
 'small':ParagraphStyle('small',fontName='Song',fontSize=9.2,leading=14.5,spaceAfter=7,wordWrap='CJK'),
}
def para(t,style='p'):return Paragraph(escape(t).replace('\n','<br/>'),ST[style])
def tab(heads,rows,widths=None):
 widths=widths or [481/len(heads)]*len(heads)
 cells=[[para(str(v),'th' if i==0 else 'cell') for v in row] for i,row in enumerate([heads]+rows)]
 t=Table(cells,colWidths=widths,hAlign='LEFT',repeatRows=1)
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf0f3')),('GRID',(0,0),(-1,-1),.45,colors.HexColor('#bfc3c9')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
 return t
class Diagram(Flowable):
 def __init__(self,kind):super().__init__();self.kind=kind;self.width=481;self.height={'architecture':205,'pipeline':150,'visibility':165}.get(kind,130)
 def draw(self):
  c=self.canv;ink=colors.HexColor('#21324a');line=colors.HexColor('#8292a5');blue=colors.HexColor('#eaf0f8')
  def txt(x,y,t,size=10,font='Hei',center=False):
   c.setFillColor(ink);c.setFont(font,size);(c.drawCentredString if center else c.drawString)(x,y,t)
  def box(x,y,w,h,lines,fill=blue):
   c.setFillColor(fill);c.setStrokeColor(line);c.roundRect(x,y,w,h,5,fill=1,stroke=1)
   for i,t in enumerate(lines):txt(x+w/2,y+h/2+(len(lines)-1)*7-i*14,t,9.5,center=True)
  def arrow(x,y,xx,yy):
   c.setStrokeColor(line);c.setLineWidth(1);c.line(x,y,xx,yy)
   import math
   a=math.atan2(yy-y,xx-x);s=5;c.line(xx,yy,xx-s*math.cos(a-.45),yy-s*math.sin(a-.45));c.line(xx,yy,xx-s*math.cos(a+.45),yy-s*math.sin(a+.45))
  if self.kind=='architecture':
   c.setStrokeColor(line);c.setDash(4,3);c.roundRect(1,4,345,195,6,stroke=1);c.setDash();txt(12,184,'用户本机边界',10)
   box(14,120,135,48,['Electron / Vue','播放器、工作台与笔记'])
   box(183,120,148,48,['Java 本机API','任务、引用与SQLite'])
   box(183,37,148,52,['独立Python运行时','ASR / OCR / 可选YOLO'])
   box(14,37,135,52,['本地存储','原视频、截图、模型、笔记'])
   arrow(149,144,183,144);arrow(257,120,257,89);arrow(183,62,149,62);arrow(81,89,81,120)
   box(365,120,114,48,['可选云同步','课程快照 / MySQL'],colors.HexColor('#f2f3f5'))
   c.setDash(3,3);arrow(331,144,365,144);c.setDash();txt(361,102,'非本地分析必需',8,font='Song')
   box(365,37,114,52,['远程模型API','导图、问答、练习'])
   arrow(331,63,365,63);txt(360,17,'发送相应文字与代表图',8,font='Song')
  elif self.kind=='pipeline':
   box(0,56,74,46,['本地视频','任务与指纹']);box(107,95,114,42,['转写','时间＋原句ID']);box(107,16,114,48,['采样、OCR','区域与人物遮罩']);arrow(74,79,107,116);arrow(74,79,107,40)
   box(254,56,103,46,['覆盖复核与补采','同页与代表图']);arrow(221,116,254,80);arrow(221,40,254,80)
   box(387,56,94,46,['整课导图','结构＋证据校验']);arrow(357,79,387,79)
   txt(107,0,'转写与视觉并行',9,font='Song')
  else:
   for x,label,pers in [(0,'锚帧 / 前帧',True),(167,'当前帧',False)]:
    c.setStrokeColor(line);c.setFillColor(colors.white);c.roundRect(x+3,30,143,108,4,fill=1)
    for j in range(5):
     c.setStrokeColor(colors.HexColor('#a4b5cb'));c.line(x+15,115-j*16,x+130,115-j*16)
    c.setFillColor(colors.HexColor('#c3c8cf'));c.roundRect(x+(12 if pers else 78),37,48,94,10,fill=1,stroke=0)
    txt(x+75,145,label,10,center=True)
   arrow(149,84,166,84)
   c.setStrokeColor(line);c.setFillColor(colors.HexColor('#dcecdf'));c.roundRect(340,30,140,108,4,fill=1)
   c.setFillColor(colors.HexColor('#c3c8cf'));c.rect(341,31,55,106,fill=1,stroke=0);c.rect(426,31,53,106,fill=1,stroke=0)
   for j in range(5):c.setStrokeColor(colors.HexColor('#64846a'));c.line(398,115-j*16,424,115-j*16)
   txt(410,145,'仅中间共同可见位置',10,center=True);arrow(315,84,338,84)
   txt(241,6,'灰色：任一帧的人物遮挡；绿色：共同可见域 C',9,font='Song',center=True)

def blocks(spec):
 out=[]
 for v in spec['blocks']:
  if v[0] in ('p','h','small'):out.append(para(v[1],v[0]))
  elif v[0]=='table':out.extend([tab(v[1],v[2],v[3]),Spacer(1,10)])
  elif v[0]=='fig':
   if v[1]=='interface':
    im=Image(str(QA/'interface.png'));im.drawWidth=300;im.drawHeight=300*1080/1500;im.hAlign='CENTER';out.append(im)
   else:out.append(Diagram(v[1]))
   out.append(para(v[2],'caption'))
 return out

# Main source and right-boundary disclosure. License strings are evidence, not legal approval.
resources=[
 ['01 语音识别程序与权重','faster-whisper 1.2.1；CTranslate2 4.8.3；small权重revision 536b0662742c…；[R4]','程序/模型声明MIT；本地推理，部分随包/模型导入。保留许可证与版权说明；上游依赖分别核验。','自研：时间映射、任务编排与缓存；无自训声明。状态：来源/版本已核对，分发核验待闭环。'],
 ['02 OCR程序与模型','PaddleOCR 3.7.0；PaddlePaddle GPU 3.2.1；PP-OCRv6 medium det/rec；[R5]','软件与模型卡声明Apache-2.0；本地OCR。保留许可/NOTICE并核对修改说明、模型与依赖条款。','自研：候选帧组织、文字证据与分组；无模型训练。模型revision见来源清单。状态：分发待核验。'],
 ['03 人物程序与模型','Ultralytics 8.4.4；yolo26n-seg.pt；assets v8.4.0；[R6]','AGPL-3.0 / Enterprise路径；可选本地分割，运行环境随包。核对对应源码、集成与模型分发义务。','自研：共同可见域选择、遮罩持久化和页判断。未声明购有Enterprise。状态：待许可方案确认。'],
 ['04 推理和图像依赖','Torch 2.6.0+cu126；OpenCV 4.10.0.84；NumPy 1.26.4；PyAV 18.1.0；[R7]','分别有BSD、Apache等许可声明；PyAV/媒体二进制依赖另核。保留许可与随包库声明，不据主包许可覆盖所有库。','自研：解码、帧定位、受限计算与绘图；未修改上游模型。状态：元数据已提取，逐项义务待核。'],
 ['05 媒体工具','FFmpeg BtbN win64-lgpl；N-127650-geceaa54a38；实际配置见资源CSV；[R8]','本机-L声明LGPLv3或以后版本，未启用gpl/nonfree；需核对对应源码及再分发方式，不能只列“免费工具”。','自研：采样/兼容播放调度；第三方FFmpeg不主张自有。状态：分发材料待核。'],
 ['06 Python服务','FastAPI 0.147.0；Uvicorn 0.54.0；[R9]','分别MIT、BSD-3-Clause声明；随运行环境部署。保留许可与版权，依赖分项核验。','自研：分析、问答、练习接口与日志策略。状态：实际版本已核对，分发审查待闭环。'],
 ['07 界面与公式组件','Vue 3.5.43；SimpleMindMap 0.14.0-fix.3；KaTeX 0.19.0；[R10]','均声明MIT；前端集成并打包。保留原版权和许可，不移除第三方署名。','自研：学习工作台、证据跳转、图文笔记和交互。状态：主包版本/声明已核对。'],
 ['08 桌面与开发工具','Electron 38.8.6；Vite 7.3.6；TypeScript 5.9.3；[R11]','Electron/Vite主包MIT，TypeScript Apache-2.0；Chromium等组件分别声明。保留Electron版权和第三方清单。','自研：受控协议、IPC与本机服务管理。状态：主包版本已核对，全部传递组件许可待核。'],
 ['09 Java与服务框架','Temurin OpenJDK 21.0.12.1+1；Spring Boot 3.5.0；[R12]','OpenJDK通常GPLv2＋Classpath Exception，具体发行物以随包声明为准；Spring Boot Apache-2.0。','自研：任务、证据、存储和同步服务；未修改JDK。状态：实际JDK已核对，分发说明待核。'],
 ['10 数据库与驱动','SQLite；sqlite-jdbc 3.49.1.0；Flyway；可选MySQL/Connector-J；[R13]','SQLite本体与JDBC驱动分别核对；Flyway、MySQL驱动按Maven实际版本及许可证执行。不能用SQLite公共领域替代驱动授权。','自研：迁移、结果存储、快照与revision冲突处理。云端可选。状态：直接声明已定位，传递项待核。'],
 ['11 GPU及解释器','CPython运行环境；CUDA运行库12.6.77；cuDNN 9.5.1.17；[R14]','Python及GPU运行库各有独立条款，CUDA/cuDNN不能笼统标为开源MIT。只按允许范围分发。','自研：模块探测、解释器隔离和auto/gpu/cpu策略。状态：版本已提取，再分发许可待核。'],
 ['12 远程模型服务','实际配置模型标识deepseek-flash；DeepSeek兼容API；[R15]','第三方服务条款和数据处理约定；不分发其远程权重。需确认素材处理权限、端点和API适用条件。','自研：材料组织、提示、引用检查和恢复；不声称模型自训。状态：调用记录已核对，服务条款待终核。'],
 ['13 AI辅助开发与创作','Codex等工具；具体会话模型版本不在本仓库固定；[R16]','按实际工具/平台服务条款使用；代码、文档、调试、测试及视觉探索均有AI参与。AI生成不等于全部自有权利。','团队确认需求、审阅行为并测试；未证明每行均经人工权利审计。状态：参与已披露，权利核查待确认。'],
 ['14 课程、图片与测试数据','真实课程内部测试；合成增长率/函数/电路材料；[R3]','第三方课程未证明可公开再分发；本报告仅列汇总数据。合成测试材料来源清晰；界面图为空历史实装。','自研：测试脚本、验证与统计；第三方视频/声音不作自有素材。状态：正式演示授权待确认。'],
 ['15 自主代码与开放成果','master 9ff0dc9；Framewise应用、脚本、测试与技术文档；[R3]','项目根许可证待团队选定并做兼容核查；拟开放有权公开的自主代码/测试/说明，不含密钥和私人课程。','不得覆盖上游权利或未核实AI内容；具体成员分工和权利授权需确认。状态：Git可追溯，正式开放方案待核。'],
]
APP=[]
for index in range(3):
 d={'title':f'附录A  开源及第三方资源使用清单（{index+1}/3）','sub':'资源用途、版本、许可、义务、自主边界与合规状态','blocks':[]}
 d['blocks'].append(('small','清单按官方参考字段合并为四列；“声明已核对”不等于全部许可义务已经履行。完整已安装Python/人物依赖和npm/Maven锁定项另附CSV供核对，未知状态不标为已合规。'))
 d['blocks'].append(('table',['名称及类型','版本 / 来源','使用方式 / 关键许可义务','自主边界 / 合规状态'],resources[index*5:index*5+5],[82,126,137,136]))
 APP.append(d)
REFS=[
 ('R1','赛事规则与报告大纲','AIC·AI+开源竞赛规则及作品提交要求0812；技术报告参考大纲260812；官方附件，2026-08。','https://www.aicomp.cn/tracks/tracks-5/4924.html'),
 ('R2','赛程调整','官方通知，2026-10-10；提交时间以平台及后续通知核对。','https://www.aicomp.cn/notice/notice-3/5435.html'),
 ('R3','项目源码与复核版本','Framewise仓库，master，9ff0dc9；外部评审访问权限需提交前核验。','https://github.com/canyuexiaoxing/videostudy/tree/9ff0dc9'),
 ('R4','语音模型与程序','程序faster-whisper；small权重revision 536b0662742c02347bc0e980a01041f333bce120。','https://github.com/SYSTRAN/faster-whisper\nhttps://huggingface.co/Systran/faster-whisper-small'),
 ('R5','OCR程序及权重','det revision 8e0f56fb2ef86b461d99cfc7ac5c137738985f61；rec revision e5a92bcbc5cc1b494628e458d267778f0704fd7c。','https://github.com/PaddlePaddle/PaddleOCR\nhttps://huggingface.co/PaddlePaddle/PP-OCRv6_medium_det\nhttps://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec'),
 ('R6','人物模型与许可','Ultralytics 8.4.4；模型assets v8.4.0；许可说明单独核对。','https://github.com/ultralytics/ultralytics\nhttps://github.com/ultralytics/assets/releases/tag/v8.4.0\nhttps://www.ultralytics.com/license'),
 ('R7','推理与图像库','PyTorch、OpenCV、NumPy、PyAV官方项目。','https://pytorch.org/\nhttps://opencv.org/\nhttps://numpy.org/\nhttps://github.com/PyAV-Org/PyAV'),
 ('R8','FFmpeg与当前构建来源','当前为BtbN LGPL构建；旧工具记录的gyan Full Build不代替本包版本。','https://ffmpeg.org/legal.html\nhttps://github.com/BtbN/FFmpeg-Builds'),
 ('R9','Python API框架','FastAPI与Uvicorn官方项目。','https://github.com/fastapi/fastapi\nhttps://github.com/Kludex/uvicorn'),
 ('R10','前端、导图与公式','Vue、SimpleMindMap和KaTeX官方项目。','https://github.com/vuejs/core\nhttps://github.com/wanglin2/mind-map\nhttps://github.com/KaTeX/KaTeX'),
 ('R11','桌面与构建工具','Electron、Vite和TypeScript官方项目；Chromium等分别按实际声明核验。','https://github.com/electron/electron\nhttps://github.com/vitejs/vite\nhttps://github.com/microsoft/TypeScript'),
 ('R12','Java运行环境与框架','Temurin、Spring Boot官方项目。','https://adoptium.net/\nhttps://github.com/spring-projects/spring-boot'),
 ('R13','数据与驱动','SQLite、sqlite-jdbc、Flyway与MySQL Connector/J。','https://sqlite.org/copyright.html\nhttps://github.com/xerial/sqlite-jdbc\nhttps://github.com/flyway/flyway\nhttps://github.com/mysql/mysql-connector-j'),
 ('R14','解释器与GPU运行库','Python、CUDA与cuDNN官方许可入口；以实际分发版本为准。','https://docs.python.org/3/license.html\nhttps://docs.nvidia.com/cuda/eula/index.html\nhttps://docs.nvidia.com/deeplearning/cudnn/backend/latest/reference/eula.html'),
 ('R15','远程API服务','DeepSeek API文档；实际服务授权和隐私条款需结合所用账户与端点终核。','https://api-docs.deepseek.com/'),
 ('R16','生成式AI辅助工具','Codex/OpenAI工具使用，参与范围见4.14节；具体服务条款需团队核实。','https://openai.com/policies/terms-of-use/'),
]
for index in range(2):
 d={'title':f'附录B  参考资料与来源链接（{index+1}/2）','sub':'资料核对日期 2026年10月20日；第三方项目权利归原权利人','blocks':[]}
 for tag,name,desc,url in REFS[index*8:index*8+8]:
  d['blocks']+=[('small',f'[{tag}] {name}。{desc}'),('small',url)]
 APP.append(d)
d={'title':'附录C  运行说明与证据索引','sub':'不含访问凭据、原视频与完整课程正文','blocks':[]}
d['blocks'].append(('h','C.1 核验方式'))
d['blocks'].append(('p','优先使用与本报告版本一致的Windows x64目录版，启动Framewise.exe后等待本机服务就绪，在设置中检查模型与设备状态；模型可按清单导入或下载。AI功能需用户自行配置可用API，读取已保存课程无需重新调用模型。目录版、旧安装包和源码构建应分别标识版本，不能混用验收结论。'))
d['blocks'].append(('p','源码运行需Node.js、Java 21、Python与相应推理依赖；前端在desktop执行npm install和npm run dev，Java在backend-java以sqlite profile配置本机数据库、上传和课件目录，Python提供本机分析服务。原生运行目录清单见scripts/dev/package/native-assemble.py。当前根README有旧描述，正式提交前须统一；本附录不将开发者机器路径作为通用运行说明。'))
d['blocks'].append(('table',['证据','项目内定位'],[
 ['核心实现','agent-python/direct_analysis.py、direct_course_map.py、person_grouping.py、slide_grouping.py、practice.py；desktop/electron/；backend-java/src/main/java/'],
 ['回归命令','node --test desktop/src/*.test.mjs desktop/electron/*.test.cjs；python -m unittest discover -s agent-python；backend-java目录执行mvn test；desktop目录执行npm run build'],
 ['合并前回归日志','.local/qa/merge-desktop-tests.log、merge-python-tests.log、merge-java-tests.log、merge-frontend-build.log'],
 ['真实练习结果','.local/qa/practice-delivery/synthetic-live-20261020-122936/result.json；对应测试脚本位于scripts/dev/qa/'],
 ['桌面读取验证','.local/qa/native-delivery/actual-native-read-result.json；scripts/dev/qa/actual-native-read.mjs'],
 ['耗时与任务对应','docs/实测耗时对照与录屏引用-2026-10-20.md；A1 eb940a63、A2 feda6396、B1 5d844c81、B2 41d4c269'],
 ['报告源稿与资源盘点','cailiao中同名Markdown、第三方依赖盘点CSV；生成与核对脚本位于scripts/dev/report/']],[105,376]))
d['blocks'].append(('small','说明：.local为本机验证输出，未随Git自动上传；评审核验时应提供经脱敏、有权展示的必要摘要。报告中的记录存在不等于评委已取得该目录访问权限。用户试用、安装验收、全量人工质量标注未完成，不提供虚构证明。'))
APP.append(d)

W,H=A4
pdf_path=OUT/'Framewise_AIC技术报告_映知_2026-10-20.pdf'
c=canvas.Canvas(str(pdf_path),pagesize=A4,pageCompression=1)
c.setTitle('Framewise课程循证学习助手技术报告');c.setAuthor('映知');c.setSubject('2026 AIC AI+开源 技术报告');c.setCreator('映知 技术报告编制')
# Cover follows the fields and ordering of the official reference.
c.setFont('Song',11);c.drawCentredString(W/2,H-51,'第八届全球校园人工智能算法精英大赛·算法主题赛')
y=H-150
for text,size,gap in [('2026 年第八届',20,44),('全球校园人工智能算法精英大赛',20,44),('算法主题赛',20,51),('AI+开源',22,60),('技术报告',30,72)]:
 c.setFont('Hei',size);c.drawCentredString(W/2,y,text);y-=gap
c.setFont('Hei',18);c.drawCentredString(W/2,y-4,TITLE);y-=78
for label,value in [('团队名称','映知'),('团队编号','AIC-2026-60885194'),('作品名称',TITLE),('参赛方向','开源赋能的AI应用创新'),('日期','2026 年 10 月 20 日')]:
 c.setFont('Song',13);c.drawString(113,y,label+'：');c.drawString(196,y,value);y-=35
c.setFont('Song',9);c.drawCentredString(W/2,62,'正文14页；附录另列。资料与实现基线：master / 9ff0dc9。')
c.showPage()
layout=[]
for i,spec in enumerate(BODY+APP):
 c.setFillColor(colors.black);c.setFont('Song',9);c.drawString(57,H-38,'第八届全球校园人工智能算法精英大赛·算法主题赛')
 c.drawRightString(W-57,H-38,'映知  |  AI+开源')
 c.setStrokeColor(colors.HexColor('#c5c5c5'));c.setLineWidth(.45);c.line(57,H-49,W-57,H-49)
 title=para(spec['title'],'h');title.style=ParagraphStyle('pageTitle',parent=ST['h'],fontSize=16,leading=24,spaceBefore=0,spaceAfter=0)
 tw,th=title.wrap(481,60);title.drawOn(c,57,H-65-th)
 c.setFont('Song',9.5);c.setFillColor(colors.HexColor('#555555'));c.drawString(57,H-104,spec.get('sub',''))
 story=blocks(spec);
 frame=Frame(57,62,481,H-184,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0,showBoundary=0)
 frame.addFromList(story,c)
 if story:raise RuntimeError(f'Page overflow {i+1}: {spec["title"]}; remaining {len(story)} blocks')
 c.setFillColor(colors.HexColor('#555555'));c.setFont('Song',9);c.drawCentredString(W/2,37,f'- {i+1} -')
 c.drawRightString(W-57,37,('正文 '+str(i+1)+'/14') if i<14 else '附录')
 layout.append({'physicalPage':i+2,'title':spec['title'],'body':i<14});c.showPage()
c.save()
# Editable text source, same content, no identity information beyond official cover fields.
mdlines=['# 2026 AIC AI+开源技术报告',f'\n作品名称：{TITLE}\n\n团队名称：映知\n\n团队编号：AIC-2026-60885194\n\n参赛方向：开源赋能的AI应用创新\n\n日期：2026-10-20\n']
for spec in BODY+APP:
 mdlines+=['\n## '+spec['title']+'\n']
 for v in spec['blocks']:
  if v[0]=='h':mdlines+=['\n### '+v[1]+'\n']
  elif v[0] in ('p','small'):mdlines+=[v[1]+'\n']
  elif v[0]=='fig':mdlines+=['['+v[2]+']\n']
  elif v[0]=='table':
   mdlines+=['| '+' | '.join(v[1])+' |','| '+' | '.join(['---']*len(v[1]))+' |']
   mdlines+=['| '+' | '.join(str(x).replace('\n',' / ') for x in row)+' |' for row in v[2]];mdlines+=['']
(OUT/'Framewise_AIC技术报告_可编辑源稿.md').write_text('\n'.join(mdlines),encoding='utf8')
(QA/'page-layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'pdf':str(pdf_path),'bodyPages':len(BODY),'appendixPages':len(APP),'totalPages':1+len(BODY)+len(APP),'bytes':pdf_path.stat().st_size},ensure_ascii=False))
