from pathlib import Path
stage=Path(__file__).parent
s=(stage/'knowledge-role-deploy.py').read_text().split("p=root/'docs/")[0].replace('knowledge-role-image','teaching-evidence-image')
(stage/'teaching-evidence-deploy.py').write_text(s)
root=Path(r'E:\workp\videostudy')
with (root/'docs/交接-2026-10-10.md').open('a',encoding='utf-8') as f:
 f.write('''

## 补充：真实课程中的例题讲评残留

检查最近课程 v4 结果发现“2017 年同比增长比的是 2016 年”“本题预期结果为整数”等核心叶子仍引用解题讲评；例题范围在数值答案后结束，且 new_knowledge 能绕过区间过滤。v5 改为要求模型按字幕用途输出 teachingSourceIds/exampleSourceIds，覆盖题目条件、计算、答案检查和后续讲评。核心节点必须引用已分类的独立讲解字幕；节点级新增知识标记不能单独绕过过滤。同一字幕冲突时优先归例题，未知ID忽略。例题结束引用延伸至同一块后续讲评，补充12段前文和8段后文作为跨块边界背景，不能用背景作引用。生产响应缺少分类数组时自动修复，最多既有3次；缓存政策版本 grounded-mind-map-v5-teaching-evidence。Python192项（191通过1跳过）；未调用付费模型，真实课堂的用途分类准确率待新生成结果检查。已有课程需手动重新生成导图才应用，原结果没有批量修改。
''')
