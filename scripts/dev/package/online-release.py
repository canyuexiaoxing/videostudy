"""Build immutable OBS online-installer releases without uploading anything."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,os,re,shutil,stat,subprocess,time,uuid,zipfile
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('native_installer',Path(__file__).with_name('native-installer.py'));native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
DEFAULT_BASE='https://framewise-download-2026.obs.cn-east-3.myhuaweicloud.com/releases/'
CSC=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
def sha256(path):return native.sha256(path)
def valid_base(value):
 p=urlsplit(value)
 if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.port not in (None,443):raise ValueError('invalid_https_base')
 return value.rstrip('/')+'/'
def valid_name(value):
 if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,120}',value) or re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)',value,re.I):raise ValueError('invalid_release_name')
 return value

def component(name):
 if name.startswith('resources/runtime/model-seed/'):return 'models'
 if name.startswith('resources/runtime/person/'):return 'person'
 if name.startswith('resources/runtime/python/'):return 'inference'
 if name.startswith('resources/runtime/java/') or name.startswith('resources/runtime/ffmpeg/'):return 'platform'
 return 'application'

def build_packages(source,output,maximum_bytes=768*1024*1024):
 source=Path(source).resolve();output=Path(output).resolve();native.plain_path(source);native.plain_path(output)
 if source==output or source in output.parents or output in source.parents:raise ValueError('source_output_overlap')
 if output.exists() and any(output.iterdir()):raise ValueError('output_not_empty')
 if not (source/'Framewise.exe').is_file():raise ValueError('Framewise_exe_required')
 groups={}
 for folder,dirs,files in os.walk(source,followlinks=False):
  for name in dirs+files:
   p=Path(folder)/name;s=p.lstat()
   if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0)&0x400:raise ValueError('linked_payload_forbidden')
   if name in files:
    relative=p.relative_to(source).as_posix()
    if name in {'.env','settings.json','framewise.db','desktop-network.jsonl'} or name.endswith(('.db-wal','.db-shm')):raise ValueError('private_data_in_payload')
    if not stat.S_ISREG(s.st_mode):raise ValueError('special_payload_file')
    groups.setdefault(component(relative),[]).append((relative,p,s.st_size))
 output.mkdir(parents=True,exist_ok=True);artifacts=[]
 for group,files in sorted(groups.items()):
  chunk=[];size=0;number=0
  def finish(items):
   nonlocal number
   if not items:return
   number+=1;name=f'{group}-{number:03d}.zip';target=output/name;started=time.monotonic()
   with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
    for relative,p,expected in items:
     before=p.stat();z.write(p,relative)
     after=p.stat()
     if before.st_size!=expected or after.st_size!=before.st_size or after.st_mtime_ns!=before.st_mtime_ns:raise ValueError('payload_changed_during_build')
   result={'name':name,'size':target.stat().st_size,'sha256':sha256(target),'unpackedBytes':sum(v[2] for v in items),'fileCount':len(items),'component':group}
   artifacts.append(result);print(json.dumps({'stage':'package_created',**result,'elapsedSeconds':round(time.monotonic()-started,2)}),flush=True)
  for row in sorted(files):
   if chunk and size+row[2]>maximum_bytes:finish(chunk);chunk=[];size=0
   chunk.append(row);size+=row[2]
  finish(chunk)
 return artifacts

def compile_core(folder,entries,version,build,output,app_id=native.APP_ID):
 include=build/'archives.iss'
 lines=[]
 for e in entries:
  valid_name(e['name']);lines.append('Source: "{code:OnlineCache}\\'+e['name']+'"; DestDir: "{app}\\versions\\'+version+'"; Flags: external extractarchive ignoreversion recursesubdirs createallsubdirs; ExternalSize: '+str(e['unpackedBytes'])+'; Hash: "'+e['sha256']+'"')
 include.write_text('\n'.join(lines)+'\n',encoding='utf-8-sig')
 info=build/'install-info.txt';info.write_text('Framewise online installation. All selected components are downloaded from HTTPS and verified before installation. User courses, notes, settings, models and original videos are preserved outside the program installation. This build is unsigned. Third-party notices remain in the runtime. External distribution requires completing the applicable license review.\n',encoding='utf8')
 command=[str(native.DEFAULT_COMPILER),'/Qp','/DOnlineArchiveInclude='+str(include),'/DAppSource='+str(folder),'/DOutputDirectory='+str(output),'/DAppVersion='+version,'/DNumericVersion='+version+'.0','/DAppName=Framewise','/DProductGuid='+app_id,'/DPayloadBytes='+str(sum(e['unpackedBytes'] for e in entries)),'/DOutputName=install-core','/DUpgradeInfo='+str(info),str(ROOT/'desktop/installer/framewise.iss')]
 result=subprocess.run(command,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));(build/'core-compile.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf8')
 if result.returncode:raise RuntimeError('inno_core_compile_failed:'+str(build/'core-compile.log'))
 p=output/'install-core.exe';return {'name':p.name,'size':p.stat().st_size,'sha256':sha256(p),'component':'installer','unpackedBytes':0}

def compile_bootstrapper(manifest,manifest_url,version,output,build):
 config=build/'ReleaseInfo.cs';config.write_text('[assembly: System.Reflection.AssemblyTitle("Framewise Online Setup")] [assembly: System.Reflection.AssemblyVersion("'+version+'.0")] namespace FramewiseSetup { internal static class ReleaseInfo { public const long ManifestSize='+str(manifest.stat().st_size)+'; public const string ManifestHash="'+sha256(manifest)+'"; public const string ManifestUrl="'+manifest_url+'"; public const long PayloadBytes='+str(json.loads(manifest.read_text())["payloadBytes"])+'; public const long DownloadBytes='+str(sum(p["size"] for p in json.loads(manifest.read_text())["packages"])+json.loads(manifest.read_text())["installer"]["size"])+'; public const string Version="'+version+'"; } }',encoding='utf8')
 winmanifest=build/'bootstrap.manifest';winmanifest.write_text('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0"><assemblyIdentity version="1.0.0.0" processorArchitecture="amd64" name="Framewise.OnlineSetup" type="win32"/><trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges><requestedExecutionLevel level="asInvoker" uiAccess="false"/></requestedPrivileges></security></trustInfo><compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1"><application><supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/></application></compatibility><dependency><dependentAssembly><assemblyIdentity type="win32" name="Microsoft.Windows.Common-Controls" version="6.0.0.0" processorArchitecture="*" publicKeyToken="6595b64144ccf1df" language="*"/></dependentAssembly></dependency></assembly>''',encoding='utf8')
 target=output/f'Framewise-{version}-Online-Setup.exe'
 cmd=[str(CSC),'/nologo','/target:winexe','/platform:x64','/optimize+','/codepage:65001','/win32manifest:'+str(winmanifest),'/win32icon:'+str(ROOT/'desktop/public/favicon.ico'),'/out:'+str(target),'/r:System.Windows.Forms.dll','/r:System.Drawing.dll','/r:System.Web.Extensions.dll',str(ROOT/'desktop/installer/OnlineDownload.cs'),str(ROOT/'desktop/installer/OnlineModelSeed.cs'),str(ROOT/'desktop/installer/OnlineSetup.cs'),str(config)]
 result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));(build/'bootstrap-compile.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf8')
 if result.returncode:raise RuntimeError('bootstrap_compile_failed:'+str(build/'bootstrap-compile.log'))
 return target

def validate_native_payload(source,version):
 manifest=source/'resources/runtime/runtime-manifest.json'
 value=json.loads(manifest.read_text(encoding='utf-8-sig'))
 if value.get('appVersion')!=version or not value.get('critical'):raise ValueError('native_version_mismatch')
 for item in value['critical']:
  name=item.get('path','')
  if not name or '\\' in name or name.startswith('/') or '..' in name.split('/') or ':' in name:raise ValueError('invalid_runtime_path')
  target=source/'resources/runtime'/name;native.plain_path(target)
  if not target.is_file() or sha256(target)!=item.get('sha256'):raise ValueError('native_integrity_failed')

def release(source,output,base_url=DEFAULT_BASE):
 started=time.monotonic();source=native.absolute(source);output=native.absolute(output);base=valid_base(base_url)
 if output.exists() and any(output.iterdir()):raise ValueError('release_output_not_empty')
 version=json.loads((ROOT/'desktop/package.json').read_text(encoding='utf-8-sig'))['version'];native.valid_version(version)
 if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('numeric_release_version_required')
 validate_native_payload(source,version)
 release_id=valid_name(version+'-r'+time.strftime('%Y%m%d%H%M%S'));publish=output/'publish';release_dir=publish/release_id;build=output/'build';build.mkdir(parents=True)
 entries=build_packages(source,release_dir)
 core=compile_core(source,entries,version,build,release_dir)
 value={'format':'framewise-online-release','schemaVersion':1,'appVersion':version,'releaseId':release_id,'platform':'windows-x64','baseUrl':base+release_id+'/','packages':entries,'installer':core,'payloadBytes':sum(e['unpackedBytes'] for e in entries),'userDataPolicy':'preserved','manifestPolicy':'installer-pinned-sha256','createdAtUtc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 manifest=release_dir/'release.json';manifest.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 exe=compile_bootstrapper(manifest,base+release_id+'/release.json',version,publish,build)
 report={'releaseId':release_id,'appVersion':version,'payloadBytes':value['payloadBytes'],'downloadBytes':sum(e['size'] for e in entries)+core['size'],'installerBytes':exe.stat().st_size,'installerSha256':sha256(exe),'manifestSha256':sha256(manifest),'elapsedSeconds':round(time.monotonic()-started,2),'publishDirectory':str(publish),'baseUrl':base,'installationValidation':'not_run_per_user_request'}
 (output/'release-summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
 (output/'上传说明.txt').write_text('将publish目录中的全部内容上传到OBS桶的releases文件夹，保留目录结构。先上传版本子目录中的所有zip、install-core.exe和release.json，校验下载后再上传对外的Online-Setup.exe。只开放这些发布对象的匿名读取，不开放写入/ACL。网页下载按钮指向'+base+exe.name+'。用户只下载Online-Setup.exe；不用逐个下载zip。不要上传build目录、用户数据或密钥。此构建未代码签名；外部分发前需完成项目及第三方许可复核。\n',encoding='utf-8-sig')
 print(json.dumps({'stage':'online_release_ready',**report}),flush=True);return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--app-folder',required=True);p.add_argument('--output-dir',required=True);p.add_argument('--base-url',default=DEFAULT_BASE);a=p.parse_args();release(a.app_folder,a.output_dir,a.base_url)
