"""Repeat timed offline candidates and write a readable experiment report."""
import importlib.util,json,time,statistics,html
from pathlib import Path
spec=importlib.util.spec_from_file_location('probe',Path(__file__).with_name('grouping-coverage-probe.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
out=m.ROOT/'.local/qa/grouping-coverage-20261017';report=json.loads((out/'report.json').read_text(encoding='utf-8'));course=report['course'];value=json.loads((out/f'{course}.json').read_text(encoding='utf-8'));folder=m.ROOT/'.local/keyframes'/course
runs={k:[] for k in ('baseline72','threshold65','coverage65')}
for trial in range(3):
 for name in (('baseline72','threshold65','coverage65') if trial%2==0 else ('coverage65','threshold65','baseline72')):
  start=time.perf_counter();pages=m.groups(value['visualEvidence'],folder,value['segments'],.72 if name=='baseline72' else .65);group_s=time.perf_counter()-start
  if name=='coverage65':
   f=m.Features(value['visualEvidence'],folder);selected=[f.select(p['memberFrameTimesMs'],.93,.5) for p in pages]
  else:selected=[p['representativeFrameTimesMs'] for p in pages]
  runs[name].append(dict(group_s=group_s,total_s=time.perf_counter()-start,groups=len(pages),representatives=sum(map(len,selected))))
summary={k:dict(groups=v[0]['groups'],representatives=v[0]['representatives'],median_s=statistics.median(x['total_s'] for x in v),min_s=min(x['total_s'] for x in v),max_s=max(x['total_s'] for x in v),samples=v) for k,v in runs.items()}
(out/'timing-final.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
# Direct tracing: frame 490000 survives in another group; old groups may split as well as merge.
new=next(x for x in report['results'] if x['threshold']==.65)['pages'];selected=set(t for p in new for t in p['representativeFrameTimesMs'])
assert {310000,490000,1112000}<=selected
lines=['# 同页分组离线测试（2026-10-17）','','范围：38分10秒课程，109张已有截图和OCR；不重做粗选、OCR、ASR，不调用远程模型，不修改正式默认值。','', '| 方案 | 页组数 | 代表图数 | 本地中位耗时 | 3轮范围 |','|---|---:|---:|---:|---:|']
labels={'baseline72':'原72%＋原选图','threshold65':'65%＋原选图','coverage65':'65%＋保守覆盖原型（93%/50%）'}
for k,v in summary.items():lines.append(f"| {labels[k]} | {v['groups']} | {v['representatives']} | {v['median_s']:.3f}s | {v['min_s']:.3f}–{v['max_s']:.3f}s |")
lines+=['','以上仅本地分组、选图阶段，含读取图片及新增特征提取；不是整课分析时间。图片变多可能增加后续模型输入与耗时，未进行付费调用，不能据此给出模型时延。','','## 阈值扫描','', '| 阈值 | 页组数 | 原选图数量 |','|---|---:|---:|']
for x in report['results']:lines.append(f"| {x['threshold']:.0%} | {x['groups']} | {x['old_representatives']} |")
lines+=['','## 质量复核','','- 原5–7组：65%入选05:10，主要内容完整；覆盖原型还保留04:48，存在保守冗余。','- 原9–10组：新组的06:00和下一组的08:10均入选。此前“08:10遗漏”是只检查一个合并组导致的错误结论，已更正；全课未丢该代表图。','- 原14–19组：65%入选18:32最终推导。16:28/16:52有后面不再显示的下标标记和过渡写法，不能宣称前图所有内容都被覆盖。保守原型多留中间图，但目前有明显冗余。','- 60%/62%：27组，比65%多合并一处；这门课样本不足以认定其更优。','- 7项合成边界测试通过：新增、擦除、正负号变化、数字变化、相同内容、弱OCR、非传递覆盖。只说明这些用例通过，不代表真实公式不遗漏。','','## 结论','','65%可作为此类公式课的分组候选值；不能称为通用最优。当前覆盖原型未达到同时少图和保内容的目标，不建议接入默认流程。固定坐标视觉覆盖、OCR可靠性、人物遮挡与高亮处理仍有限制，无OCR图形未实现完整保障。正式分组及导图逻辑保持原样。']
(out/'结论.md').write_text('\n'.join(lines),encoding='utf-8')
parts=['<!doctype html><meta charset="utf-8"><title>65%代表图核对</title><style>body{font:16px sans-serif;max-width:1500px;margin:auto}section{border-top:1px solid #aaa}img{max-width:48%;height:auto;margin:5px}h2{color:#254db4}</style><h1>65%离线结果：实际入选代表图</h1><p>实验结果，未修改正式任务。按整个课程追踪，而非仅按原组号判断。</p>']
for p in new:
 if any(t in p['memberFrameTimesMs'] for t in [284000,310000,330000,490000,858000,1112000]):
  parts.append(f"<section><h2>新组{p['pageIndex']}：{p['firstFrameTimeMs']/1000:.0f}–{p['lastFrameTimeMs']/1000:.0f}秒</h2>")
  for t in p['representativeFrameTimesMs']:parts.append(f'<p>{t/1000:.0f}秒</p><img src="../../keyframes/{course}/{t}.jpg">')
  parts.append('</section>')
(out/'review.html').write_text(''.join(parts),encoding='utf-8');print(json.dumps(summary));print(str(out/'结论.md'))
