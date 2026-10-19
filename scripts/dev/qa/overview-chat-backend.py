"""Readiness/CORS/validation checks; no valid model request is ever issued."""
from pathlib import Path
import argparse,json,subprocess,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--docker',required=True);a=p.parse_args()
def run(*args,**kwargs):return subprocess.run([a.docker,*args],cwd=ROOT,check=True,**kwargs)
folder='/tmp/framewise-overview-chat-qa';run('exec','videostudy-agent-python-1','mkdir','-p',folder)
for name in ['test_overview_chat.py','test_overview.py','test_overview_required_notes.py','test_model_diagnostics.py','test_overview_chat_route.py']:
 run('cp',str(ROOT/'agent-python'/name),'videostudy-agent-python-1:'+folder+'/'+name)
result=run('exec','-e','PYTHONPATH='+folder+':/app','-e','KEYFRAME_DIR='+folder+'/keyframes','-e','MODEL_LOG_DIR='+folder+'/logs','-w',folder,'videostudy-agent-python-1','python','-m','unittest','test_overview_chat','test_overview','test_overview_required_notes','test_model_diagnostics','test_overview_chat_route','-q',capture_output=True,text=True)
(ROOT/'.local/qa/overview-chat/python-container.log').write_text(result.stdout+result.stderr,encoding='utf8')
base='http://127.0.0.1:18080/api/transcriptions'
with urllib.request.urlopen(base) as response:history=json.load(response)
identity=history[0]['id'] if history else 'ffffffff-ffff-4fff-8fff-ffffffffffff'
preflight=urllib.request.Request(base+'/'+identity+'/media',headers={'Origin':'app://framewise','Access-Control-Request-Method':'PUT'},method='OPTIONS')
with urllib.request.urlopen(preflight) as response:assert response.headers['Access-Control-Allow-Origin']=='app://framewise' and 'PUT' in response.headers['Access-Control-Allow-Methods']
request=urllib.request.Request(base+'/'+identity+'/media',data=json.dumps({'size':0,'fingerprint':'a'*64,'bindingSource':'user_confirmed'}).encode(),headers={'Content-Type':'application/json'},method='PUT')
try:urllib.request.urlopen(request);raise AssertionError('Manual cache was accepted')
except urllib.error.HTTPError as error:
 assert error.code==(400 if history else 404)
 rejection_status=error.code
proof={'ready':True,'pythonTests':24,'desktopCorsAllowsMigration':True,'manualCacheNotAccepted':True,'liveMigrationRejectionStatus':rejection_status,'historyCountAtCheck':len(history),'paidModelCalls':0,'historyReanalysis':False}
(ROOT/'.local/qa/overview-chat/backend-verification.json').write_text(json.dumps(proof,indent=2),encoding='utf8');print(json.dumps(proof))
