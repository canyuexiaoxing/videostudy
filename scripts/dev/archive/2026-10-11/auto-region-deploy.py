from pathlib import Path
import subprocess,time,urllib.request,json
root=Path('E:/workp/videostudy');stage=Path(__file__).parent/'auto-region-images'
def run(args):subprocess.run(args,cwd=root,check=True)
query="SELECT COUNT(*) FROM transcription_jobs WHERE status IN ('queued','processing')"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
active=subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',command],text=True).strip()
if active!='0':raise RuntimeError('当前分析任务运行中，不能重启:'+active)
for name in ('python','java'):(stage/name).mkdir(parents=True,exist_ok=True)
for name in ('app.py','auto_region.py'):(stage/'python'/name).write_bytes((root/'agent-python'/name).read_bytes())
(stage/'python/Dockerfile').write_text('FROM videostudy-agent-python:latest\nCOPY app.py auto_region.py /app/\n')
(stage/'java/app.jar').write_bytes((root/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar').read_bytes())
(stage/'java/Dockerfile').write_text('FROM videostudy-java-api:latest\nCOPY app.jar /app/app.jar\n')
for name,tag in (('python','videostudy-agent-python'),('java','videostudy-java-api')):run(['docker','build','--pull=false','-t',tag,str(stage/name)])
run(['docker','compose','-f','compose.yaml','-f','compose.gpu.yaml','up','-d','--no-build','--no-deps','agent-python','java-api'])
for attempt in range(20):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18080/api/health',timeout=2) as reply:assert json.load(reply)['status']=='ok'
  break
 except Exception:
  if attempt==19:raise
  time.sleep(1)
print('Local Java health passed')
plan=root/'docs/superpowers/plans/2026-10-11-auto-region.md';plan.write_text(plan.read_text(encoding='utf-8').replace('- [ ]','- [x]'),encoding='utf-8')
with (root/'docs/交接-2026-10-10.md').open('a',encoding='utf-8') as out:out.write('''

## 2026-10-11：四点递归 AI 自动框选

- 用户确认并授权：起始取开头、1/3、2/3、结尾4帧，只对位置/大小/存在状态变化区间递归取中点，到30秒以内停止；切换点为区间中点估计。相同端点间短暂移动后返回可能漏检。
- 视频工作台增加“AI 扫描全片”，展示实际识别帧数、取消、候选结果和应用/放弃。候选区域在视频和节点列表预览，应用前不修改原设置；应用后复用忽略区域时间节点存储与分析链路。
- desktop/src/autoRegionScan.ts 为纯扫描算法：结果按时间缓存，最多64帧，判断使用IoU和坐标差，防止小幅位移累积丢失；未知/达到上限区间明确标记并暂不忽略。取消、关闭、换文件忽略迟到回复。
- regionCapture.ts 用独立视频元素读取本地/兼容副本，长边960pxJPEG；兼容视频设置crossOrigin anonymous，扫描不改变可见播放位置。只发送截图，不上传整片；每批最多4帧。
- Java /api/video-region-detections 转发Python，限制批大小、时刻、重复帧、图像字符串长度、并发与超时。Python auto_region.py 校验JPEG尺寸后解码重编码，复用DEEPSEEK_BASE_URL/MODEL/API_KEY视觉配置；模型只输出detected/absent/uncertain与完整独立摄像头窗口框，时刻始终绑定请求，排除物理手、笔、课件。不部署新模型。
- 验证：前端51项通过，Python211项（210通过、1跳过），Java87项通过，生产构建通过。真实短视频取4帧+模拟检测结果的浏览器流程、跨域HTTP兼容视频截图通过；预览、应用、取消/迟到、关闭、失败保留设置、未知提示、放弃与390px无溢出通过。provider协议及API均注入模拟响应，未调用付费模型，实际定位准确率和耗时未实测，不可声称已验证。
- 已完成只读代码复核并修复跨域画布污染与累积漂移；已更新本地Python/Java容器。使用位置：5173 → 视频工作台 → AI扫描全片。尚未提交/推送。
''')
