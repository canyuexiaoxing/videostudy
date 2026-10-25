
from pathlib import Path
import subprocess,json,time,hashlib,ast,os,re,importlib.metadata as md,sys
ROOT=Path(__file__).resolve().parents[3];QA=ROOT/'.local/qa/aic-report-2026-10-25';QA.mkdir(parents=True,exist_ok=True)
NODE='C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
GIT='C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
def run(label,cmd,cwd=ROOT,env=None):
 started=time.monotonic()
 with (QA/f'{label}.log').open('w',encoding='utf8') as log:
  p=subprocess.run(cmd,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,text=True)
 value={'command':cmd,'exitCode':p.returncode,'elapsedSeconds':round(time.monotonic()-started,3),'log':f'.local/qa/aic-report-2026-10-25/{label}.log'}
 (QA/f'{label}.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps({'stage':label,**value},ensure_ascii=False),flush=True)
 return value
env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PATH']=str(ROOT/'.local/tools/ffmpeg-9.0.2-full_build/bin')+os.pathsep+str(Path(NODE).parent)+os.pathsep+env.get('PATH','')
for name in ('RUN_MEDIA_INTEGRATION','RUN_MODEL_INTEGRATION','RUN_LIVE_TESTS'):env.pop(name,None)
mode=sys.argv[1]
if mode=='desktop':
 files=[str(p) for folder,pattern in [('desktop/src','*.test.mjs'),('desktop/electron','*.test.cjs')] for p in (ROOT/folder).glob(pattern)]
 run(mode,[NODE,'--test',*files],env=env)
elif mode=='python':
 run(mode,[str(ROOT/'.local/native/runtime/python/python.exe'),'-m','unittest','discover','-s','agent-python'],env=env)
elif mode=='build':
 run(mode,[NODE,str(ROOT/'desktop/node_modules/typescript/bin/tsc'),'--version'])
 run('frontend-typecheck',[NODE,str(ROOT/'desktop/node_modules/vue-tsc/bin/vue-tsc.js'),'--noEmit'],ROOT/'desktop',env)
 run('frontend-build',[NODE,str(ROOT/'desktop/node_modules/vite/bin/vite.js'),'build'],ROOT/'desktop',env)
elif mode=='java':
 selector=QA/'selector-tcp';selector.write_text('Force JDK TCP loopback fallback',encoding='utf8');env['JAVA_TOOL_OPTIONS']='-Djava.net.preferIPv4Stack=true -Djdk.net.unixdomain.tmpdir='+str(selector);env['JAVA_HOME']='D:/soft/OradeJDK/JDK21';env['PATH']=env['JAVA_HOME']+'/bin'+os.pathsep+env['PATH']
 run(mode,['powershell.exe','-NoProfile','-Command',"& 'D:/mytools/mavwwww/apache-maven-3.9.14/bin/mvn.cmd' '-o' 'test'"],ROOT/'backend-java',env)
elif mode=='inventory':
 inventory=[]
 for base,extensions in [('agent-python',{'.py'}),('desktop/src',{'.ts','.vue','.mjs','.css'}),('desktop/electron',{'.cjs'}),('backend-java/src',{'.java','.sql','.yml','.yaml','.properties'})]:
  for p in sorted((ROOT/base).rglob('*')):
   if not p.is_file() or p.suffix not in extensions or any(x in p.parts for x in ('__pycache__','.venv','node_modules','target','dist')):continue
   t=p.read_text(encoding='utf8',errors='replace');item={'path':p.relative_to(ROOT).as_posix(),'lines':len(t.splitlines()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'test':p.name.startswith('test_') or '.test.' in p.name or '/test/' in p.as_posix()}
   if p.suffix=='.py':
    try:item['symbols']=[n.name for n in ast.parse(t).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
    except SyntaxError:item['parseError']=True
   inventory.append(item)
 versions={}
 for folder in ('python','person'):
  versions[folder]={d.metadata['Name']:d.version for d in md.distributions(path=[str(ROOT/'.local/native/runtime'/folder/'Lib/site-packages')])}
 lock=json.loads((ROOT/'desktop/package-lock.json').read_text(encoding='utf8'))
 versions['npm']={k:v.get('version') for k,v in lock.get('packages',{}).items() if k in ['node_modules/'+x for x in ('vue','simple-mind-map','katex','electron','vite','typescript')]}
 versions['commit']=subprocess.check_output([GIT,'-c',f'safe.directory={ROOT.as_posix()}','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 result={'reviewDate':'2026-10-25','inventory':inventory,'versions':versions,'sourceFiles':len(inventory),'testsFiles':sum(x['test'] for x in inventory),'paidModelCalls':0}
 (QA/'scan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps({k:v for k,v in result.items() if k not in ('inventory','versions')},ensure_ascii=False))
