"""Install a verified frontend-only package after Framewise exits."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,os,shutil,subprocess
ROOT=Path(__file__).resolve().parents[3]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def plain(path):
 for part in (path,*path.parents):
  if part.is_symlink() or part.exists() and getattr(part.lstat(),'st_file_attributes',0)&0x400:raise RuntimeError('linked_path_refused')
def main():
 record=ROOT/'.local/qa/direct-only/prepared.json';r=json.loads(record.read_text(encoding='utf8'))
 latest=json.loads((ROOT/'.local/releases/latest.json').read_text(encoding='utf-8-sig'))
 target=Path(r['archive']).resolve();prepared=Path(r['prepared']).resolve()
 if target!=Path(latest['folder']).resolve()/'resources/app.asar':raise RuntimeError('application_path_changed')
 if not target.is_relative_to((ROOT/'.local/releases').resolve()) or not prepared.is_relative_to((ROOT/'.local/qa/direct-only').resolve()):raise RuntimeError('unexpected_path')
 plain(target);plain(prepared)
 if sha(prepared)!=r['preparedSha256'] or sha(target)!=r['previousSha256']:raise RuntimeError('package_checksum_changed')
 def closed():
  result=subprocess.run(['powershell.exe','-NoProfile','-Command','Get-Process -Name Framewise -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],capture_output=True,text=True)
  if result.stdout.strip():raise RuntimeError('desktop_must_be_closed')
 closed();backup=prepared.parent/'app.before-direct-only.asar'
 if backup.exists():raise RuntimeError('backup_already_exists')
 shutil.copy2(target,backup)
 if sha(backup)!=r['previousSha256']:raise RuntimeError('backup_checksum_failed')
 temporary=target.with_name('app.asar.direct-only.tmp')
 if temporary.exists():raise RuntimeError('temporary_already_exists')
 try:
  shutil.copy2(prepared,temporary)
  if sha(temporary)!=r['preparedSha256']:raise RuntimeError('staged_checksum_failed')
  closed();os.replace(temporary,target)
  if sha(target)!=r['preparedSha256']:raise RuntimeError('installed_checksum_failed')
 except Exception:
  if sha(target)!=r['previousSha256']:shutil.copy2(backup,target)
  temporary.unlink(missing_ok=True);raise
 r.update(installed=True,backup=str(backup),installedAt=datetime.now(timezone(timedelta(hours=8))).isoformat(),databaseModified=False,runtimeModified=False,cloudArtifactsModified=False)
 record.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps({k:r[k] for k in ['installed','installedAt','databaseModified','runtimeModified','cloudArtifactsModified','backup']}))
if __name__=='__main__':main()
