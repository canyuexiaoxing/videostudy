from pathlib import Path
import subprocess
root=Path('E:/workp/videostudy')
stage=Path(__file__).parent/'region-images/python'
query="SELECT COUNT(*) FROM transcription_jobs WHERE status IN ('queued','processing')"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
active=subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',command],text=True).strip()
assert active=='0','Active analysis task; do not restart'
(stage/'analysis.py').write_bytes((root/'agent-python/analysis.py').read_bytes())
subprocess.run(['docker','build','--pull=false','-t','videostudy-agent-python',str(stage)],cwd=root,check=True)
subprocess.run(['docker','compose','-f','compose.yaml','-f','compose.gpu.yaml','up','-d','--no-build','--no-deps','agent-python'],cwd=root,check=True)
for name in ['docs/superpowers/specs/2026-10-10-video-ignore-region-backend.md','docs/交接-2026-10-10.md']:
    p=root/name;s=p.read_text(encoding='utf-8')
    s=s.replace('Python173项：172通过','Python174项：173通过').replace('Python173项（172通过1跳过）','Python174项（173通过1跳过）').replace('新增8项','新增9项')
    if 'backend.md' in name:
        s+='\n代码复核发现并修复NULL区域任务新增缓存字段导致旧检查点失效的问题：仅非空区域加入缓存上下文。增加旧版上下文实际缓存文件回归测试，确认无框选旧任务可复用转写阶段，避免重复调用已完成模型阶段。\n'
    p.write_text(s,encoding='utf-8')
