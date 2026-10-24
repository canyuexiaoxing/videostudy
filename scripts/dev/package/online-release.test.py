import importlib.util,json,tempfile,unittest,zipfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('online_release',Path(__file__).with_name('online-release.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ReleaseTests(unittest.TestCase):
 def test_base_requires_https_without_credentials_or_query(self):
  for value in ['http://example.com/releases/','https://user:pass@example.com/','https://example.com/x?token=x','https://example.com/x#y']:
   with self.assertRaises(ValueError):m.valid_base(value)
  self.assertEqual(m.valid_base('https://example.com/releases'),'https://example.com/releases/')
 def test_filename_blocks_traversal_and_reserved_windows_names(self):
  for value in ['../x.zip','a/b.zip','CON.zip','x.zip:stream','a\\x.zip','x.zip\n']:
   with self.assertRaises(ValueError):m.valid_name(value)
 def test_groups_keep_model_and_runtime_separate(self):
  self.assertEqual(m.component('resources/runtime/model-seed/a/model.bin'),'models')
  self.assertEqual(m.component('resources/runtime/person/Lib/torch.dll'),'person')
  self.assertEqual(m.component('resources/runtime/python/Lib/numpy/a.dll'),'inference')
  self.assertEqual(m.component('resources/app.asar'),'application')
 def test_zip_and_manifest_preserve_complete_fixture(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);source=root/'app';source.mkdir();(source/'Framewise.exe').write_bytes(b'exe')
   (source/'resources').mkdir();(source/'resources/app.asar').write_bytes(b'fixture')
   result=m.build_packages(source,root/'out',maximum_bytes=4)
   recovered={}
   for item in result:
    p=root/'out'/item['name'];self.assertEqual(m.sha256(p),item['sha256']);self.assertEqual(p.stat().st_size,item['size'])
    with zipfile.ZipFile(p) as z:
     for name in z.namelist():recovered[name]=z.read(name)
   self.assertEqual(recovered,{'Framewise.exe':b'exe','resources/app.asar':b'fixture'})
 def test_source_output_overlap_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'Framewise.exe').write_bytes(b'x')
   with self.assertRaises(ValueError):m.build_packages(root,root/'output')
 def test_existing_output_not_overwritten(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);src=root/'app';src.mkdir();(src/'Framewise.exe').write_bytes(b'x');out=root/'out';out.mkdir();(out/'sentinel').write_text('keep')
   with self.assertRaises(ValueError):m.build_packages(src,out)
   self.assertEqual((out/'sentinel').read_text(),'keep')
 def test_private_data_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);src=root/'app';src.mkdir();(src/'Framewise.exe').write_bytes(b'x');(src/'.env').write_text('private')
   with self.assertRaises(ValueError):m.build_packages(src,root/'out')
 def test_native_payload_checks_version_hash_and_path(self):
  with tempfile.TemporaryDirectory() as t:
   source=Path(t);runtime=source/'resources/runtime';runtime.mkdir(parents=True);payload=runtime/'agent.py';payload.write_bytes(b'fixture')
   manifest=runtime/'runtime-manifest.json'
   value={'appVersion':'0.3.1','critical':[{'path':'agent.py','sha256':m.sha256(payload)}]}
   manifest.write_text(json.dumps(value));m.validate_native_payload(source,'0.3.1')
   with self.assertRaises(ValueError):m.validate_native_payload(source,'0.3.2')
   payload.write_bytes(b'corrupt')
   with self.assertRaises(ValueError):m.validate_native_payload(source,'0.3.1')
   value['critical'][0]['path']='../escape';manifest.write_text(json.dumps(value))
   with self.assertRaises(ValueError):m.validate_native_payload(source,'0.3.1')
if __name__=='__main__':unittest.main()
