"""Attach explicitly scoped human visual review to a completed offline benchmark."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'.local/qa/page-schemes-20261018';path=OUT/'report.json';report=json.loads(path.read_text(encoding='utf-8'))
reviews=[
 {'course':'d517b4f7-58d3-483d-bd9f-a0966341461b','scheme':'threshold65','verdict':'confirmed_missing_known_black_solution','viewed':[890000,1064000,1076000],'finding':'Red explanation is not a substitute for the black 2104-1987=117 computation and answer A; both known black frames are absent.'},
 {'course':'427ff2cd-8534-4f04-bc75-0a275c9e918b','scheme':'dedup93','verdict':'confirmed_missing_final_sum','viewed':[1386000,1452000],'finding':'Old coefficient derivation does not replace final y(x)=exp(-x)+2exp(x) and convergence-domain prompt.'},
 {'course':'d517b4f7-58d3-483d-bd9f-a0966341461b','scheme':'coverage65','verdict':'alternative_source_visually_present','viewed':[890000,908000,1076000],'finding':'908000 retains red annotations and adds black marks; 1076000 retains the black final solution. Missing exact 890000 is not itself content loss.'},
 {'course':'cbacd60e-c271-48b2-9353-2bc88d7c2aec','scheme':'coverage65','verdict':'red_alternative_visually_present','viewed':[888000],'finding':'888000 contains the red annotated explanation. No full-course semantic completeness claim.'},
 {'course':'427ff2cd-8534-4f04-bc75-0a275c9e918b','scheme':'coverage65','verdict':'final_sum_alternative_visually_present','viewed':[1452000,1456000],'finding':'1456000 still shows final sum and convergence-domain prompt, with a different pointer/highlight. Exact checkpoint miss is not content loss.'},
 {'course':'427ff2cd-8534-4f04-bc75-0a275c9e918b','scheme':'new_observe','verdict':'six_merged_collection_endpoints_sampled','viewed':[284000,310000,330000,490000,858000,1128000,1300000,1340000,1822000,1828000,1880000,2252000],'finding':'Sampled endpoints show continued versions of their respective questions; all baseline images retained. Interior frames and all formula symbols not exhaustively annotated.'},
 {'course':'56ac6493-3085-45e2-b9c4-130b583b95d1','scheme':'new_observe','verdict':'one_merged_pair_sampled','viewed':[333000,351000],'finding':'Same question and derivation with changed pointer/highlight; both original frames kept.'},
 {'course':'cbacd60e-c271-48b2-9353-2bc88d7c2aec','scheme':'new_observe','verdict':'one_revision_pair_sampled','viewed':[1612000,1764000],'finding':'Same graph question before and after annotations are cleared; original annotated image is retained.'},
 {'course':'d517b4f7-58d3-483d-bd9f-a0966341461b','scheme':'new_protect','verdict':'redundant_addition_observed','viewed':[1064000,1076000],'finding':'Original and added frames both contain black final calculation. OCR novelty can add visually redundant material.'}
]
report['manual_visual_review']=reviews
report['verification']={'synthetic_tests':28,'all_passed':True,'model_calls':0,'production_code_changed':False,'history_written':False}
for row in report['results']:
 baseline=set(row['schemes']['baseline72']['selected'])
 assert row['baseline_matches_saved'] and row['input_unchanged']
 for name in ('new_observe','new_protect'):
  result=row['schemes'][name];removed=baseline-set(result['selected']);proofs={p['removed']:p['retained'] for p in result['proofs']}
  assert all(t in proofs and proofs[t] in result['selected'] for t in removed)
  assert result['extra_read']<=16 and result['cache_bytes']<=32*1024*1024
  assert all((ROOT/'.local/keyframes'/row['course']/f'{t}.jpg').is_file() for t in result['selected'])
 row['new_baseline_evidence_preserved']=True
report['prototype_limitations']+=['Prototype IDs do not implement full production input fingerprint invalidation.','Only selective manual endpoint review was performed; zero distinct-question merge errors has not been proven.','28 synthetic tests validate this probe, not production cancellation/history/UI or full mathematical coverage.']
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# 同页整理方案离线对照测试（2026-10-18）','','## 结论','','建议优先继续“仅整理展示入口、保留原模型图片”方向。自动补留版本策略产生过多图片，目前不建议接入模型输入；降低分组阈值和宽松代表图去重已有明确漏选反例。','','本次新方案只是离线原型，不是设计方案的完整实现：只完成空间文字锚点＋画面差异的同页候选、保留原代表图、最多16张已有图的OCR差异补留，以及严格相同文件去重。人物遮挡识别、公式语义覆盖、生产回退/取消、完整缓存指纹与端到端保存均未实现。不能称为完整新方案验收。','','## 方法','','- 4份任务、3门独立视频；增长量新旧记录来自同一视频。共358张已有截图。','- 每方案3轮，分组阈值和后处理顺序交替；复用真实区域设置，不重新转写/OCR/YOLO、不调用模型。套接字连接被禁止，缺快照即失败。','- 数值为本机本地分组＋选图耗时中位数，不包含抽帧、转写、OCR、补采或云模型时间；不能推断整课提速。','- 原72%重放4份记录全部与保存分组一致。保留首轮测量，无操作系统冷缓存控制；3轮不足以证明稳定p95。','','## 图片数量与新增耗时','','|方案|增长量新|极限题|增长量旧|幂级数|每份记录新增耗时中位数范围|','|---|---:|---:|---:|---:|---|']
names={'baseline72':'原72%','threshold65':'65%＋原选图','threshold70':'70%＋原选图','coverage65':'65%＋覆盖选图','dedup93':'仅代表图去重93%','dedup97':'仅代表图去重97%','new_observe':'新原型：整理入口、保留原图','new_protect':'新原型：再补留内容版本'}
for key,label in names.items():
 values=[r['schemes'][key] for r in report['results']];lo=min(x['extra_median_s'] for x in values);hi=max(x['extra_median_s'] for x in values)
 lines.append('|'+label+'|'+'|'.join(str(x['image_count']) for x in values)+f'|{lo:.3f}～{hi:.3f}秒|')
lines+=['','新增耗时指分组后的后处理，65%/70%的分组耗时另见完整表；不能用上表新增为0推断总耗时为0。','','## 新原型的入口与时间','','|样本|原入口→候选入口|原图→保留原图版|补留版本后的图数|仅整理新增秒|补留版新增秒|','|---|---|---|---:|---:|---:|']
for row in report['results']:
 b=row['schemes']['baseline72'];a=row['schemes']['new_observe'];p=row['schemes']['new_protect']
 lines.append(f"|{row['label']}|{b['entries']}→{a['entries']}|{b['image_count']}→{a['image_count']}|{p['image_count']}|{a['extra_median_s']:.3f}|{p['extra_median_s']:.3f}|")
lines+=['','补留版保留小图数组约3.30～5.60MiB，这是缓存计数，不是进程峰值内存。本次每课均读取16张候选，仍有34/55/37/55个OCR差异候选未核对；未核对不代表内容确实缺失。这里只记录预算是否超限，没有实现生产超时整批回退。','','## 质量检查','','1. **65%仍漏选黑笔最终计算图。** 增长量新记录未选1064000/1076000ms，旧记录未选1072000ms；70%旧记录同样缺失。已查看红笔与黑笔图：黑笔包含2104−1987=117和A，红笔图不能替代。','2. **93%代表图去重仍漏最终结论。** 幂级数35→31张，最终1452000ms被删除，而保留的1386000ms是旧推导，不含最终和函数与收敛域提示。','3. **97%代表图去重收益有限。** 四份记录分别只减少1张；已知红黑版本和最终答案检查点保留。不能据此保证整课逐符号无遗漏。','4. **覆盖选图原型明显增图。** 23/46/22/56张。精确时间检查有未命中，但本次查看908000/888000ms仍保留红笔内容，1456000ms仍保留最终和函数与收敛域提示，不能把时间替换误报为内容丢失。','5. **新原型保留全部原代表图。** 未发生原图裁减；样例红黑版本、08:10推导、23:06推导、24:12最终答案均保留。这只证明未新增裁减，不证明修复了原72%已有的漏选。','6. **同页合并仅作候选。** 已抽查幂级数6个合并集合的首尾、极限题一对、增长量旧一对，所查画面符合题目持续讲解/版本变化；不是全部成员逐图标注，也未证明所有不同题干误合并为0。','7. **补留版本策略过于敏感。** 以高置信OCR文本差异排候选并补留，图片增至32/37/28/51；增长量1064000与新增1076000ms已目视看到相同黑笔结果，说明OCR差异不等于独有内容。','','## 验证与边界','','- 本次28项合成测试通过：原覆盖7、代表图去重7、新原型契约8、集成6。首次受限临时目录写入失败；改用经审批的项目.local/qa临时目录后通过，未修改算法以隐藏测试失败。','- 报告校验：4份输入未修改；原72%重放一致；新原型保留所有原代表图；选图均指向存在文件；候选读图≤16；小图缓存≤32MiB。','- 新增脚本仅在scripts/dev/qa，报告、对照HTML和拼图仅在.local/qa；未修改业务代码、历史数据、服务或部署；未提交/推送。','- 没有真实生成导图，不能给出导图语义质量、云模型速度、token费用或总显存结论。','','## 下一步建议','','先继续完善同页候选和展示投影，模型输入保留原代表图。版本补留先记录待核对候选，不把OCR变化直接变成新增图片。下一轮建立关键区域标注，再优化增图与重复替代；不要直接启用现有自动补留版。','','## 产物','','- report.json：全部三轮时间、完整选图、区域、来源检查点与人工对照记录。','- summary.md：32行方案/样本完整时间表；Known source checkpoints为精确来源命中，不能当质量得分。']
for row in report['results']:lines.append(f"- [{row['label']}图片对照]({row['course']}.html)")
(OUT/'结论.md').write_text('\n'.join(lines),encoding='utf-8')
index='<meta charset="utf-8"><title>同页方案离线测试</title><h1>同页方案离线测试 · 2026-10-18</h1><p>只读已有资料；无模型调用。新方案为部分实现的离线原型。</p><ul>'+''.join(f'<li><a href="{r["course"]}.html">{r["label"]}图片对照</a></li>' for r in report['results'])+'</ul>'
(OUT/'index.html').write_text(index,encoding='utf-8')
print(json.dumps({'records':len(report['results']),'synthetic_tests':28,'all_baseline_sources_preserved':True,'report':str(OUT/'结论.md')},ensure_ascii=False))
