"""Assemble the offline application payload without copying developer state."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time

ROOT = Path(__file__).resolve().parents[3]
REQUIRED = ('python/python.exe', 'person/python.exe', 'java/bin/java.exe', 'ffmpeg/bin/ffmpeg.exe', 'ffmpeg/bin/ffprobe.exe', 'agent/native_bootstrap.py', 'agent/native_process_host.py', 'app.jar')

def digest(file):
    value = hashlib.sha256()
    with file.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()

def plain(file):
    for entry in (file, *file.parents):
        if entry.is_symlink() or (entry.exists() and getattr(entry.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('linked_payload_forbidden')

def assemble(root=ROOT):
    start = time.monotonic()
    root = Path(root).resolve()
    native = root / '.local/native'
    runtime = native / 'runtime'
    plain(runtime)
    runtime.mkdir(parents=True, exist_ok=True)
    agent = runtime / 'agent'
    agent.mkdir(exist_ok=True)
    sources = sorted(file for file in (root / 'agent-python').glob('*.py') if not file.name.startswith('test_'))
    expected = {file.name for file in sources}
    for old in agent.glob('*.py'):
        if old.name not in expected:
            old.unlink()
    for file in sources:
        plain(file)
        shutil.copy2(file, agent / file.name)
    jar = root / 'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar'
    plain(jar)
    shutil.copy2(jar, runtime / 'app.jar')
    for name in ('models-manifest.json', 'models-NOTICE.json', 'assets.lock.json', 'python-requirements.lock.txt', 'person-requirements.lock.txt'):
        plain(native / name)
        shutil.copy2(native / name, runtime / name)
    for name in ('model-seed', 'model-sources'):
        source = native / name
        for file in source.rglob('*'):
            plain(file)
        shutil.copytree(source, runtime / name, dirs_exist_ok=True)
    licenses = runtime / 'licenses'
    licenses.mkdir(exist_ok=True)
    for name in ('LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md'):
        source = root / name
        plain(source)
        if not source.is_file():
            raise ValueError('license_notice_missing:' + name)
        shutil.copy2(source, licenses / name)
    (licenses / 'THIRD-PARTY-NOTICES.txt').write_text('Framewise first-party code: AGPL-3.0-only. See LICENSE, NOTICE and THIRD_PARTY_NOTICES.md. Components retain original licenses. Source-only review does not certify runtime redistribution.\n', encoding='utf-8')
    critical_names = list(REQUIRED)
    critical_names += [f'agent/{file.name}' for file in sources]
    critical_names += ['models-manifest.json', 'models-NOTICE.json']
    critical_names += ['python/python311.dll', 'person/python311.dll', 'java/lib/modules']
    critical = []
    for name in sorted(set(critical_names)):
        file = runtime / name
        plain(file)
        if not file.is_file():
            raise ValueError('required_runtime_file_missing:' + name)
        critical.append({'path': name, 'sha256': digest(file)})
    app_version = json.loads((root / 'desktop/package.json').read_text(encoding='utf-8-sig'))['version']
    if not isinstance(app_version, str) or not app_version:
        raise ValueError('invalid_app_version')
    manifest = {'version': 1, 'appVersion': app_version, 'critical': critical}
    target = runtime / 'runtime-manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    report = {'stage': 'native_assembled', 'runtime': str(runtime), 'agentFiles': len(sources), 'criticalFiles': len(critical), 'elapsedSeconds': round(time.monotonic()-start, 2)}
    print(json.dumps(report), flush=True)
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    assemble(parser.parse_args().root)
