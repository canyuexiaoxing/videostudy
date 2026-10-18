# Framewise Windows 桌面版

## 本次交付

沿用原界面，Electron38.8.6 / Windows x64 便携版，Framewise.exe 独立窗口，无需启动Vite或浏览器。程序目录和zip路径见.local/releases/latest.json。压缩包约145MiB，解压后保留整个软件目录，双击Framewise.exe。运行时有Framewise名称/图标、原生窗口控制、隐藏菜单（Alt可显示）、单实例聚焦、窗口关闭退出。没有打包丢弃的framewise-preview设计页。

此包包含前端和Electron运行时，不含Java/Python/MySQL/GPU模型。分析服务仍使用本机127.0.0.1:18080，需维持现有后端运行；跨机器完整部署还需另配分析后端。桌面配置目录为Electron Framewise用户数据目录，localStorage和IndexedDB可持久保存，与浏览器网页数据分离，不自动迁移网页版笔记、关联或预览缓存。后端历史课程共用，可读取后重新选择指纹匹配的原视频。

## 实现

app://framewise稳定安全来源，protocol.handle只读取打包dist内已允许扩展名的资源，路径解码后检查，不读取任意本地文件。渲染器保持sandbox/contextIsolation，nodeIntegration关闭；不关闭webSecurity，不把任意网站加载为桌面内容；弹窗默认拒绝。后台新增DesktopCors，只补充app://framewise来源，保留原浏览器来源；不修改导图、AI解读或分析流程。时间轴预览模块照常在桌面端本机持久缓存。

入口desktop/electron/main.cjs，资源路由desktop/electron/assets.cjs，打包脚本scripts/dev/package/framewise-windows.mjs。开发npm --prefix desktop run desktop:dev（先启动Vite）；本地正式界面npm --prefix desktop run desktop；打包npm --prefix desktop run package:win。官方@electron/packager固定20.0.4，复用本机已有Electron zip（.local/dev/electron-cache），无缓存时按固定Electron版本使用官方包下载。构建阶段只复制dist与桌面入口，不携带本地视频、密钥、分析输出和node_modules。

## 验证

原前端88项、桌面路由2项、Java124项通过；类型检查/生产构建通过。实际启动打包Framewise.exe，验证app://framewise加载、后端API200、secureContext、渲染器无Node权限、已保存课程导图和图片、真实本地兼容视频解码定位，以及关闭重开后localStorage/IndexedDB保留。运行检查不创建收费分析任务、不调用模型。复现scripts/dev/qa/framewise-desktop.mjs，日志截图和verification.json在.local/qa/framewise-desktop。

后端已部署新版jar并校验SHA；回退镜像videostudy-java-api:before-framewise-desktop-20261018。打包产物未纳入Git。此版为便携程序，非安装器，也不声称已完成自带分析后端的全栈离线发行。
