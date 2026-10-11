from pathlib import Path
p=Path('E:/workp/videostudy')
for name in ['agent-python/Dockerfile','agent-python/Dockerfile.gpu']:
 path=p/name
 s=path.read_text(encoding='utf-8')
 assert 'practice.py ./' in s
 path.write_text(s.replace('practice.py ./','practice.py question_chat.py ./'),encoding='utf-8')
