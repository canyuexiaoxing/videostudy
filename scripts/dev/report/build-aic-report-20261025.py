
from pathlib import Path
import json,ast,re,hashlib
from reportlab.pdfgen import canvas
# Reuse verified typography and team-authored diagrams, without executing the old report build.
ROOT=Path(__file__).resolve().parents[3]
old=(ROOT/'scripts/dev/report/build-aic-report.py').read_text(encoding='utf8')
exec(old.split('# Main source and right-boundary')[0])
QA=ROOT/'.local/qa/aic-report-2026-10-25';OUT=ROOT/'cailiao';BODY=json.loads((QA/'body.json').read_text(encoding='utf8'))
ST['p'].fontSize=10.8;ST['p'].leading=18;ST['p'].spaceAfter=8;ST['p'].firstLineIndent=21.6
# Use light gray visible borders for all tables.
orig_tab=tab
def tab(heads,rows,widths=None):
 t=orig_tab(heads,rows,widths);t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.45,colors.HexColor('#D9D9D9'))]));return t
tree=ast.parse(old);resources=None;refs=None
for node in tree.body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='resources' for t in node.targets):resources=ast.literal_eval(node.value)
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REFS' for t in node.targets):refs=ast.literal_eval(node.value)
assert resources and refs
for r in resources:
 r[:]=[v.replace('master 9ff0dc9','当前源码40173c8').replace('截图为空历史实装','不附未授权课程原图').replace('实际配置见资源CSV','版本取自随包二进制') for v in r]
resources[12][3]='团队以AI辅助实现、调试和文档编制，由队长负责开发、两名队员负责测试；采用内容需审阅、验证并核对第三方权利。参与范围已披露。'
resources[13]=['14 课程、图片与测试数据','三类真实课程内部记录；模拟增长率/函数/电路资料；[E2][E3]','真实课程未证明可公开再分发，不随报告提供原视频、声音和整套课件；公开演示另确认授权。','自研测试与统计；不主张第三方课程权利。合成模型测试未发送用户课程，演示授权待确认。']
resources[14]=['15 自主代码与开放成果','源码40173c8；处理模块、桌面、脚本、测试和说明；[R3]','本次未发现根LICENSE；按官方允许方式提供有权提交的成果。项目许可不能覆盖第三方。','开放范围及许可方案待团队确认；代码基线已核对，不能写为全部开源或全部合规。']
import importlib.util as _iu
_rev_spec=_iu.spec_from_file_location('review_revision',ROOT/'scripts/dev/report/report-review-evidence-20261025.py')
_rev=_iu.module_from_spec(_rev_spec);_rev_spec.loader.exec_module(_rev)
_rev.revise_resources(resources)
APP=[]
for i in range(3):
 APP.append({'title':f'附录A 开源及第三方资源使用清单 {i+1}/3','sub':'资源声明、本次源码包范围与后续安装包事项分列','blocks':[
 ['small','版本取自实际环境、锁文件与模型声明。本次仅提交自主源码、配置、文档、测试及自制样例；不含第三方安装依赖、运行库和模型权重。当前状态与后续安装包事项逐项说明。'],
 ['table',['名称与类型','版本与来源','许可与本次包含范围','自主内容、当前状态与后续事项'],resources[i*5:i*5+5],[82,126,137,136]]]})
# Evidence is self-contained enough to explain the measurements; raw logs are not asserted public.
APP.append({'title':'附录B 验证证据与复现说明','sub':'当前离线验证与历史模型样本分开归档','blocks':[
 ['h','B.1 当前验证记录 E1'],
 ['p','本次核查日期2026年10月25日，源码40173c8462cbfeeeb53ff44ebd70111e14c6db04，前端0.3.1。扫描自有代码和测试352个文件，排除虚拟环境与第三方目录；数量仅说明范围，不作为创新评分依据。当前验证没有新增模型调用或修改用户课程。'],
 ['table',['证据','项目内定位与复核方法'],[
 ['E1 离线回归','.local/qa/aic-report-2026-10-25/：desktop、python、java、frontend-typecheck及frontend-build的JSON与日志；复核脚本scripts/dev/report/audit-aic-report-20261025.py。'],
 ['E2 历史课程','docs/录屏参考-五条历史质量与成功耗时-2026-10-21.md；docs/实测耗时对照与录屏引用-2026-10-20.md；对应任务和时间口径保留。'],
 ['E3 真实模型','docs/练习题兼容修复与弹性题量-2026-10-20.md；.local/qa/practice-delivery/synthetic-live-20261020-122936/result.json。只使用模拟材料。'],
 ['E4 代码与依赖','scan.json记录源文件哈希、模块与实际版本。模型revision见.local/native/models-NOTICE.json；完整依赖以各模块锁文件和随包声明为准。']],[95,386]],
 ['h','B.2 运行与核验'],
 ['p','优先运行与报告基线匹配的Windows目录版Framewise.exe，等待本机服务、模型与设备就绪，配置个人可用API，再选择有权使用的课程。查看历史需正确关联本地原视频；没有原视频仍可阅读保存文字资料，图片缺失不能伪装已加载。源码方式使用Java21、Node及独立Python推理环境，SQLite配置与目录见打包脚本。根README含历史部署描述，不能将其旧MySQL与固定端口写法当作当前原生运行前提，发布前应统一说明。'],
 ['small','媒体夹具使用测试FFmpeg的libx264；Java回归复用桌面运行时的JDK Unix-domain回环兼容机制。环境首次失败和复测日志均保留。正式媒体集成、全新机器安装与实际公网同步未在本轮验收。.local证据默认仅本机存在，提交时需提供有权共享的摘要，不能把本机路径当成评委可访问链接。']]})
updated=[]
for row in refs:
 row=list(row);row[2]=row[2].replace('master，9ff0dc9','源码40173c8').replace('9ff0dc9','40173c8');row[3]=row[3].replace('/tree/9ff0dc9','/tree/40173c8');row[2]=row[2].replace('参与范围见4.14节','参与范围见3.3节')
 updated.append(row)
for i in range(2):
 bs=[]
 for ident,title,note,url in updated[i*8:i*8+8]:
  bs.append(['small',f'[{ident}] {title}。{note}\n{url}'])
 APP.append({'title':f'附录C 参考资料与来源链接 {i+1}/2','sub':'官方规则与上游资源入口；具体许可按实际采用版本核对','blocks':bs})
from importlib.util import spec_from_file_location,module_from_spec
extra_spec=spec_from_file_location('technical_appendix',ROOT/'scripts/dev/report/report-technical-appendix-20261025.py')
extra=module_from_spec(extra_spec);extra_spec.loader.exec_module(extra)
APP.extend(extra.technical_appendices())
_rev.apply_appendices(APP)
_original_blocks=blocks
def blocks(spec):
 result=[]
 for item in spec['blocks']:
  if item[0]=='shot':
   im=Image(str(ROOT/item[1]));factor=min(481/im.imageWidth,390/im.imageHeight);im.drawWidth=im.imageWidth*factor;im.drawHeight=im.imageHeight*factor;im.hAlign='CENTER';result.extend([im,para(item[2],'caption')])
  else:result.extend(_original_blocks({'blocks':[item]}))
 return result
W,H=A4
pdf=OUT/'Framewise_AIC技术报告_映知_2026-10-25.pdf';c=canvas.Canvas(str(pdf),pagesize=A4,pageCompression=1)
c.setTitle('Framewise课程循证学习助手技术报告');c.setAuthor('映知');c.setSubject('2026 AIC AI+开源技术报告');c.setCreator('映知 技术报告编制')
c.setFont('Song',11);c.drawCentredString(W/2,H-55,'第八届全球校园人工智能算法精英大赛·算法主题赛')
y=H-150
for t,sz,gap in [('2026 年第八届',20,42),('全球校园人工智能算法精英大赛',20,42),('算法主题赛',20,47),('AI+开源',22,56),('技术报告',30,70)]:
 c.setFont('Hei',sz);c.drawCentredString(W/2,y,t);y-=gap
c.setFont('Hei',18);c.drawCentredString(W/2,y-5,TITLE);y-=79
for label,value in [('团队名称','映知'),('团队编号','AIC-2026-60885194'),('作品名称',TITLE),('参赛方向','开源赋能的AI应用创新'),('日期','2026 年 10 月 25 日')]:
 c.setFont('Song',13);c.drawString(105,y,label+'：');c.drawString(190,y,value);y-=33
c.setFont('Song',9);c.drawCentredString(W/2,61,'正文15页，附录另列。源码核对基线40173c8，前端版本0.3.1。');c.showPage()
# Front contents, chapter starts indexed by body page.
c.setFont('Hei',22);c.drawString(57,H-79,'目录与阅读说明')
c.setFont('Song',10);c.drawString(57,H-108,'正文与附录分别编号：正文1～15页，附录1～14页；以下均为页脚编号。')
rows=[]
for title,start in [('一、作品概述',1),('二、需求分析与总体方案',2),('三、AI技术与开源资源选择',3),('四、设计与实现过程',4),('五、成果展示与效果验证',10),('六、创新性与开放价值',13),('七、合规、安全与风险说明',14),('八、总结与展望',15)]:
 rows.append([title,str(start)])
flow=[tab(['正文章节','正文页码'],rows,[399,82]),Spacer(1,20),para('附录A：第三方资源清单（附录第1～3页）；B：证据与运行说明（第4页）；C：参考资料（第5～6页）；D：关键实现细节（第7～10页）。E：四页真实界面截图（第11～14页）。正文第5页说明五阶段，第15页说明团队分工。'),para('自主代码采用AGPL-3.0-only；评审源码包包含声明、测试摘要与运行说明，不含第三方运行库、用户课程或密钥。截图使用自制课件与预置数据；真实课程与模型抽样分列。成果版本固定为aic-2026-review-20261025-r3标签，访问和下载入口见附录B。')]
Frame(57,90,481,H-225,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0).addFromList(flow,c)
assert not flow
c.showPage()
layout=[]
for i,spec in enumerate(BODY+APP):
 body=i<len(BODY);n=i+1
 c.setFillColor(colors.black);c.setFont('Song',9);c.drawString(57,H-38,'第八届全球校园人工智能算法精英大赛·算法主题赛');c.drawRightString(W-57,H-38,'映知  |  AI+开源')
 c.setStrokeColor(colors.HexColor('#D9D9D9'));c.line(57,H-49,W-57,H-49)
 title=Paragraph(escape(spec['title']),ParagraphStyle('pagetitle',parent=ST['h'],fontSize=15.5,leading=23,spaceBefore=0))
 _,th=title.wrap(481,60);title.drawOn(c,57,H-65-th)
 sub=Paragraph(escape(spec['sub']),ST['small']);_,sh=sub.wrap(481,50);sub.drawOn(c,57,H-99-sh)
 flow=blocks(spec)
 f=Frame(57,61,481,H-190,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0);f.addFromList(flow,c)
 if flow:raise RuntimeError(f'overflow at {i+1} {spec["title"]}, remaining={len(flow)}')
 c.setFont('Song',9);c.setFillColor(colors.HexColor('#555555'));printed=i+1 if body else i-len(BODY)+1;c.drawCentredString(W/2,35,f'- {printed} -' if body else f'- 附{printed} -');c.drawRightString(W-57,35,('正文 '+str(printed)+'/15') if body else '附录 '+str(printed)+'/'+str(len(APP)))
 c.bookmarkPage('body'+str(i+1));c.addOutlineEntry(spec['title'],'body'+str(i+1),level=0,closed=False)
 layout.append({'physicalPage':i+3,'title':spec['title'],'body':body,'printedNumber':printed});c.showPage()
c.save()
# Source stays in QA rather than creating extra submission candidates.
lines=[f'# {TITLE}技术报告\n','团队名称：映知\n\n团队编号：AIC-2026-60885194\n\n参赛方向：开源赋能的AI应用创新\n\n日期：2026-10-25\n']
for spec in BODY+APP:
 lines.append('\n## '+spec['title']+'\n')
 for v in spec['blocks']:
  if v[0]=='h':lines.append('\n### '+v[1]+'\n')
  elif v[0] in ('p','small'):lines.append(v[1]+'\n')
  elif v[0]=='fig':lines.append('['+v[2]+']\n')
  elif v[0]=='table':
   lines+=['| '+' | '.join(v[1])+' |','| '+' | '.join('---' for _ in v[1])+' |']
   lines+=['| '+' | '.join(str(x).replace('\n',' / ') for x in row)+' |' for row in v[2]]
(QA/'report-source.md').write_text('\n'.join(lines),encoding='utf8')
(QA/'report-all-pages.json').write_text(json.dumps(BODY+APP,ensure_ascii=False,indent=2),encoding='utf8')
(QA/'report-layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'pdf':str(pdf),'bodyPages':len(BODY),'appendixPages':len(APP),'totalPages':2+len(BODY)+len(APP),'bytes':pdf.stat().st_size},ensure_ascii=False))
