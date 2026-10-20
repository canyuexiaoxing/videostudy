"""Compile the complete native Windows application into a per-user Inno installer.

The packaged folder is copied intact into versions/<version>. Older installed
versions remain available for explicit rollback; user data is never packaged or
removed. All .exe/.bin output slices must stay together during installation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_COMPILER = ROOT / '.local/dev/native-runtime/inno/ISCC.exe'
APP_ID = '11A814C4-205B-4EEB-A103-B8DA5D846E87'
RESERVE = 512 * 1024 * 1024


def plain_path(target: Path):
    for candidate in [target, *target.parents]:
        if candidate.is_symlink() or (candidate.exists() and getattr(candidate.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('symlink_or_junction_forbidden')


def sha256(target: Path):
    digest = hashlib.sha256()
    with target.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def valid_version(value: str):
    if not re.fullmatch(r'\d{1,5}\.\d{1,5}\.\d{1,5}(?:[-+][A-Za-z0-9.-]{1,48})?', value):
        raise ValueError('invalid_version')
    if any(int(part) > 65535 for part in value.split('-')[0].split('+')[0].split('.')):
        raise ValueError('version_component_too_large')
    return value


def absolute(value):
    target = Path(value)
    if not target.is_absolute():
        raise ValueError('absolute_path_required')
    plain_path(target)
    return target.resolve()


def payload(folder: Path):
    plain_path(folder)
    executable = folder / 'Framewise.exe'
    if not executable.is_file():
        raise ValueError('packaged_Framewise_exe_required')
    count = total = 0
    # os.walk visits each ancestor through this validated root. Checking every
    # ancestor again for every file turns a full native payload into millions
    # of Windows filesystem calls; inspect each entry once instead.
    def walk_error(error):
        raise error
    for directory, directories, files in os.walk(folder, followlinks=False, onerror=walk_error):
        file_names = set(files)
        for name in directories + files:
            file = Path(directory) / name
            metadata = file.lstat()
            if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400:
                raise ValueError('symlink_or_junction_forbidden')
            if name in file_names:
                if not stat.S_ISREG(metadata.st_mode):
                    raise ValueError('special_payload_file_forbidden')
                count += 1
                total += metadata.st_size
    return {'files': count, 'bytes': total}


def compile_installer(app_folder, output_dir, compiler=DEFAULT_COMPILER, version=None, app_id=APP_ID, app_name='Framewise', compression='lzma2/fast'):
    if compression not in {'lzma2/fast', 'zip/1', 'none'}:
        raise ValueError('invalid_compression_method')
    folder, output, compiler = absolute(app_folder), absolute(output_dir), absolute(compiler)
    if folder == output or folder in output.parents or output in folder.parents:
        raise ValueError('source_output_overlap')
    if not compiler.is_file():
        raise ValueError('inno_compiler_not_found')
    if not re.fullmatch(r'[A-Za-z0-9 -]{1,64}', app_name):
        raise ValueError('invalid_app_name')
    product_id = str(uuid.UUID(app_id)).upper()
    if version is None:
        version = json.loads((ROOT / 'desktop/package.json').read_text(encoding='utf-8-sig'))['version']
    version = valid_version(version)
    numeric = re.split(r'[-+]', version)[0] + '.0'
    scan_start = time.monotonic()
    details = payload(folder)
    scan_elapsed = round(time.monotonic() - scan_start, 2)
    print(json.dumps({'stage': 'installer_payload_scanned', **details, 'elapsedSeconds': scan_elapsed}), flush=True)
    output.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output).free < details['bytes'] + RESERVE:
        raise ValueError('insufficient_build_disk_space')
    output_name = f'{app_name.replace(" ", "-")}-{version}-windows-x64-Setup'
    build_folder = ROOT / '.local/native/installer-build' / (version + '-' + product_id[:8])
    plain_path(build_folder)
    build_folder.mkdir(parents=True, exist_ok=True)
    information = build_folder / 'upgrade-info.txt'
    information.write_text(
        'Framewise installs for the current Windows user.\n\n'
        'Courses, SQLite data, API key credentials, notes and downloaded models remain in the external application user data folder. Uninstall keeps these files.\n\n'
        'Before an upgrade, use Framewise Settings > Backup to export a complete application backup, including note images. The installer retains the previous binary version under the versions folder.\n\n'
        'If a new version fails, close Framewise, restore the pre-upgrade application backup using a compatible version, and launch PreviousExecutable from install-state.ini. Do not open a newer SQLite schema with an older binary without restoring the matching backup.\n\n'
        'All setup .exe and .bin files must stay in the same folder. The bundled third-party license notices are included with the application; no application source license is selected by this installer.\n', encoding='utf-8')
    compile_output = output / ('.compile-' + uuid.uuid4().hex)
    compile_output.mkdir()
    command = [str(compiler), '/Qp', '/DCompressionMethod=' + compression, '/DAppSource=' + str(folder), '/DOutputDirectory=' + str(compile_output), '/DAppVersion=' + version, '/DNumericVersion=' + numeric, '/DAppName=' + app_name, '/DProductGuid=' + product_id, '/DPayloadBytes=' + str(details['bytes']), '/DOutputName=' + output_name, '/DUpgradeInfo=' + str(information), str(ROOT / 'desktop/installer/framewise.iss')]
    start = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    compile_log = build_folder / 'compile.log'
    compile_log.write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
    attempt = {'stage': 'installer_compile', 'version': version, 'compression': compression, 'elapsedSeconds': round(time.monotonic()-start, 2), 'exitCode': result.returncode, 'endedAtUtc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    with (build_folder / 'attempts.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(attempt) + '\n')
    if result.returncode:
        raise RuntimeError(f'inno_compile_failed:{result.returncode}:{compile_log}')
    artifacts = sorted(compile_output.glob(output_name + '*'))
    if not any(file.suffix.lower() == '.exe' for file in artifacts):
        raise RuntimeError('installer_output_missing')
    for file in artifacts:
        plain_path(file)
        if file.suffix.lower() == '.bin' and file.stat().st_size > 1000000000:
            raise RuntimeError('installer_slice_too_large')
    promoted = []
    for file in artifacts:
        destination = output / file.name
        plain_path(destination)
        os.replace(file, destination)
        promoted.append(destination)
    compile_output.rmdir()
    artifacts = promoted
    report = {'format': 'framewise-installer-artifacts', 'version': 1, 'appVersion': version, 'appId': product_id, 'payload': details, 'payloadScanSeconds': scan_elapsed, 'compression': compression, 'installedRelativeExecutable': f'versions/{version}/Framewise.exe', 'previousVersionPolicy': 'retain-version-folders; matching application data backup is required for schema rollback', 'userDataPolicy': 'external; preserved by uninstall', 'compilerVersion': 'Inno Setup 7.1', 'elapsedSeconds': round(time.monotonic()-start, 2), 'files': [{'name': file.name, 'size': file.stat().st_size, 'sha256': sha256(file)} for file in artifacts if file.is_file()]}
    report_path = output / 'installer-artifacts.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'stage': 'installer_compiled', 'version': version, 'artifacts': len(report['files']), 'payloadBytes': details['bytes'], 'elapsedSeconds': report['elapsedSeconds'], 'report': str(report_path)}), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-folder', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--compiler', default=str(DEFAULT_COMPILER))
    parser.add_argument('--version')
    parser.add_argument('--app-id', default=APP_ID, help='Override only for isolated installer QA fixtures.')
    parser.add_argument('--app-name', default='Framewise', help='Override only for isolated installer QA fixtures.')
    parser.add_argument('--compression', choices=['lzma2/fast','zip/1','none'], default='lzma2/fast', help='Use none only for faster local acceptance rehearsal; release default is compressed.')
    args = parser.parse_args()
    compile_installer(args.app_folder, args.output_dir, args.compiler, args.version, args.app_id, args.app_name, args.compression)

