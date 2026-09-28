# VideoStudy

课程视频学习与错因诊断系统。目前已打通本地播放器、临时上传、带时间转写、点击原视频回放和 MySQL 任务持久化。画面经粗选、PP-OCRv6 和文字 Agent 补采后，先按时间合并为 PPT 页面，再按用户选择运行 OCR-only 或 OCR＋图片理解；图片路线只向 DeepSeek 发送每页代表截图，保留全部候选帧作回看依据。截图保存在项目的 `.local/keyframes`，分析成功后删除服务器临时视频。旧任务仍可读取。新分组已通过合成视频集成测试，29 分钟原视频尚未用新版图片路线完整复测。示例知识节点仍是固定数据；**真实知识图和错因诊断尚未实现**。

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

打开 `http://127.0.0.1:5173` 可先在浏览器中联调；需要 Electron 窗口时，再开一个终端运行 `cd E:\workp\videostudy\desktop; npm run electron`。选择本地视频后可直接播放。当前上传上限为 2 GB，可通过服务器的 `MAX_MEDIA_UPLOAD_SIZE` 调整；长视频上传和分析需要足够的临时磁盘空间。默认 `ANALYSIS_MODE=transcription` 只转写；设为 `full` 后，流程依次执行转写、PPT 粗选与 OCR、文字 Agent 复核与有限的 0.5 秒补采、同页分组。上传时可选“只用 OCR 文字”或“OCR＋图片理解”；后者只发送每页 1 张代表图，擦除前后内容互补时最多 2 张。每次选择写入 MySQL 任务记录，失败重试沿用原选择。结果保存成功后删除临时视频；失败时保留上传文件供重试，超过 24 小时的失败文件由定时任务删除。另一个“运行接口演示”按钮仍只返回固定示例节点。

Java API 默认端口为 18080，Python 为 8000。若端口冲突，可用环境变量 `SERVER_PORT` 和 `AGENT_BASE_URL` 配置 Java；前端的 API 地址目前在 `desktop/src/App.vue` 中固定为 18080。

`visualEvidence` 保留逐帧 OCR 原文字块和时间；`pageGroups` 记录同一 PPT 页的成员帧、代表图、合并后的 OCR 来源及可选的图片理解。分组先用本地画面与文字判断，疑难边界最多调用 8 次文字 Agent；无法确认时保守拆分。图片模型返回无效格式会重试，仍无法解析或服务超时时标记该页图片理解失败，保留 OCR 和截图。前端按页展示，也能展开原始候选帧并跳转原视频。截图由 Java 的 `/api/transcriptions/{任务ID}/frames/{时间毫秒}` 接口读取；MySQL 不存图片二进制。旧任务按原逐帧结果展示，不自动重新分析或补存截图。分组阈值还需用真实课程标注和校准，不能把自动分组当作已验证的准确翻页识别。

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

设计与竞赛需求见 [docs](./docs/需求分析.md)。下一阶段应针对真实样本校正专业词、去除重复 OCR、检查漏页，再实现真实知识图与错因诊断。当前语音转写用 faster-whisper 的 PyAV 读取音轨，FFmpeg 用于视觉粗选和按时间补帧；单个真实样本的成功不等于所有课程都不会漏页。
