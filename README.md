# VideoStudy

课程视频学习与错因诊断系统。目前已打通本地播放器、临时上传、带时间转写、点击原视频回放和 MySQL 任务持久化。画面经粗选、PP-OCRv6 和文字 Agent 补采后，先按时间合并为 PPT 页面，再按用户选择运行两条页面理解路线：文字路线向模型发送同期语音文字＋本页 OCR 文字；图片路线发送同期语音文字＋一张代表图，不附 OCR 文字。只有图片模型判断关键内容被遮挡、语音又未明确补足时，才从同页候选画面中补发一张不同截图。Agent 从转写生成带原句与时间引用、层级可变的思维导图；前端用 [SimpleMindMap](https://github.com/wanglin2/mind-map)（MIT 许可）显示双侧曲线分支，画布可拖动、缩放，点击节点回放本地原视频或录音。截图保存在项目的 `.local/keyframes`，分析成功后删除服务器临时视频。旧任务可用已存转写补生成导图，无需重新上传。多概念关系图和错因诊断尚未实现。

## 本机开发环境

- JDK 21、Maven 3.9.x
- Node.js 22 或更新版本、npm
- Python 3.11 或更新版本（当前演示接口已在 3.13 上验证；后续模型依赖仍计划用 3.11 验证）

本机默认 `java` 可能仍指向 JDK 17。启动 Java 前，在该 PowerShell 窗口设置：

```powershell
$env:JAVA_HOME='D:\soft\OradeJDK\JDK21'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
java -version
```

## 启动（开三个终端）

Python 服务：

```powershell
cd E:\workp\videostudy\agent-python
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Java 服务（另一个已设置 JDK 21 的 PowerShell）：

```powershell
cd E:\workp\videostudy\backend-java
mvn spring-boot:run
```

桌面界面：

```powershell
cd E:\workp\videostudy\desktop
npm install
npm run dev
```

打开 `http://127.0.0.1:5173` 可先在浏览器中联调；需要 Electron 窗口时，再开一个终端运行 `cd E:\workp\videostudy\desktop; npm run electron`。选择本地视频后可直接播放，点击顶部“开始分析”才会临时上传。当前上传上限为 2 GB，可通过服务器的 `MAX_MEDIA_UPLOAD_SIZE` 调整；长视频上传和分析需要足够的临时磁盘空间。默认 `ANALYSIS_MODE=transcription` 只转写；设为 `full` 后，流程依次执行转写、PPT 粗选与 OCR、文字 Agent 复核与有限的 0.5 秒补采、同页分组。上传时可选“语音文字＋OCR 文字”或“语音文字＋每页代表图”；图片路线每页先发 1 张，仅在关键内容被遮挡且语音无法补足时再补 1 张同页截图。两条路线都用时间对齐的语音文字。每次选择写入 MySQL 任务记录，失败重试沿用原选择。结果保存成功后删除临时视频；失败时保留上传文件供重试，超过 24 小时的失败文件由定时任务删除。已有分析可在“已有分析编号”输入任务编号读取，不会重新上传。

全量分析结束后，导图生成器将语音转写按最多 80 段分块，提炼章节和可递归的知识点。叶子知识点必须引用真实转写 ID，上层主题可从子节点继承引用；程序用对应原句和时间重建链接，不接受模型返回的时间。页面标题只作为上下文提示，不作为本轮导图的独立依据。没有音轨或无法取得可靠引用时显示空/失败状态，不伪造节点。已有完成任务可点“从已有转写生成导图”，也可明确点击“重新生成导图”使用新版生成器；此操作会再次调用模型，但不需要重新上传视频。长导图默认聚焦主题，可逐支展开或一键展开全部，没有固定层级上限。关闭页面后重新打开，需要重新选择本地原文件才能播放。同一段 30 分钟课程的 608 段历史转写已用新版生成器实测，得到 8 个章节、144 个节点，最深为第 4 层；课程术语准确率仍需人工抽查。

“历史记录”选项列出当前设备浏览器保存的任务编号、文件名和最近查询到的任务状态；早期通过本机上传的任务会从 `analysisMedia:<任务编号>` 迁入列表。点击记录后，Java 从 MySQL 读取已保存的转写、OCR/页面文字、导图和时间引用；随手笔记仍保存在本机。成功任务的临时原视频已删除，回放必须重新选择本地原文件。点击某条记录的“删除”并确认后，服务器删除该任务的 MySQL 结果、关键截图目录和可能残留的临时上传，客户端删除本机历史、文件关联及以任务编号归属的笔记；电脑上的原视频不会被删除。排队或分析中的任务不可删除。直接清除浏览器数据只会清空本机列表，不会清理服务器。其他任务的截图仍保留，尚未实施统一的截图保留/清理策略。没有登录和任务归属校验，因此历史列表不能跨设备同步，当前开发 API（包括删除接口）也不能直接对外开放。

Java API 默认端口为 18080，Python 为 8000。若端口冲突，可用环境变量 `SERVER_PORT` 和 `AGENT_BASE_URL` 配置 Java；前端的 API 地址目前在 `desktop/src/App.vue` 中固定为 18080。

`visualEvidence` 保留逐帧 OCR 原文字块和时间；`pageGroups` 记录同一 PPT 页的成员帧、代表图、合并后的 OCR 来源，以及按路线保存的 `textAnalysis` 或 `imageAnalysis`。分组先用本地画面与文字判断，疑难边界最多调用 8 次文字 Agent；无法确认时保守拆分。分组用的 OCR 不会附在图片理解请求中。页面模型需列出未解决的语音/画面矛盾及精确计算；程序核对其列出的算式结果，发现冲突时带原证据进行一次模型复核，仍无法消除则标为 `unverified`，不展示错误结论为已完成。这只能发现已列出的计算，不能保证发现所有模型遗漏的事实或数字。页面理解失败时保留 OCR 和截图；补图分析失败时保留首次图片理解结果。前端按页展示，也能展开原始候选帧并跳转原视频。截图由 Java 的 `/api/transcriptions/{任务ID}/frames/{时间毫秒}` 接口读取；MySQL 不存图片二进制。旧任务按原逐帧结果展示，不自动重新分析或补存截图。分组阈值还需用真实课程标注和校准，不能把自动分组当作已验证的准确翻页识别。

## 下载文件的位置

项目的可控下载与缓存尽量留在 `E:\workp\videostudy` 内：

| 内容 | 目录 |
| --- | --- |
| npm 包 | `desktop/node_modules`；npm 下载缓存 `.npm-cache` |
| Maven 依赖 | 复用你已配置的本地仓库 `D:\mytools\mavwwww\mvnrep`；不重复下载到项目内 |
| Python 包 | `agent-python/.venv`；安装命令禁用额外的 pip 下载缓存 |
| Whisper `base`/`small` 与 PP-OCRv6 medium 检测/识别模型 | `.local/models`，容器内为 `/models`；见 [模型资源清单](./docs/模型资源清单.md) |
| Windows FFmpeg Full Build | `.local/tools/ffmpeg-9.0.2-full_build/bin`；见 [工具资源清单](./docs/工具资源清单.md) |

项目内的下载目录已加入 `.gitignore`，不提交到 GitHub。`base` 仍是当前转写使用的型号；已下载 `small`，但一分钟真实课程片段的对比仍把“基期”错读为“机器”，因此尚未切换默认模型。新分析任务使用 PP-OCRv6 medium 识别课程画面，并在结果中记录 OCR 型号；旧任务的 PP-OCRv5 结果保持原样。手写批注与密集表格仍可能有错字。Maven 继续复用电脑上已有的本地仓库；Docker 镜像依赖由 Docker Desktop 管理。

## Docker Compose（Java、Python、MySQL）

先启动 Docker Desktop，确认 `docker version` 能显示 Server 版本。然后在项目根目录执行：

```powershell
cd E:\workp\videostudy
Copy-Item .env.example .env
# 编辑 .env，把两个示例密码换掉
docker compose up --build -d
docker compose ps
```

Java API 仅发布在本机 `http://127.0.0.1:18080`，Python 和 MySQL 只在 Compose 内部网络访问。桌面前端继续在电脑上运行 `npm run dev`；**不放进容器**。模型目录挂载为 `E:\workp\videostudy\.local\models` → Python 容器 `/models`。MySQL 数据放在 Docker 命名卷 `mysql-data`，不会随容器重建消失；转写任务与结果已持久化，课程和固定示例任务仍只在内存里。

检查接口：

```powershell
Invoke-RestMethod http://127.0.0.1:18080/api/health
docker compose logs --tail=50 java-api agent-python
```

此 Compose 文件是本机开发配置。要让其他电脑连接服务器，还需配置 HTTPS、认证、上传限额及持久化；不要直接把当前 18080 端口公开到互联网。

2026-09-27 已在 Docker 中对 `30MIN.mp4` 完成 `full` 模式验证：视频长约 29 分 29 秒、157 MiB；2 秒预览共约 884 帧，粗选 80 张，Agent 另补采 2 张。最终保存 608 段转写和 82 张 OCR 画面，复核状态为完成，服务器临时上传已删除。首次调用因 DeepSeek 默认思考模式耗尽 600 token 而失败；已改用非思考模式并经真实 API 请求验证。当前转写把若干专业词读错，OCR 对手写和密集数字也不稳定；这次验证证明流程可运行，不代表课程内容已达到可直接用于自动诊断的准确度。打开桌面界面后选择本地原视频，在“已有分析编号”填入 `51557229-d873-4a4a-b80e-5d4f21e2d1ae` 可读取本次结果，无需再次上传。

## 验证

### 原文与 AI 字幕

播放器提供「原文字幕 / AI 校正字幕」切换，以及中文、English 和与原文相同三种目标选项。同语言校正尽量保持读音和原句结构；中英互译按语义翻译。字幕保留 Whisper 原始分段 ID 和起止时间，切换不重新播放视频。「语音文字」面板可展开修改前后对照及 OCR 引用。

新上传默认启用，可在高级选项关闭。同页分组完成后，后台独立生成字幕，与页面理解和导图并行，不作为主任务完成的前置条件。尚未生成该语言的历史课程可点击「生成 AI 字幕」，仅使用保存的语音文字及同页 OCR，不上传图片、不重新 OCR、不需要原视频。

原文一直保留。校正会过滤大范围改写、不近音替换、额外语气词及超过一次的实际增删；必要的一字/一词增删要求同页 OCR 支持。通过规则的候选修改再集中做一次语义复核，只能认可或舍弃，不产生新改写。无法校正、部分调用失败时保留对应原文，暂时网络错误自动有限重试。字幕结果和来源文字存 MySQL，删除课程时级联删除。校准不读取原音，因此拼音/英文音码过滤不能证明实际读音，也不能保证纠错准确率，需用人工参考字幕评测。

设计与验证见 [AI 字幕设计](./docs/superpowers/specs/2026-10-03-ai-subtitles-design.md) 和 [AI 字幕验证](./docs/AI字幕验证.md)。

### 课件画面

课件画面按已有同页分组浏览，展示代表图及同组全部截图，支持同组前后切换、缩略图分页、大图查看和对应时间回放。手动浏览会暂停跟随视频分组，点击“跟随播放”可恢复；原图已清理时仍保留时间与回放入口。设计及实测见 [同组截图浏览](./docs/superpowers/specs/2026-10-04-page-gallery.md)。

### AI 解读

学习工作台的“AI 解读”概括视频整体内容，包含一句话概括、摘要、学习目标、重点、易错点和重点回看片段。全部页面理解完成后，用完整语音及页面理解结果与思维导图并行生成，不重复 OCR 或上传图片。详细条目引用真实转写片段，点击时间回看本地视频；旧课程可用保存的材料补生成。失败保留明确状态，解读结果随课程删除。设计及验证见 [AI 解读](./docs/superpowers/specs/2026-10-04-ai-overview.md)。

### AI 时间章节

主分析完成后独立生成按讲解时间排列的 AI 章节，不复用思维导图层级。旧课程读取结果时可补生成，无需重新上传视频；结果存 MySQL，随课程删除。鼠标移入视频显示分段进度条，悬停可看章节名称和时间范围；点击或拖动进度条定位到对应时间，章节目录回到章节开头。章节生成失败不影响现有播放、导图和字幕。设计及实测见 [AI 时间章节与播放器](./docs/superpowers/specs/2026-10-03-ai-chapters-design.md)。

### 分析性能配置

默认采用五项优化：补采检查按 10 分钟窗口最多 3 并发；同一轮汇总补采时间、去重后批量提取；Whisper 与视觉粗选/OCR 并行；一个独立 OCR 进程跨分析任务复用已加载模型；页面理解最多 5 并发，完成后按原页面顺序汇总。同一窗口的复查仍在补图 OCR 完成后进行，最多两轮，不增加全视频截图上限或模型输出 Token 上限。

`.env` 可配置 `REVIEW_CONCURRENCY=3`、`PAGE_CONCURRENCY=5`、`MEDIA_PARALLEL=1`。API 并发参数改为 `1` 可对比串行；CPU/内存较紧张时将 `MEDIA_PARALLEL=0`。修改后重建服务配置。API 请求有有限次数的限流/暂时故障重试，不能保证并发越高越快。

粗选与补采的正式截图都按每批最多 8 个输出启动 FFmpeg，每个时间点单独快速定位，避免从头解码整个视频；8 是资源批大小，不限制 Agent 总共补采多少张。批量中间图片随提取结束删除，正式候选图仍按现有任务目录保存和删除规则处理。

页面理解和补采检查的 API 请求会用列名/数据行表格精简重复字段，重复 OCR 文字共享一份字典并保留各帧时间索引。没有删减对应语音、原始文字或时间；内部结果结构不变。格式重试只附带最近一次错误响应，原始证据仍完整发送。已测量的提图及请求字符数变化见 [性能优化验证](./docs/性能优化验证.md)，这些局部测量不等于整节课的总耗时或 Token 减少比例。

导图分块的模型请求现在自动重试：JSON 解析失败、章节必填字段不合格、响应未正常结束，或限流与暂时网络错误时，单个分块合计最多尝试 3 次（首次加 2 次重试），不重做转写/OCR或已成功的其他分块。格式重试附带最近错误及修复要求，网络错误退避后重试；认证失败等非暂时 HTTP 错误直接报告失败。连续失败则保留其他章节并标记整体 `failed`。日志区分 HTTP 响应 JSON、模型内容 JSON、章节字段校验阶段及具体解析错误位置，不打印密钥。

OCR 进程一次服务一个视频任务，任务结束释放使用权，模型保留到服务退出；不会因跨任务复用混用视频路径。常驻进程会持续占内存，语音与 OCR 并行也会增加 CPU、内存峰值。完整 Python 分析结果增加 `stageTimingsMs`：转写、视觉 OCR、补采检查、页面分组、页面理解、导图与总耗时。并行阶段耗时不能直接相加，当前前端尚未展示这些计时字段。

```powershell
cd E:\workp\videostudy\backend-java
mvn test
cd E:\workp\videostudy\desktop
npm run build
cd E:\workp\videostudy\agent-python
.\.venv\Scripts\python.exe -c "from test_app import test_demo_result_has_clickable_time_and_clear_label, test_transcription_rejects_non_uuid_file_id; test_demo_result_has_clickable_time_and_clear_label(); test_transcription_rejects_non_uuid_file_id()"
```

完整 Python 媒体测试使用已构建的 Docker 镜像及项目内模型：

```powershell
cd E:\workp\videostudy
docker compose run --rm --no-deps -e RUN_MEDIA_INTEGRATION=1 -v E:/workp/videostudy/agent-python:/app agent-python python -m unittest -v test_analysis_integration test_analysis test_slide_grouping test_image_understanding test_agent_review test_visual_evidence test_transcription_media
```

设计与竞赛需求见 [docs](./docs/需求分析.md)。下一阶段应针对真实样本校正专业词、去除重复 OCR、检查漏页，再深化概念关系图与错因诊断。当前语音转写用 faster-whisper 的 PyAV 读取音轨，FFmpeg 用于视觉粗选和按时间补帧；单个真实样本的成功不等于所有课程都不会漏页。
