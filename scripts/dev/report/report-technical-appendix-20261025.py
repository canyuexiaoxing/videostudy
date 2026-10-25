"""Source-grounded implementation details for the AIC report appendix."""
def technical_appendices():
 pages=[]
 def page(title,sub):
  value={'title':title,'sub':sub,'blocks':[]};pages.append(value);return value['blocks']
 def p(b,t):b.append(['p',t])
 def h(b,t):b.append(['h',t])
 def table(b,heads,rows,widths):b.append(['table',heads,rows,widths])
 b=page('附录D 关键实现细节 1/4','D.1 分析调度、时间对齐与中间数据')
 b.append(['fig','pipeline','图D1 默认整课直生成路径。转写与视觉并行，未独立执行页面／组图文理解。'])
 table(b,['数据对象','主要字段与用途'],[
 ['原句 segment','id、startMs、endMs、text；同一ID唯一，开始时间非负且结束不早于开始。'],
 ['视觉证据 visual','frameTimeMs、ocrBlocks；文字块保留text、score、polygon，时间来自实际帧。'],
 ['同页组 page','pageIndex、first/lastFrameTimeMs、memberFrameTimesMs、representativeFrameTimesMs。'],
 ['导图节点 node','title、children、details、sourceIds、imageIds；例题另存examples，落库后形成evidenceRefs。']],[91,390])
 h(b,'D.1.1 取帧与进度不共用时间假设')
 p(b,'frame_stream.py由frame.pts×frame.time_base换算时间，并按容器／流起点归一；采样时不使用“帧号÷固定帧率”推断时间。补采可从前方关键帧向目标解码，再记录实际帧时间；请求时间仅用于核对补采返回。旋转与显示方向在图像转换阶段处理。')
 p(b,'SavedFramePipeline把选帧、原子保存与消费分开，队列容量限制在1～4，满队列等待而不无限积压。进度包含stage、completedStages、completedUnits和totalUnits，通过临时文件替换progress.json；进度只表示阶段与工作单元，不估算剩余秒数。')

 b=page('附录D 关键实现细节 2/4','D.2 人物可见域、同页判定和补采边界')
 h(b,'D.2.1 遮罩与原图绑定')
 p(b,'person_visibility.py把180×320人物布尔遮罩packbits后保存，7200字节位图附带frameTimeMs、原图尺寸、模型SHA-256和图片SHA-256。加载时校验版本、尺寸、模型与图像摘要；损坏或缺失遮罩返回不可用，调用方进入明确回退路径。比较遮罩不改变保存的原始课件图。')
 table(b,['判定条件','当前实现'],[
 ['共同可见域','C=A∩¬(P0∪P1∪Pt)，排除锚帧、前帧和当前帧人物并集；OCR框至少90%在C内。'],
 ['题号冲突','使用高置信可见文字的题号变化作为新页线索；先于同页合并判断。'],
 ['同页文字锚点','置信度至少0.5，标准化文本相同、长度至少6，中心在画面15%～85%；位置IoU至少0.5。'],
 ['合并与待定','当前帧对锚帧及前帧均需至少2个不同文字锚点且总字数至少20；可见域不足35%时待定，待定帧上限8。']],[99,382])
 h(b,'D.2.2 补采针对可解释的文字缺口')
 p(b,'agent_review.py按10分钟窗划分已有视觉证据，前后30秒提供邻接语句，默认最多3窗并发。复核只见ASR/OCR文字；允许请求的原因包括missing_text、evidence_conflict和reasoning_gap，逐项校验有限数值、时间区间和视频边界，并对同一问题附近请求去重。每轮按问题取真实帧，最多两轮；补取后回到OCR与分组，不让模型画出缺失板书。')
 p(b,'无视觉证据时该复核返回not_applicable；这与“已完成全课画面检查”不同。页组仍可保存多个代表时刻，逐步书写不因同页而压成最终答案一张图。这里的阈值反映当前实现，需用人工标注集进一步评价漏页与误拆。')

 b=page('附录D 关键实现细节 3/4','D.3 输出契约、一次修复预算与引用注册表')
 h(b,'D.3.1 首次输出按同一递归契约组织')
 p(b,'课程请求携带完整有效转写、pageContext及最终代表图；图像以original细节发送，忽略区域按任务配置遮蔽，原文件保留。提示明确区分通用知识与具体例题，要求条件、符号、步骤、易错点和自我纠正有证据；空数组写[]，不生成Markdown外壳或多个根对象。json_object模式、非流式响应和输出上限共同配置，但实际能力取决于所用服务。')
 table(b,['验证层','具体规则'],[
 ['响应与JSON','检查finish_reason及完整正文；解析时保留重复键信息，拒绝冲突重复字段与多个不同文档。'],
 ['字段与递归','根需topic、children、examples；节点标题与数组类型检查；记录root.children[i]等精确路径。'],
 ['格式修复','同一请求上下文追加原回复及定位信息；仅修序列化，按节点路径、标题、层级和元数据核对保留。'],
 ['引用修复','未用格式修复预算且问题数在上限内才触发；仅接受指定path/field/index更正及指定无来源节点补引用。']],[88,393])
 p(b,'格式修复与引用修复共用repair_used，一次生成最多追加一次此类修复请求。无法确认内容无损、原样返回或修复后仍不合法，记录具体失败；不会截取首个可解析对象作为完整结果，也不静默移走节点来通过检查。')
 h(b,'D.3.2 来源由程序重建')
 p(b,'course_citations.py将真实截图frame_<毫秒>映射为本次请求的img_1等短句柄，并拒绝与原句ID冲突。模型只选择已给出的编号；返回后映射为真实ID，再由注册表重建原句和时间。编号放错字段但指向唯一真实来源可归类修正，未知或超范围引用拒绝。验证报告写入任务.map-validation；日志只留路径、原因与计数，不复制正文。')

 b=page('附录D 关键实现细节 4/4','D.4 上下文复用、数据一致性与回归定位')
 h(b,'D.4.1 课程学习与按题会话')
 p(b,'map_conversation.py以导图版本、节点结构、引用、模型信息等计算指纹，保存已完成导图的system/user/assistant材料及图片摘要。出题复用时逐图验证文件和SHA-256，再切换练习Schema；限定范围只允许选中知识的来源。课程对话与按题答疑各自保存，按题线程绑定题库、题目及客户端，避免不同题目混用交流记录。')
 p(b,'练习图形接受结构化数据，本地绘制统计、函数、几何与电路图。函数表达式最长160字符、AST最多70节点，只接受白名单变量、运算和单参数函数；数值必须有限，拒绝属性访问和任意代码。KaTeX承担公式排版，独立核算检查数值一致性，二者不混为一项准确性验证。')
 h(b,'D.4.2 检查点与同步事务')
 p(b,'检查点键为SHA-256(版本、任务配置、阶段、输入的规范化JSON)，只有accept判定通过的阶段写入，以临时文件替换实现原子提交。手动重生成不复用旧导图输出。云同步PUT携带expectedRevision，冲突返回409；拉取前核对本地base_hash，再在事务内替换白名单课程表、校验关联并重置运行令牌。媒体文件与IndexedDB笔记不纳入该数据库快照。')
 table(b,['实现模块','已有回归定位（项目内）'],[
 ['媒体与补采','test_frame_stream.py、test_visual_evidence.py、test_agent_review.py'],
 ['分组与引用','test_yolo_slide_grouping.py、test_slide_grouping.py；course JSON／citation系列测试'],
 ['格式及练习','test_course_reply_repair.py、test_practice_reply.py、test_practice_diagrams.py'],
 ['桌面与数据库','desktop/src/*.test.mjs、desktop/electron/*.test.cjs；backend-java/src/test/java']],[106,375])
 p(b,'上述测试覆盖确定性边界和故障行为；报告中的回归数量沿用2026年10月25日E1已归档结果。本次增加技术说明未新增课程处理、付费模型请求或硬件测试，未把文档更新写成新的性能实验。')
 return pages
