"""Offline parser microbenchmark; no course files or model requests."""
import sys,json,time,statistics,importlib.util,os,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
import course_json

def load(path):
 spec=importlib.util.spec_from_file_location('before',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
old=load(ROOT/'.local/dev/course-json-before-duplicates.py')
leaf={'title':'formula x + y = z','sourceIds':['t_1'],'imageIds':['img_1'],'children':[],'details':[]}
raw={'topic':'offline','children':[dict(leaf,title=f'method {i}') for i in range(200)],'examples':[],'uncertainties':[]}
text=json.dumps(raw);dup=text.replace('"sourceIds": ["t_1"]','"sourceIds": ["t_1"],"sourceIds": ["t_1"]')
def bench(parser,value):
 samples=[]
 for _ in range(5):
  t=time.perf_counter()
  for _ in range(100):parser(value)
  samples.append((time.perf_counter()-t)*10)
 return round(statistics.median(samples),3)
with tempfile.TemporaryDirectory() as d:
 os.environ['MODEL_LOG_DIR']=d
 assert old.parse_course_json(text)==course_json.parse_course_json(text)==course_json.parse_course_json(dup)
 report={'characters':len(text),'nodes':200,'old_valid_ms':bench(old.parse_course_json,text),'new_valid_ms':bench(course_json.parse_course_json,text),'new_duplicate_ms':bench(course_json.parse_course_json,dup),'paidCalls':0}
 target=ROOT/'.local/qa/duplicate-key-performance.json';target.write_text(json.dumps(report,indent=2));print(json.dumps(report))
 from model_diagnostics import close_logs
 close_logs()
