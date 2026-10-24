# Framewise 下载官网

独立静态网站，不依赖桌面端、Java、数据库或 Node 服务。此目录是网站源码，安装组件仍在 OBS。

## 本地预览

在项目根目录运行 `python -m http.server 5180 --bind 127.0.0.1 --directory website`，访问 http://127.0.0.1:5180/ 。也可以直接打开 index.html，但 HTTP 预览更接近服务器行为。

## 内容与交互

- 沿用 Framewise 现有品牌图标、浅色与蓝色视觉。
- 三种可切换的学习演示：导图、课程问答、随手笔记；节点和依据按钮可定位左侧的示意讲解时间。
- 演示使用静态教学示例，不会真实调用模型、上传视频或产生 API 费用。页面内标明了示意性质。
- 下载按钮直接指向已验证的 OBS 0.3.1 安装器。没有账户、支付或访问追踪代码。
- 原生平滑锚点、粘性磨砂导航、滚动入场、阅读进度、交互状态反馈；支持 prefers-reduced-motion、键盘 Tab/方向键、无脚本基本下载、手机菜单。
- 明确披露 Windows x64、下载大小、空间要求、AI 服务计费和数据使用边界。

## 打包与华为云 Ubuntu 部署

1. 在项目根目录运行 `python scripts/dev/package/download-site.py`。
2. 将 `.local/releases/2026-10-20-download-website/Framewise-download-website.zip` 传到自己的 Ubuntu 服务器。它只包含 HTML、CSS、JS 与两个品牌资源，不含安装组件和用户资料。
3. 在服务器执行 `sudo apt update`，再执行 `sudo apt install -y nginx unzip`。
4. 执行 `sudo mkdir -p /var/www/framewise`，将 ZIP 解压到该目录。确保 `/var/www/framewise/index.html` 存在，不能再套一层文件夹。
5. 参考 `scripts/dev/deploy/framewise-download.nginx.conf` 创建 Nginx 站点配置。启用站点前检查已有默认站点和监听配置，避免覆盖其他项目。
6. 执行 `sudo nginx -t`，检查通过后执行 `sudo systemctl reload nginx`。在云安全组放行网站所需的 TCP 80 端口；也检查服务器本机防火墙。
7. 使用服务器公网地址验证页面与下载按钮。正式域名确定后，改为该域名的 server_name，并为正式站点配置有效的 HTTPS 证书；域名接入和备案按华为云及适用要求办理。

当前任务只制作并启动本地预览，没有登录、修改服务器或发布外网站点。不要把整个代码仓库、.env 或安装器组件传到网站目录。

## 版本更新

当前版本号和下载链接位于 index.html，搜索 `0.3.1` 和 `Online-Setup.exe` 更新。下载量、展开大小、支持系统应以新的 release-summary.json 为准同步更新，不要覆盖 OBS 已发布的不可变清单。

## 验证

`node scripts/dev/qa/download-site.mjs` 使用本机 Playwright 与 Edge，在 5180 本地服务上验证交互。下载使用模拟附件，不运行安装器。截图和验证结果位于 `.local/qa/download-site/`。Playwright 导入路径是此开发环境现有运行时，其他电脑可改为自己的 playwright 安装。
