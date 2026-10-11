from pathlib import Path
import subprocess,time,urllib.request,json
root=Path('E:/workp/videostudy'); stage=Path(__file__).parent/'analysis-area-images'
def run(args):subprocess.run(args,cwd=root,check=True)
query="SELECT COUNT(*) FROM transcription_jobs WHERE status IN ('queued','processing')"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
active=subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',command],text=True).strip()
if active!='0':raise RuntimeError('分析任务正在运行，不能重启:'+active)
for name in ('python','java'):(stage/name).mkdir(parents=True,exist_ok=True)
names=('app.py','auto_region.py','ignored_region.py','visual_evidence.py','slide_grouping.py','page_understanding.py','analysis.py')
for name in names:(stage/'python'/name).write_bytes((root/'agent-python'/name).read_bytes())
(stage/'python/Dockerfile').write_text('FROM videostudy-agent-python:latest\nCOPY '+' '.join(names)+' /app/\n')
(stage/'java/app.jar').write_bytes((root/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar').read_bytes())
(stage/'java/Dockerfile').write_text('FROM videostudy-java-api:latest\nCOPY app.jar /app/app.jar\n')
for name,tag in (('python','videostudy-agent-python'),('java','videostudy-java-api')):run(['docker','build','--pull=false','-t',tag,str(stage/name)])
run(['docker','compose','-f','compose.yaml','-f','compose.gpu.yaml','up','-d','--no-build','--no-deps','agent-python','java-api'])
for attempt in range(30):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18080/api/health',timeout=2) as reply:assert json.load(reply)['status']=='ok'
  break
 except Exception:
  if attempt==29:raise
  time.sleep(1)
print('Local API healthy')
run(['docker','cp',str(root/'agent-python/test_analysis_region.py'),'videostudy-agent-python-1:/tmp/test_analysis_region.py'])
run(['docker','exec','-e','PYTHONPATH=/app','videostudy-agent-python-1','python','-m','unittest','discover','-s','/tmp','-p','test_analysis_region.py','-q'])
plan=root/'docs/superpowers/plans/2026-10-11-analysis-area.md'
plan.write_text(plan.read_text(encoding='utf-8').replace('- [ ]','- [x]'),encoding='utf-8')
with (root/'docs/交接-2026-10-10.md').open('a',encoding='utf-8') as f:f.write('''

## 2026-10-11：分析区域与忽略区域叠加

- 视频工作台新增绿色“分析区域”，与蓝色“忽略区域”独立操作、持久化和设置时间节点。首次框选从0秒起，后续移动/缩放/重画新增当前时间节点；不设置分析范围时默认全画面。
- 有效范围为分析框减去忽略框的交集；忽略框在分析范围外不影响分析，部分重叠只排除交集。前端所有手动保存、删除节点和AI候选应用均检查两类节点的全部边界，防止完全遮住分析范围；Java/Python重复校验。
- 沿用 ignoredRegion 参数与原数据库列，兼容旧静态框和忽略时间线；新增组合结构 {analysisRegion,ignoredRegion}。分析框允许全画面。
- 分析范围实际应用到粗选、OCR、同页分组和发给视觉模型的图片。原始视频/截图不修改，通过白色遮罩保持原坐标；OCR过滤保留原始来源索引。音频仍使用整段视频。仅新分析使用设置，历史结果不自动重算。
- 验证：前端55项通过及生产构建通过；Python218项（217通过、1跳过）；Java打包通过。浏览器真实短视频验证绿蓝双框、外部无效提示、部分重叠、完全覆盖拒绝、组合上传参数、独立清除和390px布局。模型调用采用模拟响应，未使用付费模型。
- 已更新本地Python/Java容器并检查健康；尚未提交/推送。
''')
