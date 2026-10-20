"""Unit checks for the model catalog integrity boundary (no model or network downloads)."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('native_model_catalog', Path(__file__).with_name('native-model-catalog.py'))
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


class ModelCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='framewise-catalog-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / 'model.bin'
        self.file.write_bytes(b'official model bytes')

    def test_lfs_sha256_and_size_must_match(self):
        sha = hashlib.sha256(self.file.read_bytes()).hexdigest()
        size = self.file.stat().st_size
        meta = {'type': 'file', 'size': size, 'lfs': {'oid': sha, 'size': size}}
        actual, verification = catalog.verify_hf_file(self.file, meta)
        self.assertEqual(actual['sha256'], sha)
        self.assertEqual(verification['kind'], 'huggingface-lfs-sha256')
        meta['lfs']['oid'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'official_lfs_sha256_mismatch'):
            catalog.verify_hf_file(self.file, meta)

    def test_plain_git_blob_hash_includes_git_header(self):
        data = self.file.read_bytes()
        oid = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
        meta = {'type': 'file', 'size': len(data), 'oid': oid}
        self.assertEqual(catalog.verify_hf_file(self.file, meta)[1]['digest'], oid)
        meta['oid'] = hashlib.sha1(data).hexdigest()
        with self.assertRaisesRegex(ValueError, 'official_git_blob_mismatch'):
            catalog.verify_hf_file(self.file, meta)

    def test_size_mismatch_fails_before_accepting_any_hash(self):
        with self.assertRaisesRegex(ValueError, 'official_size_mismatch'):
            catalog.verify_hf_file(self.file, {'type': 'file', 'size': 999, 'oid': '0' * 40})

    def test_offline_source_cache_must_match_expected_official_url(self):
        target = self.root / 'evidence.json'
        catalog.atomic_json(target, {'sourceUrl': 'https://huggingface.co/official', 'data': {'sha': 'pinned'}})
        self.assertEqual(catalog.source_json('https://huggingface.co/official', target, True)['sha'], 'pinned')
        with self.assertRaisesRegex(ValueError, 'source_evidence_url_mismatch'):
            catalog.source_json('https://huggingface.co/different', target, True)

    def test_revision_is_pinned_and_consistent_across_required_files(self):
        metadata = self.root / '.cache/huggingface/download'
        metadata.mkdir(parents=True)
        (metadata / 'a.metadata').write_text('a' * 40 + '\nhash\n0')
        (metadata / 'b.metadata').write_text('b' * 40 + '\nhash\n0')
        with self.assertRaisesRegex(ValueError, 'mixed_huggingface_revisions'):
            catalog.read_revision(self.root, ['a', 'b'])
        (metadata / 'b.metadata').write_text('main\nhash\n0')
        with self.assertRaisesRegex(ValueError, 'unpinned_huggingface_revision'):
            catalog.read_revision(self.root, ['b'])

    def test_untrusted_metadata_sources_never_fetch(self):
        for url in ['http://huggingface.co/a', 'file:///private', 'https://127.0.0.1/a', 'https://example.com/a']:
            with self.assertRaisesRegex(ValueError, 'untrusted_metadata_url'):
                catalog.fetch_bytes(url)

    def test_symlink_input_is_rejected(self):
        link = self.root / 'linked.bin'
        try:
            link.symlink_to(self.file)
        except OSError:
            self.skipTest('symlink privilege unavailable')
        self.addCleanup(link.unlink)
        with self.assertRaisesRegex(ValueError, 'symlink_or_junction_forbidden'):
            catalog.hashes(link)


if __name__ == '__main__':
    unittest.main()
