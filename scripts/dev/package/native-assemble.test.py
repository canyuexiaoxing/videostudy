import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('assembler', Path(__file__).with_name('native-assemble.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class AssemblyTests(unittest.TestCase):
    def fixture(self, root):
        for name in ('LICENSE','NOTICE','THIRD_PARTY_NOTICES.md'):(root/name).write_text('AGPL review fixture: '+name)
        (root/'desktop').mkdir()
        (root/'desktop/package.json').write_text('{"version":"0.3.0"}')
        for name in module.REQUIRED + ('python/python311.dll','person/python311.dll','java/lib/modules'):
            if name.startswith('agent/') or name == 'app.jar': continue
            target=root/'.local/native/runtime'/name
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'runtime')
        for name in ('native_bootstrap.py','native_process_host.py','app.py','test_private.py'):
            target=root/'agent-python'/name;target.parent.mkdir(exist_ok=True);target.write_text('pass')
        target=root/'backend-java/target/backend-java-0.1.0-SNAPSHOT.jar';target.parent.mkdir(parents=True);target.write_bytes(b'jar')
        for name in ('models-manifest.json','models-NOTICE.json','assets.lock.json','python-requirements.lock.txt','person-requirements.lock.txt'):
            (root/'.local/native'/name).write_text('{}')
        for name in ('model-seed','model-sources'):(root/'.local/native'/name).mkdir()
    def test_payload_excludes_tests_and_hashes_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root);module.assemble(root)
            runtime=root/'.local/native/runtime'
            self.assertFalse((runtime/'agent/test_private.py').exists())
            manifest=json.loads((runtime/'runtime-manifest.json').read_text())
            for entry in manifest['critical']:self.assertEqual(module.digest(runtime/entry['path']),entry['sha256'])
            self.assertTrue((runtime/'licenses/THIRD-PARTY-NOTICES.txt').is_file())
            for name in ('LICENSE','NOTICE','THIRD_PARTY_NOTICES.md'):
                self.assertEqual((root/name).read_bytes(),(runtime/'licenses'/name).read_bytes())
    def test_missing_runtime_fails_before_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root);(root/'.local/native/runtime/python/python.exe').unlink()
            with self.assertRaisesRegex(ValueError,'required_runtime_file_missing'):module.assemble(root)
            self.assertFalse((root/'.local/native/runtime/runtime-manifest.json').exists())

if __name__=='__main__':unittest.main()
