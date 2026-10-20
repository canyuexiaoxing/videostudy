"""Refresh changed verified native runtime files; the desktop app must be closed."""
from pathlib import Path
import hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[3]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if __name__=='__main__':
 latest=json.loads((ROOT/'.local/releases/latest.json').read_text(encoding='utf-8'))
 folder=Path(latest['folder']).resolve()
 expected=(ROOT/'.local/releases/2026-10-19T15-22-36-954Z/Framewise-win32-x64').resolve()
 if folder!=expected:raise RuntimeError('unexpected_delivery_folder')
 command="Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath -like '"+str(folder)+"\\*'} | Select-Object -ExpandProperty ProcessId"
 processes=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,check=True).stdout.strip()
 if processes:raise RuntimeError('desktop_must_be_closed')
 source=ROOT/'.local/native/runtime';target=folder/'resources/runtime'
 manifest=json.loads((source/'runtime-manifest.json').read_text(encoding='utf-8'));changed=[]
 for entry in manifest['critical']:
  relative=Path(entry['path']);src=source/relative;dst=target/relative
  if digest(src)!=entry['sha256']:raise RuntimeError('source_integrity_failed')
  if not dst.exists() or digest(dst)!=entry['sha256']:
   dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);changed.append(entry['path'])
 shutil.copy2(source/'runtime-manifest.json',target/'runtime-manifest.json')
 print(json.dumps({'changed':changed,'folder':str(folder)},ensure_ascii=False))
