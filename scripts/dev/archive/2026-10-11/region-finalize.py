from pathlib import Path
import subprocess
root=Path('E:/workp/videostudy');stage=Path(__file__).parent/'core-map-images/python'
for name in ('app.py','analysis.py','visual_evidence.py','slide_grouping.py','ignored_region.py','analysis_progress.py','mind_map.py'):
 (stage/name).write_bytes((root/'agent-python'/name).read_bytes())
def run(args):subprocess.run(args,cwd=root,check=True)
query="SELECT COUNT(*) FROM transcription_jobs WHERE status IN ('queued','processing')"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
active=subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',command],text=True).strip()
if active!='0':raise RuntimeError('分析任务正在运行，暂不重启:'+active)
run(['docker','build','--pull=false','-t','videostudy-agent-python',str(stage)])
run(['docker','compose','-f','compose.yaml','-f','compose.gpu.yaml','up','-d','--wait','--no-build','--no-deps','agent-python'])
doc=root/'docs/交接-2026-10-10.md'
text='''

## 2026-10-11：忽略区域按时间自动设置节点

- 视频工作台首次框选（无论当前时间）保存为 0ms 默认节点，应用于全片；之后重新框选、移动框或拖右下角缩放，松开指针时以当前视频时间新增节点。同一毫秒更新原节点；没有实际变化不创建节点。
- 区域时间节点可跳转、删除。删除后该时段沿用前一节点；0ms 基线由“清除全部节点”统一清理。播放/拖动进度条时显示该时间实际生效的区域。最多200个节点。
- 按原视频指纹保存，兼容旧静态框。原 ignoredRegion multipart参数接受静态矩形或 {nodes:[{timeMs,region}]}，Java存储/重试与Python分析上下文原样保留时间节点，不需要数据库迁移。
- FFmpeg粗选按时间启用对应遮罩；跨节点的像素比较排除双方忽略框的并集，避免框移动自身成为“课件变化”。同页分组按当前时间过滤OCR，边界比较使用共同可见文字及像素；遮住全部文字不会单独制造空白换页，但真实清屏仍可识别。
- 原始截图和OCR不裁切、不删改。设置只用于新分析，历史任务及重试沿用原参数。
- 验证：前端45项测试；Python207项（206通过、1项跳过）；Java85项通过；生产构建通过。浏览器短视频验证首次0秒、移动新增、同时间缩放更新、重画新增、跳转还原、删除恢复、文件隔离/恢复、实际multipart节点参数、清空和390px无横向溢出，未触发模型调用。已更新本地容器和5173预览。
- 执行计划：docs/superpowers/plans/2026-10-11-ignore-region-timeline.md。本批修改尚未提交或推送。
'''
with doc.open('a',encoding='utf-8') as output:output.write(text)
