from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[3]
DOC='docs/aic-review-2026-10-25/'
def revise_resources(resources):
 for row in resources:
  row[3]=row[3].replace('状态：直接声明已定位，传递项待核。','参赛源码不含安装依赖；后续二进制须保留各项声明。').replace('状态：版本已提取，再分发许可待核。','参赛源码不分发解释器或GPU运行库，原安装包另审。')
 resources[2][:]=['03 人物程序与模型','Ultralytics 8.4.4；YOLO26n-seg assets v8.4.0；[R6]','选择AGPL路线；自主代码提供AGPL-3.0-only全文及源码、构建说明。模型和安装包不随源码核验ZIP分发。','自研：共同可见区域比较、延后分组、区域节点。根LICENSE/NOTICE已加入；未购买或主张Enterprise授权。']
 resources[4][:]=['05 媒体工具','原运行时FFmpeg LGPL构建，测试工具另用libx264；[R8]','源码包不带FFmpeg；依赖由使用者另行取得。后续带二进制发布需提供匹配源码/构建信息并履行LGPL相关义务。','自研：PTS取帧、区域筛选与兼容副本。旧OBS安装包未纳入本次源码范围的许可结论。']
 resources[10][:]=['11 GPU及解释器','CPython；CUDA 12.6.77；cuDNN 9.5.1.17；[R14]','CUDA/cuDNN按NVIDIA条款，不归本项目AGPL授权；本包不含DLL、驱动或完整工具包。解释器、运行库另行取得。','自研：设备探测、解释器隔离、GPU/CPU策略。已明确排除二进制再分发；后续安装包单独核对。']
 resources[11][:]=['12 远程模型服务','DeepSeek兼容API；历史配置deepseek-flash；[R15]','服务调用不等于分发权重；实际端点按实际服务方条款。用户自备密钥并拥有输入处理权限，公开AI输出按适用要求标识。','自研：资料组织、提示、引用与恢复。服务适用条款已列；不提供账户密钥，不承诺服务能力或额度。']
 resources[13][:]=['14 课件和测试素材','自制增长率课件、确定性界面样例；历史课程汇总；[E2][E3]','自制文字、数值与图表随包用于操作核验；界面预置数据明确标识。第三方原视频、声音及整套课件不随包公开。','已用自制素材生成四张实际界面图；不把预置导图/练习记为模型实测。历史API抽样另列。']
 resources[14][:]=['15 自主代码与开放成果','基于40173c8的2026-10-25参赛源码快照；[R3]','自主代码AGPL-3.0-only；根LICENSE/NOTICE/THIRD_PARTY_NOTICES.md。源码、测试、构建及说明以逐文件SHA-256固定。','许可选择、声明文件和源码ZIP已落实；未改变第三方许可。成果固定标签aic-2026-review-20261025；公开自主源码与核验ZIP，第三方安装包分发另行核对。']
def apply_appendices(app):
 package=json.loads((ROOT/'.local/qa/aic-open-release-2026-10-25/source-package.json').read_text(encoding='utf8'))
 app[3]={'title':'附录B 成果访问、证据与复核入口','sub':'源码核验包内提供证据；本机私有目录不作为评委入口','blocks':[
 ['p','核心源码基线40173c8462cbfeeeb53ff44ebd70111e14c6db04，另附本次AGPL授权、打包声明修正与自制界面核验材料；包内SOURCE_MANIFEST.json逐文件列出SHA-256。它不是旧安装包的原样快照。'],
 ['small','成果包：'+package['file']+'；SHA-256：'+package['sha256']],
 ['table',['证据','源码包内路径与用途'],[
 ['运行与开放说明',DOC+'README.md；根LICENSE、NOTICE、THIRD_PARTY_NOTICES.md。'],
 ['E1 离线回归',DOC+'test-summary.json、test-desktop.log、test-python.log、test-java.log、test-frontend-typecheck.log、test-frontend-build.log。保留原基线与运行日期。'],
 ['E2 历史课程','正文5.2列出样本条件、处理量与分口径成功时间；不包含课程原片。'],
 ['E3 真实模型',DOC+'model-synthetic-summary.json：历史四次合成文字材料API抽样，日期、返回/保留数量及核算状态。'],
 ['E4 源码与界面','包根SOURCE_MANIFEST.json；'+DOC+'interface-verification.json与assets/。本次许可随包复制回归2项通过。']],[94,387]],
 ['small','固定版本：https://github.com/canyuexiaoxing/videostudy/tree/aic-2026-review-20261025\\n成果下载：从该标签的cailiao目录下载本报告和源码核验ZIP；不要使用仅有本机路径的旧证据入口。'],
 ['p','固定参赛标签包含本次AGPL许可证、第三方声明、测试摘要与运行说明；核心算法基线为40173c8，后续许可与核验文件由源码包清单固定。既有OBS安装器和清单可读取，但本次源码材料不替其完成安装及二进制分发许可验收。'],
 ['p','评委可先离线阅读包内代码、声明、测试摘要和截图，再按README启动源码：Node/npm前端、Java21+SQLite、独立Python和自行取得的FFmpeg/模型。完整AI分析需自己的可用API；离线测试与预置数据界面核验不需付费请求。Windows GPU路线、可选同步与各阶段限制在运行说明中单列。']]}
 for spec in app:
  if spec['title'].startswith('附录C'):
   for block in spec['blocks']:
    if block[0]=='small':
     block[1]=block[1].replace('外部评审访问权限需提交前核验。','2026-10-25仓库及固定提交已可匿名访问；新增许可与核验资料固定在aic-2026-review-20261025标签，见附录B。').replace('具体服务条款需团队核实。','工具参与范围见3.3节；实际适用服务条款按账户与工具核对。')
 shots=[
 ('01-workspace-detail.png','E.1 视频工作台：区域设置','图E1 在真实视频工作台拖动保存分析区域。','使用自制30秒课件，拖动绿色框后界面显示已设置1个时间节点；区域在新分析时生效，已有历史任务不被改写。该图验证区域交互与保存，不演示模型识别结果。'),
 ('02-map-detail.png','E.2 导图画布：知识组织','图E2 实际导图组件显示预置的增长量、增长率和基期选择三个主题。','这是来自实际组件的渲染截图，数据由自制样例预置；用于展示画布布局、缩放与节点操作。端到端课程生成的技术链与既有实测另见正文4.2、4.4及5.2，本图不纳入生成成功率。'),
 ('03-evidence.png','E.3 引用回看：原句与时间','图E3 点击增长率节点后，播放器到达00:10，对应原句同步高亮。','脚本断言播放器currentTime=10秒；文件指纹与样例历史一致，字幕原句和课件为自制内容。验证的是已保存引用如何驱动回看，不据此推断生成内容的语义准确性。'),
 ('04-practice-detail.png','E.4 练习反馈：解析与回看','图E4 选择错误答案后，真实组件展示解析、知识提示和回看入口。','预置题从100增加到120，正确增长率为20%；选择10%后显示错误反馈，并提供00:10～00:20讲解入口。题目、解析和引用为确定性样例，未调用付费模型。')]
 for i,(file,title,caption,paragraph) in enumerate(shots):
  app.append({'title':'附录E 实际界面与操作核验 '+str(i+1)+'/4','sub':title,'blocks':[
   ['small','素材与数据：团队自制课件＋预置演示结果；实际运行Vue界面。用于操作核验，非真实模型端到端效果测量。'],
   ['shot',DOC+'assets/'+file,caption],
   ['p',paragraph],
   ['small','复核脚本：scripts/dev/report/capture-aic-demo.mjs；结果与完整截图随源码核验包提供。无外网模型请求，无用户数据库写入。']]})
