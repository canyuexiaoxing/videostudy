"""Pin local native model assets against official repository metadata; never download weights.

Run with Python 3.11+: python scripts/dev/package/native-model-catalog.py
Use --offline only after one successful online build to reuse frozen source evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[3]
HF_GROUPS = [
    ('asr', 'Systran/faster-whisper-small', 'faster-whisper-small', ['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt']),
    ('ocr-det', 'PaddlePaddle/PP-OCRv6_medium_det', 'paddleocr/PP-OCRv6_medium_det_infer', ['inference.json', 'inference.pdiparams', 'inference.yml']),
    ('ocr-rec', 'PaddlePaddle/PP-OCRv6_medium_rec', 'paddleocr/PP-OCRv6_medium_rec_infer', ['inference.json', 'inference.pdiparams', 'inference.yml']),
]
YOLO_URL = 'https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n-seg.pt'


def log(stage, **fields):
    print(json.dumps({'stage': stage, 'time': time.time(), **fields}), flush=True)


def no_links(target: Path):
    for candidate in [target, *target.parents]:
        if candidate.is_symlink() or getattr(candidate, 'is_junction', lambda: False)() or (candidate.exists() and getattr(candidate.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('symlink_or_junction_forbidden')


def hashes(file: Path):
    no_links(file)
    before = file.stat()
    size = before.st_size
    sha256 = hashlib.sha256()
    git_blob = hashlib.sha1(f'blob {size}\0'.encode())
    with file.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            sha256.update(block)
            git_blob.update(block)
    after = file.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_ino):
        raise ValueError('model_changed_during_hash')
    return {'size': size, 'sha256': sha256.hexdigest(), 'gitBlob': git_blob.hexdigest()}


def verify_hf_file(file: Path, metadata: dict):
    actual = hashes(file)
    if metadata.get('type') != 'file' or actual['size'] != metadata['size']:
        raise ValueError('official_size_mismatch')
    if metadata.get('lfs'):
        expected = metadata['lfs']['oid']
        if not re.fullmatch(r'[a-f0-9]{64}', expected) or actual['sha256'] != expected or metadata['lfs']['size'] != actual['size']:
            raise ValueError('official_lfs_sha256_mismatch')
        verification = {'kind': 'huggingface-lfs-sha256', 'digest': expected}
    else:
        expected = metadata['oid']
        if not re.fullmatch(r'[a-f0-9]{40}', expected) or actual['gitBlob'] != expected:
            raise ValueError('official_git_blob_mismatch')
        verification = {'kind': 'huggingface-git-blob-sha1', 'digest': expected}
    return actual, verification


def read_revision(directory: Path, names: list[str]):
    revisions = set()
    for name in names:
        metadata = directory / '.cache/huggingface/download' / (name + '.metadata')
        no_links(metadata)
        revision = metadata.read_text(encoding='utf-8').splitlines()[0]
        if not re.fullmatch(r'[a-f0-9]{40}', revision):
            raise ValueError('unpinned_huggingface_revision')
        revisions.add(revision)
    if len(revisions) != 1:
        raise ValueError('mixed_huggingface_revisions')
    return revisions.pop()


def fetch_bytes(url: str, *, max_size=8 * 1024 * 1024):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'huggingface.co', 'api.github.com', 'raw.githubusercontent.com', 'docs.ultralytics.com', 'www.ultralytics.com'}:
        raise ValueError('untrusted_metadata_url')
    proxies = {'https': 'http://127.0.0.1:7897'} if parsed.hostname in {'api.github.com', 'raw.githubusercontent.com', 'docs.ultralytics.com', 'www.ultralytics.com'} else {}
    request = urllib.request.Request(url, headers={'User-Agent': 'Framewise-model-catalog/1', 'Accept': 'application/json' if '/api/' in url or parsed.hostname == 'api.github.com' else '*/*'})
    for attempt in range(3):
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler(proxies)).open(request, timeout=30) as response:
                data = response.read(max_size + 1)
                if len(data) > max_size:
                    raise ValueError('metadata_too_large')
                return data
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def atomic_json(file: Path, value):
    no_links(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    temp = file.with_name(file.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        os.replace(temp, file)
    finally:
        temp.unlink(missing_ok=True)


def source_json(url, destination: Path, offline: bool):
    if offline:
        no_links(destination)
        cached = json.loads(destination.read_text(encoding='utf-8'))
        if cached.get('sourceUrl') != url:
            raise ValueError('source_evidence_url_mismatch')
        return cached['data']
    data = json.loads(fetch_bytes(url))
    atomic_json(destination, {'sourceUrl': url, 'retrievedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'data': data})
    return data


def source_text(url, destination: Path, offline: bool):
    if offline:
        no_links(destination)
        return destination.read_bytes()
    data = fetch_bytes(url)
    no_links(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return data


def build(root=ROOT, offline=False):
    source = root / '.local/models'
    output = root / '.local/native'
    evidence = output / 'model-sources'
    for directory in [source, output, evidence]:
        no_links(directory)
    evidence.mkdir(parents=True, exist_ok=True)
    files, notices, unresolved = [], [], []
    for group, repository, folder, names in HF_GROUPS:
        local = source / folder
        revision = read_revision(local, names)
        base = f'https://huggingface.co/{repository}/resolve/{revision}'
        metadata_url = f'https://huggingface.co/api/models/{repository}/tree/{revision}'
        tree = source_json(metadata_url, evidence / f'{group}-tree.json', offline)
        card_url = f'https://huggingface.co/api/models/{repository}/revision/{revision}'
        card = source_json(card_url, evidence / f'{group}-card.json', offline)
        if card.get('sha') != revision:
            raise ValueError('official_revision_mismatch')
        entries = {item['path']: item for item in tree}
        for name in names:
            if name not in entries:
                raise ValueError(f'official_file_missing:{group}:{name}')
            actual, verification = verify_hf_file(local / name, entries[name])
            relative = f'{folder}/{name}'
            files.append({'id': group + '-' + name.replace('.', '-'), 'relativePath': relative, 'url': base + '/' + urllib.parse.quote(name), 'size': actual['size'], 'sha256': actual['sha256'], 'group': group, 'repository': repository, 'revision': revision, 'verification': {**verification, 'source': metadata_url}})
            log('model_verified', group=group, file=name, bytes=actual['size'], verification=verification['kind'])
        readme_url = base + '/README.md'
        source_text(readme_url, evidence / f'{group}-README.md', offline)
        license_value = card.get('cardData', {}).get('license')
        if not license_value:
            unresolved.append({'group': group, 'reason': 'No license declaration returned by pinned repository card', 'source': card_url})
        notices.append({'group': group, 'repository': repository, 'revision': revision, 'declaredLicense': license_value, 'source': f'https://huggingface.co/{repository}/tree/{revision}', 'modelCard': readme_url, 'evidence': f'licenses/{group}-README.md'})

    # The original downloaded asset has independently recorded release digest provenance.
    provenance_file = source / 'yolo26/download.json'
    no_links(provenance_file)
    provenance = json.loads(provenance_file.read_text(encoding='utf-8-sig'))
    if provenance.get('source') != YOLO_URL or provenance.get('release') != 'v8.4.0' or provenance.get('verified_release_digest') is not True:
        raise ValueError('unverified_yolo_provenance')
    actual = hashes(source / 'yolo26/yolo26n-seg.pt')
    if actual['sha256'] != provenance['sha256'] or actual['size'] != provenance['size_bytes']:
        raise ValueError('yolo_local_digest_mismatch')
    release_url = 'https://api.github.com/repos/ultralytics/assets/releases/tags/v8.4.0'
    release = source_json(release_url, evidence / 'yolo-release.json', offline)
    asset = next((item for item in release['assets'] if item.get('name') == 'yolo26n-seg.pt'), None)
    if not asset or asset.get('browser_download_url') != YOLO_URL or asset.get('size') != actual['size'] or asset.get('digest') != 'sha256:' + actual['sha256']:
        raise ValueError('official_yolo_release_digest_mismatch')
    files.append({'id': 'person-yolo26n-seg', 'relativePath': 'yolo26/yolo26n-seg.pt', 'url': YOLO_URL, 'size': actual['size'], 'sha256': actual['sha256'], 'group': 'person', 'release': 'v8.4.0', 'verification': {'kind': 'github-release-sha256', 'digest': actual['sha256'], 'source': release_url}})
    docs_url = 'https://www.ultralytics.com/license'
    source_text(docs_url, evidence / 'yolo-license.html', offline)
    license_url = 'https://raw.githubusercontent.com/ultralytics/ultralytics/v8.4.0/LICENSE'
    source_text(license_url, evidence / 'yolo-LICENSE.txt', offline)
    notices.append({'group': 'person', 'declaredLicense': provenance.get('license'), 'source': YOLO_URL, 'licenseDocumentation': docs_url, 'licenseText': license_url, 'evidence': 'licenses/yolo-LICENSE.txt'})
    manifest = {'version': 1, 'generatedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'files': files, 'groups': [{'id': group, 'required': True} for group in ['asr', 'ocr-det', 'ocr-rec', 'person']], 'unresolvedSources': unresolved}
    notice = {'format': 'framewise-model-notices', 'version': 1, 'description': 'Upstream source and license declarations recorded for review. These records do not grant rights or provide a legal conclusion.', 'models': notices}
    stage = output / ('model-seed.' + uuid.uuid4().hex + '.tmp')
    no_links(stage)
    stage.mkdir()
    try:
        for entry in files:
            destination = stage / entry['relativePath']
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / entry['relativePath'], destination)
            verified = hashes(destination)
            if verified['sha256'] != entry['sha256'] or verified['size'] != entry['size']:
                raise ValueError('seed_copy_verification_failed')
        licenses = stage / 'licenses'
        licenses.mkdir()
        for group, *_ in HF_GROUPS:
            shutil.copyfile(evidence / f'{group}-README.md', licenses / f'{group}-README.md')
        shutil.copyfile(evidence / 'yolo-LICENSE.txt', licenses / 'yolo-LICENSE.txt')
        shutil.copyfile(evidence / 'yolo-license.html', licenses / 'yolo-license.html')
        atomic_json(stage / 'models-manifest.json', manifest)
        atomic_json(stage / 'NOTICE.json', notice)
        seed = output / 'model-seed'
        no_links(seed)
        old = None
        if seed.exists():
            old = output / ('model-seed.previous-' + uuid.uuid4().hex)
            seed.rename(old)
        try:
            stage.rename(seed)
        except Exception:
            if old is not None and not seed.exists():
                old.rename(seed)
            raise
        atomic_json(output / 'models-manifest.json', manifest)
        atomic_json(output / 'models-NOTICE.json', notice)
        log('catalog_complete', files=len(files), bytes=sum(entry['size'] for entry in files), unresolved=len(unresolved), offline=offline)
        return manifest
    except Exception:
        # Only a newly created, checked staging directory is eligible for cleanup.
        if stage.exists():
            no_links(stage)
            for candidate in stage.rglob('*'):
                no_links(candidate)
            shutil.rmtree(stage)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Reuse metadata frozen by a previous online verification; never access the network.')
    args = parser.parse_args()
    build(offline=args.offline)


