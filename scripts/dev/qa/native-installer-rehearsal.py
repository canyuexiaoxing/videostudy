"""Rehearse the full installer in a unique owned directory; never launch user analysis."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid

ROOT=Path(__file__).resolve().parents[3]

def sha(file):
    value=hashlib.sha256()
    with file.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()

def run(setup, app_folder, skip_smoke=False, resume_base=None):
    setup=Path(setup).resolve(strict=True);app_folder=Path(app_folder).resolve(strict=True)
    if setup.suffix.lower()!='.exe':raise ValueError('setup_exe_required')
    base=Path(resume_base).resolve() if resume_base else ROOT/'.local/qa/native-delivery/full-install'/str(uuid.uuid4())
    if base.parent.resolve()!=(ROOT/'.local/qa/native-delivery/full-install').resolve() or str(uuid.UUID(base.name))!=base.name:raise ValueError('invalid_resume_directory')
    install=base/'program';external=base/'external-user-data';external.mkdir(parents=True,exist_ok=True)
    note=external/'notes.json'
    if not note.exists():note.write_text('{"note":"keep user data","image":"fixture"}',encoding='utf-8')
    original=sha(note);events=[]
    def execute(stage,args):
        started=time.monotonic()
        result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=1800)
        (base/(stage+'-output.log')).write_text(result.stdout.decode('utf-8','replace')+'\n'+result.stderr.decode('utf-8','replace'),encoding='utf-8')
        events.append({'stage':stage,'elapsedSeconds':round(time.monotonic()-started,2),'exitCode':result.returncode})
        (base/'events.json').write_text(json.dumps(events,indent=2),encoding='utf-8')
        if result.returncode:raise RuntimeError(stage+'_failed:'+str(result.returncode))
    if not resume_base:execute('silent_install',[str(setup),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER','/SP-','/DIR='+str(install),'/GROUP=Framewise QA','/LOG='+str(base/'install.log')])
    manifest=json.loads((app_folder/'resources/runtime/runtime-manifest.json').read_text(encoding='utf-8'))
    version=manifest['appVersion'];installed=install/'versions'/version
    if sha(installed/'Framewise.exe')!=sha(app_folder/'Framewise.exe'):raise RuntimeError('installed_exe_mismatch')
    if sha(installed/'resources/app.asar')!=sha(app_folder/'resources/app.asar'):raise RuntimeError('installed_asar_mismatch')
    for entry in manifest['critical']:
        if sha(installed/'resources/runtime'/entry['path'])!=entry['sha256']:raise RuntimeError('installed_runtime_integrity_mismatch')
    if not skip_smoke:
        smoke = ROOT/'scripts/dev/qa/native-installed-smoke.mjs'
        if not smoke.is_file():raise RuntimeError('installed_smoke_script_missing')
        node = os.environ.get('FRAMEWISE_QA_NODE') or shutil.which('node')
        if not node:raise RuntimeError('qa_node_required')
        execute('installed_executable_smoke',[node,str(smoke),'--app='+str(installed/'Framewise.exe'),'--profile='+str(base/'application-profile')])
    marker=install/'unowned-preserve.txt';marker.write_text('unowned file',encoding='utf-8')
    uninstall=install/'unins000.exe'
    if not uninstall.is_file():raise RuntimeError('uninstaller_missing')
    execute('silent_uninstall',[str(uninstall),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(base/'uninstall.log')])
    if (installed/'Framewise.exe').exists():raise RuntimeError('uninstall_left_installed_executable')
    if sha(note)!=original or not marker.is_file():raise RuntimeError('uninstall_did_not_preserve_external_data_or_unowned_file')
    report={'stage':'full_installer_rehearsal','setup':str(setup),'appFolder':str(app_folder),'isolatedInstall':str(install),'criticalFilesVerified':len(manifest['critical']),'appAsarSha256':sha(app_folder/'resources/app.asar'),'installedSmoke':not skip_smoke,'userDataPreserved':True,'unownedFilePreserved':True,'events':events}
    (base/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--setup',required=True);parser.add_argument('--app-folder',required=True);parser.add_argument('--skip-smoke',action='store_true');parser.add_argument('--resume-base');args=parser.parse_args();run(args.setup,args.app_folder,args.skip_smoke,args.resume_base)
    # A coordination gate stops an already-running QA pipeline from starting
    # its release build while another independently tested patch is pending.
    if not args.skip_smoke and (ROOT/'.local/qa/native-delivery/hold-release.json').exists():
        print(json.dumps({'stage':'release_compile_held','qaRehearsalPassed':True}),flush=True)
        raise SystemExit(75)

