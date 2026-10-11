from pathlib import Path
import shutil
p=Path('E:/workp/videostudy')
root=p/'.local/qa/chat-images'
py=root/'python';java=root/'java'
py.mkdir(parents=True,exist_ok=True);java.mkdir(parents=True,exist_ok=True)
for name in ['app.py','question_chat.py']:shutil.copy2(p/'agent-python'/name,py/name)
shutil.copy2(p/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar',java/'app.jar')
(py/'Dockerfile').write_text('FROM videostudy-agent-python:latest\nCOPY app.py question_chat.py /app/\n',encoding='utf-8')
(java/'Dockerfile').write_text('FROM videostudy-java-api:latest\nCOPY app.jar /app/app.jar\n',encoding='utf-8')
