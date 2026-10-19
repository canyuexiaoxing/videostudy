from pathlib import Path
import subprocess,argparse,time,json
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--docker',required=True);a=p.parse_args()
def run(*args,**kw):return subprocess.run([a.docker,*args],check=True,cwd=ROOT,**kw)
folder='/tmp/math-figures-qa-'+str(int(time.time()));run('exec','videostudy-agent-python-1','mkdir','-p',folder)
modules=['practice.py','practice_diagrams.py','question_chat.py','overview_chat.py','model_diagnostics.py']
tests=['test_practice.py','test_practice_context.py','test_practice_history.py','test_practice_diagrams.py','test_question_chat.py','test_overview_chat.py','test_overview_required_notes.py','test_model_diagnostics.py']
for name in modules+tests:run('cp',str(ROOT/'agent-python'/name),'videostudy-agent-python-1:'+folder+'/'+name)
result=run('exec','-e','PYTHONPATH='+folder+':/app','-e','KEYFRAME_DIR='+folder+'/keyframes','-e','MODEL_LOG_DIR='+folder+'/logs','-w',folder,'videostudy-agent-python-1','python','-m','unittest',*[Path(name).stem for name in tests],'-q',capture_output=True,text=True)
output=result.stdout+result.stderr;(ROOT/'.local/qa/math-figures/python-container.log').write_text(output,encoding='utf8');print(output[-600:]);print(json.dumps({'passed':True,'paidModelCalls':0}))
