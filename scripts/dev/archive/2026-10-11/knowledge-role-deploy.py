from pathlib import Path
import subprocess
root=Path(r'E:\workp\videostudy')
stage=Path(__file__).parent/'knowledge-role-image'
stage.mkdir(exist_ok=True)
query="SELECT COUNT(*) FROM transcription_jobs WHERE status IN ('queued','processing')"
command='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -Nse "'+query+'"'
active=subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',command],text=True).strip()
if active!='0': raise RuntimeError('存在进行中的分析任务，暂不重启：'+active)
(stage/'mind_map.py').write_bytes((root/'agent-python/mind_map.py').read_bytes())
(stage/'Dockerfile').write_text('FROM videostudy-agent-python:latest\nCOPY mind_map.py /app/mind_map.py\n')
subprocess.run(['docker','build','--pull=false','-t','videostudy-agent-python',str(stage)],cwd=root,check=True)
subprocess.run(['docker','compose','-f','compose.yaml','-f','compose.gpu.yaml','up','-d','--no-build','--no-deps','agent-python'],cwd=root,check=True)
p=root/'docs/交接-2026-10-10.md'
with p.open('a',encoding='utf-8') as f:
 f.write('''

## 补充：区分独立知识讲解与例题中的知识应用

用户纠正：前面已专门讲过的核心知识，后面例题再次使用时仍属于例题，不能变成重复核心跳转。提示版本更新为 grounded-mind-map-v4-teaching-roles，要求按讲解目的区分 explanation、application、new_knowledge。例题提醒公式和代入步骤不进入核心；只有例题中新引入的独立定义、推导、适用条件才允许 new_knowledge。汇总后以已验证例题时间区间过滤普通核心引用；混合引用保留独立讲解部分，纯应用节点移除，祖先继承引用重新从保留子节点取得。有独立核心引用的父节点不会因应用子节点移除而消失。内部角色与显式引用标记不进入API结果。仅导图缓存版本变化，媒体和页面缓存不变，模型请求次数不增加。旧导图需用户手动重新生成。

Python188项（187通过1跳过），含混合引用、例题范围过滤、独立新增知识保留、空分组裁剪、父级跳转重建和独立父节点保留的回归验证；无付费模型调用，尚未实测模型对真实课堂角色的分类准确率。
''')
