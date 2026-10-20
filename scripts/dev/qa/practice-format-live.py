"""Explicitly authorized bounded follow-up; four practice batches, at most eight real API calls."""
from pathlib import Path
import json,os,shutil,subprocess,time
ROOT=Path(__file__).resolve().parents[3];old=ROOT/'.local/qa/deepseek-live/20261019-144804';folder=ROOT/'.local/qa/practice-format'/('live-'+time.strftime('%Y%m%d-%H%M%S'));folder.mkdir(parents=True,exist_ok=False)
shutil.copytree(old/'database',folder/'database');shutil.copytree(old/'keyframes',folder/'keyframes');(folder/'uploads').mkdir()
(ROOT/'.local/qa/practice-format/live-latest.json').write_text(json.dumps({'folder':str(folder)}))
image=json.loads((ROOT/'.local/qa/practice-format/build.json').read_text())['images']['agent-python']['staged']
env={**os.environ,'FRAMEWISE_LIVE_AGENT_IMAGE':image,'FRAMEWISE_LIVE_QA_RESUME':str(folder),'FRAMEWISE_LIVE_QA_PHASE':'format','FRAMEWISE_LIVE_LIMIT':'8'}
raise SystemExit(subprocess.run([str(ROOT/'agent-python/.venv/Scripts/python.exe'),'-u',str(ROOT/'scripts/dev/qa/deepseek-live.py')],cwd=ROOT,env=env).returncode)
