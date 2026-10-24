"""Deliver only the verified map-format patch after the directory app exits."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shutil,subprocess
ROOT=Path(__file__).resolve().parents[3]
FILES=('course_map_format.py','course_reply_repair.py','course_mind_map.py','direct_course_map.py')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def plain(path):
 for item in (path,*path.parents):
  if item.is_symlink() or (item.exists() and getattr(item.lstat(),'st_file_attributes',0)&0x400):raise RuntimeError('linked_path_refused')
def deliver():
 latest=json.loads((ROOT/'.local/releases/latest.json').read_text(encoding='utf-8-sig'))
 folder=Path(latest['folder']).resolve();release_root=(ROOT/'.local/releases').resolve()
 if not folder.is_relative_to(release_root):raise RuntimeError('unexpected_application_folder')
 plain(folder);runtime=folder/'resources/runtime';manifest_path=runtime/'runtime-manifest.json';plain(manifest_path)
 process_check=subprocess.run(['powershell.exe','-NoProfile','-Command',"Get-Process -Name Framewise -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],capture_output=True,text=True)
 if process_check.stdout.strip():raise RuntimeError('desktop_must_be_closed')
 manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'));entries={item['path']:item for item in manifest['critical']}
 backup=ROOT/'.local/qa/map-format-boundary/delivery-backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');backup.mkdir(parents=True)
 destinations=[]
 for name in FILES:
  source=ROOT/'agent-python'/name;target=runtime/'agent'/name;plain(source);plain(target)
  key='agent/'+name
  if key not in entries or digest(target)!=entries[key]['sha256']:raise RuntimeError('target_integrity_mismatch:'+name)
  shutil.copy2(target,backup/name);destinations.append((source,target,key))
 shutil.copy2(manifest_path,backup/'runtime-manifest.json')
 try:
  for source,target,key in destinations:
   shutil.copy2(source,target);entries[key]['sha256']=digest(source)
   if digest(target)!=entries[key]['sha256']:raise RuntimeError('delivery_checksum_mismatch')
  temp=manifest_path.with_suffix('.json.patch-tmp');temp.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8');os.replace(temp,manifest_path)
 except Exception:
  for _,target,_ in destinations:shutil.copy2(backup/target.name,target)
  shutil.copy2(backup/'runtime-manifest.json',manifest_path);raise
 result={'stage':'map_format_delivery','status':'completed','timestamp':datetime.now(timezone.utc).isoformat(),'application':str(folder),'appVersion':manifest['appVersion'],'changed':list(FILES),'backup':str(backup),'cloudArtifactsModified':False}
 (ROOT/'.local/qa/map-format-boundary/delivery-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':deliver()
