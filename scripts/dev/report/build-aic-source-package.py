"""Build a deterministic source-only review ZIP, with per-file hashes."""
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone
import subprocess,json,hashlib,zipfile,re
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'cailiao';QA=ROOT/'.local/qa/aic-open-release-2026-10-25';DOCS=ROOT/'docs/aic-review-2026-10-25'
git='C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
tracked=subprocess.check_output([git,'-c',f'safe.directory={ROOT.as_posix()}','ls-files','-z'],cwd=ROOT).decode().split('\0')
prefixes=('agent-python/','backend-java/','desktop/','scripts/dev/package/','scripts/dev/deploy/')
fixed={'.gitattributes','README.md','LICENSE','NOTICE','THIRD_PARTY_NOTICES.md','compose.yaml','compose.gpu.yaml','compose.person.yaml','.env.example'}
files={name for name in tracked if name and (name.startswith(prefixes) or name in fixed)}
files.update(fixed)
for sub in ['docs/aic-review-2026-10-25']:
 files.update(p.relative_to(ROOT).as_posix() for p in (ROOT/sub).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
files.update(['scripts/dev/qa/recording-effective-timings.py', 'scripts/dev/report/audit-aic-report-20261025.py', 'scripts/dev/report/build-aic-report-20261025.py', 'scripts/dev/report/build-aic-report.py', 'scripts/dev/report/build-aic-source-package.py', 'scripts/dev/report/capture-aic-demo.mjs', 'scripts/dev/report/check-aic-open-delivery.py', 'scripts/dev/report/check-aic-report-20261025.py', 'scripts/dev/report/export-aic-review-evidence.py', 'scripts/dev/report/prepare-aic-demo.py', 'scripts/dev/report/prepare-aic-open-release.py', 'scripts/dev/report/report-content-20261025.py', 'scripts/dev/report/report-review-evidence-20261025.py', 'scripts/dev/report/report-technical-appendix-20261025.py'])
# Include documentation required by build/runtime preparation without private course assets.
files.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'docs').glob('*.md'))
forbidden_parts={'.git','.local','.venv','node_modules','target','dist','__pycache__'}
files={name for name in files if not (set(PurePosixPath(name).parts)&forbidden_parts) and not name.endswith(('.pyc','.log'))}
files.update(f'docs/aic-review-2026-10-25/test-{key}.log' for key in ['desktop','python','java','frontend-typecheck','frontend-build','license-packaging'])
contents={};manifest=[]
for name in sorted(files):
 p=ROOT/name
 if not p.is_file() or p.is_symlink():raise RuntimeError('missing_or_linked_source:'+name)
 b=p.read_bytes()
 if p.suffix.lower() in {'.py','.ts','.vue','.js','.mjs','.cjs','.json','.md','.txt','.properties','.xml','.yaml','.yml','.example','.log'}:
  t=b.decode('utf8',errors='replace')
  # Block credential-like live strings, not variable names or bounded dummy IDs.
  if re.search(r'wxid_[A-Za-z0-9_]+',t):raise RuntimeError('private_chat_path:'+name)
  if re.search(r'\bsk-[A-Za-z0-9_-]{24,}\b',t):raise RuntimeError('credential_pattern:'+name)
  if re.search(r'-----BEGIN (?:OPENSSH|RSA) PRIVATE KEY-----\r?\n[A-Za-z0-9+/=]{40,}',t):raise RuntimeError('private_key:'+name)
 contents[name]=b;manifest.append({'path':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
meta={'format':'framewise-source-review-v1','baseCommit':'40173c8462cbfeeeb53ff44ebd70111e14c6db04','snapshotDate':'2026-10-25','license':'AGPL-3.0-only','scope':'first-party source snapshot plus license/packaging notices and review materials; no installed dependencies/weights/user courses/Git history','files':manifest}
contents['SOURCE_MANIFEST.json']=json.dumps(meta,ensure_ascii=False,indent=2).encode()
archive=OUT/'Framewise_AIC源码核验包_2026-10-25.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
 for name,b in sorted(contents.items()):
  info=zipfile.ZipInfo('Framewise-source/'+name,date_time=(2026,10,25,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,b)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for item in manifest:assert hashlib.sha256(z.read('Framewise-source/'+item['path'])).hexdigest()==item['sha256']
summary={'file':archive.name,'files':len(contents),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'firstPartyLicense':'AGPL-3.0-only','baseCommit':meta['baseCommit'],'reproducibleFileManifest':True,'credentialPatternScan':'passed','thirdPartyWeightsOrRuntimesIncluded':False,'remotePublished':False}
(QA/'source-package.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(summary,ensure_ascii=False))
