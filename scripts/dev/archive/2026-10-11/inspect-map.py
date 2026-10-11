import subprocess,json
from pathlib import Path
q="SELECT result_json FROM transcription_jobs WHERE status='completed' AND result_json IS NOT NULL ORDER BY updated_at DESC LIMIT 1"
cmd='MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" --default-character-set=utf8mb4 -NBr -e "'+q+'"'
raw=subprocess.check_output(['docker','exec','videostudy-mysql-1','sh','-c',cmd],text=True,encoding='utf-8').strip()
data=json.loads(raw);Path(__file__).with_name('actual-course.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
m=data.get('mindMap') or {};print('version:',m.get('promptVersion'),'examples:',len(m.get('examples') or []))
def walk(n):
 if not n.get('children'):
  print(json.dumps({'title':n['title'],'time':n['startMs'],'refs':[r['quote'][:140] for r in n.get('evidenceRefs',[])]},ensure_ascii=False))
 for c in n.get('children',[]):walk(c)
walk(m.get('root') or {'title':'empty','startMs':0})
