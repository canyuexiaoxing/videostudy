# Framewise 参赛运行与核验说明

本包是基于源码40173c8462cbfeeeb53ff44ebd70111e14c6db04的2026-10-25参赛快照，
另含AGPL授权、声明随包修正、核验文档和自制演示。逐文件SHA-256见包根SOURCE_MANIFEST.json。
不是旧安装包的原样源码快照；许可证和打包声明的后续修改已由清单单独固定。

## 1. 成果与许可

自主代码采用AGPL-3.0-only，完整文本见根LICENSE；NOTICE与THIRD_PARTY_NOTICES.md说明第三方边界。
源码包不含安装运行库、模型权重、FFmpeg、CUDA/cuDNN、用户视频、数据库、密钥或Git历史。
调用第三方依赖时仍须遵守原许可证。旧OBS安装器另属二进制分发，本包不替它作完整许可认证。

固定参赛版本：
https://github.com/canyuexiaoxing/videostudy/tree/aic-2026-review-20261025-r4

标签内cailiao目录提供最新版技术报告与源码核验ZIP；本目录提供运行说明、测试摘要和自制界面样例。
把固定标签地址填入作品其他材料链接。评审期保持可访问；有条件时另备一份网盘或OBS镜像。
现有旧OBS安装器是单独的二进制发布，不纳入本源码材料的完整许可结论。
源码包本身可离线解压阅读，代码无需先启动服务器才能核验。

## 2. 最短核验路径

1. 解压源码包，先阅读LICENSE、NOTICE与本说明。
2. 查看本目录四张实际界面截图及interface-verification.json。
3. 阅读test-summary.json与五份test-*.log，核对207桌面、696 Python通过/1跳过、163 Java通过及前端构建。
4. 查阅model-synthetic-summary.json，区分历史真实API抽样与本次预置数据界面验证。
5. 对照agent-python/direct_analysis.py、course_reply_repair.py、course_citations.py及desktop/src/查看实现。
6. 需要亲自操作时使用下面的源码启动方式；完整AI分析需要用户自己的模型资源、FFmpeg与API配置。

截图的课件文字、数值、柱图由团队制作；导图与练习是确定性预置样例。
截图来自实际运行的Vue组件，验证框选、节点跳转和作答反馈，不冒充真实模型端到端结果或准确率测量。
真实课程历史只提供报告中的汇总统计，不随包分发第三方原视频、声音和整套课件。

## 3. 前端与数据库服务（源码）

环境：Windows x64、Node.js 22或更新、npm、JDK21、Maven3.9、Python3.11及FFmpeg。
先在根目录打开终端，按需创建自己的环境变量；不要把密钥写进源码。

前端（从desktop目录）：
    npm ci
    npm run build
    npm run dev

在浏览器打开http://127.0.0.1:5173。浏览器开发入口本机Java默认为18080，Python默认为8000。
原生Electron由运行监督器动态选择端口，二者不可混作同一套固定端口设置。

Java（从backend-java目录）：
    mvn spring-boot:run -Dspring-boot.run.profiles=sqlite

默认SQLite位于项目.local/database/framewise.db，可用SQLITE_PATH改到独立核验目录。
临时媒体和课件可用MEDIA_TEMP_DIR、KEYFRAME_DIR指定；SERVER_PORT和AGENT_BASE_URL设置Java与Python地址。
本机源码运行不要求Docker或MySQL。可选同步服务另配SYNC_SERVER_URL和SYNC_TOKEN，不是启动前提。
默认ANALYSIS_MODE=transcription；完整流程需ANALYSIS_MODE=full。

Python（从agent-python目录）：
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000

requirements.txt是通用CPU开发路线；Windows GPU与人物分割使用独立环境，见
scripts/dev/package/native-runtime.py、native-model-catalog.py与agent-python/native_bootstrap.py。
FFmpeg应加入PATH；模型来源和版本以模型目录准备脚本为准，不随本源码包提供。
AI调用使用自己的DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL、DEEPSEEK_MODEL，并确认所选服务支持所需输入。
历史读取、界面预置数据核验和离线单元测试不需要真实付费调用。
检查http://127.0.0.1:18080/api/health；不把本机开发API直接暴露到公网。

## 4. 回归与截图复现

桌面逻辑：node --test desktop/src/*.test.mjs desktop/electron/*.test.cjs
Python逻辑：python -m unittest discover -s agent-python
Java逻辑：backend-java目录执行mvn test
前端：desktop目录执行npm run build

上述命令在具备相应依赖时执行；Java离线测试须已有Maven缓存。
媒体集成测试需显式启用；测试夹具使用支持libx264的FFmpeg，不能用缺少编码器的发行构建替代。
本包保留历史测试摘要，不把换机运行结果预先标为通过。

界面截图核验脚本：
    scripts/dev/report/prepare-aic-demo.py
    scripts/dev/report/capture-aic-demo.mjs

现成自制媒体与数据在本目录assets。脚本要求Pillow、Playwright及Chrome/Chromium。
FRAMEWISE_PLAYWRIGHT_MODULE可指定Playwright的index.mjs；FRAMEWISE_CHROME可指定浏览器；
FRAMEWISE_FFMPEG可指定含libx264的测试FFmpeg。截图写入.local/qa，不接触用户数据库。
capture脚本拦截API为预置样例，禁止外网模型请求；不是在线分析入口。

## 5. 开放和维护

本次开放自主源码、构建脚本、单元测试、资料结构、核验文档和自制交互样例。
使用与修改遵循AGPL，第三方部分遵守各自授权。问题反馈应包含版本、步骤和脱敏日志，
不提交密钥、私人课程或含学校/指导教师信息的评审素材。后续维护沿用版本快照、问题反馈、回归验证和文档更新。

## 历史课程有效耗时

course-effective-timings.json按原始计时保存全流程有效耗时。两条曾失败的记录以原预处理关键路径加最终成功导图请求及校验重建，不冒充一次连续成功的实测；剔除失败与重试等待，原始失败记录仍保留。

## 同类案例对照

course-comparison-evidence.json记录用户留存的两组同课导图与一组百度网盘导图／出题截图，共8张的哈希和可见事实，并关联本项目历史指标、四次模拟出题记录与真实组件交互核验。报告6.2据此说明题型、解法组织与循证学习流程；第三方截图原图不随源码核验包分发。
