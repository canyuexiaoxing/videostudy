"""Record anonymous access checks and the notice-copy regression."""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
import json,subprocess,sys,re,hashlib
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];doc=ROOT/'docs/aic-review-2026-10-25';q=ROOT/'.local/qa/aic-open-release-2026-10-25'
rows=[]
for name,url in [('source_repository','https://api.github.com/repos/canyuexiaoxing/videostudy'),('source_baseline','https://api.github.com/repos/canyuexiaoxing/videostudy/git/commits/40173c8462cbfeeeb53ff44ebd70111e14c6db04'),('remote_license','https://api.github.com/repos/canyuexiaoxing/videostudy/license'),('old_installer','https://framewise-download-2026.obs.cn-east-3.myhuaweicloud.com/releases/Framewise-0.3.1-Online-Setup.exe'),('old_manifest','https://framewise-download-2026.obs.cn-east-3.myhuaweicloud.com/releases/0.3.1-r20261020181422/release.json')]:
 try:
  with urlopen(Request(url,headers={'User-Agent':'Framewise-anonymous-review','Range':'bytes=0-65535'}),timeout=20) as r:
   data=r.read(65536);entry={'name':name,'url':url,'status':r.status,'sampleBytes':len(data),'sampleSha256':hashlib.sha256(data).hexdigest()}
   if name in ('source_repository','source_baseline'):
    value=json.loads(data);entry.update(private=value.get('private'),sha=value.get('sha'),license=value.get('license'))
   rows.append(entry)
 except (HTTPError,URLError,TimeoutError) as e:rows.append({'name':name,'url':url,'status':getattr(e,'code',None),'errorType':type(e).__name__})
(doc/'access-check.json').write_text(json.dumps({'checkedAtUtc':datetime.now(timezone.utc).isoformat(),'anonymous':True,'sourceArchivePublished':False,'requests':rows,'scope':'small range GET only; no full installer execution or verification'},ensure_ascii=False,indent=2),encoding='utf8')
run=subprocess.run([sys.executable,str(ROOT/'scripts/dev/package/native-assemble.test.py')],capture_output=True,text=True,encoding='utf8')
output=run.stdout+'\n'+run.stderr
output=re.sub(r'[A-Z]:\\\\Users\\\\[^\"\\r\\n]*','<temporary-path>',output)
(doc/'test-license-packaging.log').write_text(output,encoding='utf8')
assert run.returncode==0 and 'Ran 2 tests' in output and 'OK' in output
(doc/'license-packaging-check.json').write_text(json.dumps({'exitCode':run.returncode,'tests':2,'checks':['notice files copied byte-for-byte','missing runtime rejects manifest'],'newBinaryPackageProduced':False},indent=2),encoding='utf8')
print(json.dumps({'anonymousAccess':rows,'licensePackagingTests':2,'passed':True},ensure_ascii=False))
