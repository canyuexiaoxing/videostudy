# Page Visibility and Content Versions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Use checkbox steps to track work. This document is a draft; writing it does not authorize implementation, deployment, paid model calls or pushing commits.

**Goal:** 减少同页入口碎片，保护遮挡、擦除和重写产生的必要内容版本，再审慎调整代表图。

**Architecture:** 原72%分组不变。独立本地整理层输出可选 `pageCollections`，版本选图按直接来源覆盖检查；前端展示和整课直生成适配分阶段启用，分组汇总的原候选链不改。

**Tech Stack:** Python、OpenCV、NumPy、已有OCR；Java21/Spring Boot、Vue/TypeScript；不新增模型依赖。

**Spec:** [设计说明](../specs/2026-10-17-page-visibility-and-versions.md)

## Global Constraints

- 保持72%默认、原pageGroups、真实frame毫秒ID和原始截图；不改导图语义结构。
- 不新增收费请求、OCR或YOLO推理；不重分析历史；未确认不得部署、提交或推送。
- `PAGE_COLLECTIONS=off|observe|apply`，默认off；首版不新增覆盖补采轮次。
- 每关系最多额外读2张已有图，整课最多16张；超限保留原资料；缓存最多32MiB。
- 本机验收目标：代表图阶段新增p95≤0.5秒，含有限复核≤1.5秒；是目标，不是已测性能。
- 开发脚本放scripts/dev，私有素材/报告放.local；日志只用白名单元数据。

## Review Focus

1. 原组号在补采后变化、源图被替换：输入指纹变化必须失效，禁止恢复陈旧裁减。
2. 最后一图遮挡但同时新增、或无OCR图形变化：不能只保留一个时间点；证据不足保守回退。
3. 模板相同、题号或一个负号改变：相似像素不能成为同页或等价的充分证明。
4. Java更新导图/笔记时丢扩展字段、旧历史字段缺失：字段往返及旧构造器必须兼容。
5. 消费方仍需要原组号：字幕、练习、增量候选和回看不能跟展示编号一起重排。

## 文件职责与接口

以下为拟新增接口，尚未存在；不大规模重构现有模块。

| 文件 | 责任 / 接口 |
|---|---|
| `agent-python/page_versions.py` | 图像/OCR局部特征、可见性、版本选择；`select_versions(member_times, visuals, root, region, *, signal=None, budget=None) -> dict` 返回versions、selectedTimesMs、unresolvedTimesMs、replacementProofs、reasonCodes |
| `agent-python/page_collections.py` | 原组相邻关系、集合契约、缓存/预算；`build_page_collections(pages, visuals, root, region, *, signal=None, mode='off') -> dict` 返回status、collections、metrics；off返回空扩展，不变更输入 |
| `agent-python/page_materials.py` | 只负责直生成适配；`build_material_pages(pages, collections) -> list[dict]` 返回派生页面，保留sourcePageIndices，原输入不变 |
| `desktop/src/pageCollections.ts` | 新契约校验与画廊投影；`galleryPages(rawPages, collections) -> GalleryPage[]`，无效或缺失扩展回退原组 |

新字段类型按spec第4节固定；集合判定不调用模型，不把数值指标当成数学语义证明。

### Task 1: 原组不可变与集合契约

**Files:** Create `agent-python/page_collections.py`、`agent-python/test_page_collections.py`。

**Consumes:** 原PageGroup、VisualEvidence、region和本地文件目录。**Produces:** 经验证的collections、policyVersion/inputFingerprint及回退状态。

- [ ] 先写失败测试：off不变更输入；非连续/不存在原组号拒绝；frame ID必须实际存在；同一输入集合ID稳定；补采/图像/OCR/区域变化失效。
- [ ] 在agent-python运行 `python -m unittest test_page_collections -v`，确认上述接口不存在/行为不符而失败。
- [ ] 实现契约、默认off、指纹与确定性ID；不改slide_grouping._boundary。
- [ ] 重跑测试通过；再核对所有输入深拷贝前后相等。

### Task 2: 版本保护与末帧遮挡

**Files:** Create `agent-python/page_versions.py`、`agent-python/test_page_versions.py`；extend Task 1 tests。

**Consumes:** Task 1中的真实帧与区域。**Produces:** select_versions结果和仅含可核验来源的replacementProofs。

- [ ] 先写失败测试：后图补全、后图遮挡、遮挡同时新增、模糊、红黑批注、擦除重写、最终答案、正负号/数字/上下标修改、无OCR图形和低置信OCR。
- [ ] 再加A→B→C非传递例：删A必须直接证明最终选图覆盖A，不能只检查B；OCR失读不能证明擦除。
- [ ] Run `python -m unittest test_page_versions -v`，确认失败；实现局部特征、冲突保护、unknown状态、预算与取消。
- [ ] 实现select_versions：必要时最多读取2张/关系、16张/课；不强制只留一张；没有充分证据时不裁减。
- [ ] 重跑测试通过；测试缓存32MiB限额、来源损坏回退以及取消抛出CancelledError。

### Task 3: 相邻同页集合与安全回退

**Files:** Modify `agent-python/page_collections.py`、`agent-python/model_diagnostics.py`；extend both test modules。

**Consumes:** Task 2的版本结果。**Produces:** spec中的duplicate/extension/revision/new_page/uncertain关系及完整集合。

- [ ] 写失败用例：跨6分钟同页、多模板不同题干、区域时间节点变化；标题相同不足以合并；revision保留不同版本。
- [ ] 写预算超限整批回退与中途取消测试，不能发布只裁减一半的集合。
- [ ] 实现相邻候选和明确关系；65%/97%指标仅作为排序信号，已知错误反例必须拒绝删除。
- [ ] 新增page_collection/page_versions白名单阶段和数量/耗时日志；测试日志不含OCR、公式、原图和未知私有字段。
- [ ] Run `python -m unittest test_page_collections test_page_versions test_model_diagnostics -v`，通过后进入链路接入。

### Task 4: 保存、历史与展示，先observe

**Files:** Modify `agent-python/direct_analysis.py`、`agent-python/grouped_analysis.py`；Java `TranscriptionController.java`、必要的 `TranscriptionJobStore.java` / `HttpMediaAnalyzer.java`；create `backend-java/src/test/java/cn/videostudy/api/PageCollectionsTest.java`。Create `desktop/src/pageCollections.ts`、`desktop/src/pageCollections.test.mjs`；modify `desktop/src/App.vue`、`desktop/src/PageGallery.vue`。

**Consumes:** Task 3的collections。**Produces:** 可选result.pageCollections，端到端历史往返和同页画廊。

- [ ] 写Python集成失败测试：off字段可缺失、observe不改变模型图片/请求数；grouped仍消费原分组，补采修订使扩展失效。
- [ ] 写Java序列化、数据库JSON往返、旧字段缺失、withMindMap及笔记更新保留字段的失败测试；保留现有构造器兼容，不默认要求SQL迁移。
- [ ] 写前端测试：集合入口一份、多版本可看、真实时间可跳转、缺图提示、按播放时间定位、旧记录回退、坏扩展不吞原组。
- [ ] 实现元数据传递与画廊投影；不在UI呈现算法内部阈值或把unknown说成已补全。
- [ ] Run前述Python测试、Java21的 `mvn -o test`、`node --test desktop/src/*.test.mjs` 及desktop `npm run build`。
- [ ] 浏览器测试API全部模拟；验证大图、跟随播放、手机布局与历史重开；不发起真实分析。

### Task 5: 直生成图片适配，单独准入

**Files:** Create `agent-python/page_materials.py`、`agent-python/test_page_materials.py`；modify `agent-python/direct_course_map.py`、`agent-python/direct_analysis.py`；extend `test_direct_course_map.py`、`test_map_regeneration.py`。

**Consumes:** 已验证collections；observe仍用原图片。**Produces:** apply模式派生material_pages及真实图片引用注册表。

- [ ] 先测：代表图必须属于派生页成员；sourcePageIndices准确；红/黑批注及最终答案均可注册；collectionId不能成为图片引用。
- [ ] 测试新图列表与hash进入缓存键和导图上下文；重生成不复用旧裁减；原图不能被拼接/覆盖；sourceID和时间由程序产生。
- [ ] 实现build_material_pages：派生页合并真实成员，允许必要多版本，不给非所属旧组硬挂新图；原pageGroups仍用于历史、字幕和练习。
- [ ] apply只有验收后显式配置启用；格式/引用修正仍共享原一次额度，模型请求数量不增加。
- [ ] 用模拟回复跑direct、引用、重生成测试；核对不改course_outline.py、mindMap.ts与例题归并规则。grouped模型链仍不裁减、不换候选ID。

### Task 6: 离线多课程质量与性能验收

**Files:** Create `scripts/dev/qa/page-versions-evaluation.py`；artifacts `.local/qa/page-versions/`；update交接文档。

**Consumes:** 前述函数、已有数据和人工重要区域标注。**Produces:** 质量/时间报告，明确是否允许apply。

- [ ] 先建立私有标注：幂级数08:10推导、23:06与24:12最终答案、18:32/18:48版本；增长量红黑批注与117答案；极限题的换元推导。标注和原图只放.local。
- [ ] 比较原72%、observe、apply，至少3轮交替顺序运行；记录读图/特征/整理耗时、p95、内存缓存峰值、入口与图片数、回退及已标注遗漏。
- [ ] 整课追踪图片，不只比较旧组号。旧增长量作为重复控制，不重复统计独立课程数量。没有真实模型调用就不声称导图质量/云端速度改善。
- [ ] 执行全部Python测试、Java113项及后续新增项、前端测试/构建和模拟浏览器检查；实际数量以当次输出为准。
- [ ] 门槛：已标注关键新增遗漏0、不同题干误合并0、引用可追溯、无新增模型请求、本地预算达标。未达标保持off/observe，不部署裁减。
- [ ] 输出自查和独立代码审查结论；修复重要问题后重新验证受影响项。更新交接；仅在用户后续要求实施/部署时执行，提交和推送另外遵守当时指令。

## 自查与交付状态

本文所有任务均未执行。关系枚举、接口名、result字段和开关与spec一致；5类Review Focus都有对应失败测试；首版不把分组后待核对再送一次覆盖模型。当前离线原型仅作反例和性能参考，不能直接复制为生产删图准则。
