"""Installer checks. Set FRAMEWISE_INSTALLER_INTEGRATION=1 for actual isolated install/upgrade/uninstall QA."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('native_installer', Path(__file__).with_name('native-installer.py'))
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
QA_ID = '844C198D-E7D0-48FE-8308-B474D9FBACDF'


class InstallerUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='framewise-installer-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.app = self.base / 'App with spaces'
        self.app.mkdir()
        (self.app / 'Framewise.exe').write_bytes(b'fixture')

    def test_compression_rejects_preprocessor_injection(self):
        with self.assertRaisesRegex(ValueError, 'invalid_compression_method'):
            installer.compile_installer(self.app, self.base/'output', compression='none\n#define unsafe')

    def test_requires_absolute_source_and_output(self):
        with self.assertRaisesRegex(ValueError, 'absolute_path_required'):
            installer.absolute('relative/app')

    def test_version_prevents_path_and_preprocessor_injection(self):
        for value in ['../escape', '1.2', '1.2.3/evil', '1.2.3"', '65536.1.0', '1.2.3\n#define bad']:
            with self.assertRaises(ValueError):
                installer.valid_version(value)
        self.assertEqual(installer.valid_version('1.2.3-beta.1'), '1.2.3-beta.1')

    def test_payload_is_recursive_and_counts_license_files(self):
        nested = self.app / 'resources/runtime/licenses'
        nested.mkdir(parents=True)
        (nested / 'NOTICE.txt').write_bytes(b'upstream declaration')
        self.assertEqual(installer.payload(self.app), {'files': 2, 'bytes': 27})

    def test_missing_app_executable_rejected(self):
        (self.app / 'Framewise.exe').unlink()
        with self.assertRaisesRegex(ValueError, 'packaged_Framewise_exe_required'):
            installer.payload(self.app)

    def test_payload_symlinks_rejected(self):
        link = self.app / 'linked'
        try:
            link.symlink_to(self.app / 'Framewise.exe')
        except OSError:
            self.skipTest('symlink privilege unavailable')
        self.addCleanup(link.unlink)
        with self.assertRaisesRegex(ValueError, 'symlink_or_junction_forbidden'):
            installer.payload(self.app)

    def test_source_output_overlap_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source_output_overlap'):
            installer.compile_installer(self.app, self.app / 'output', installer.DEFAULT_COMPILER)

    def test_script_preserves_data_and_never_force_closes_apps(self):
        text = (installer.ROOT / 'desktop/installer/framewise.iss').read_text(encoding='utf-8-sig')
        self.assertIn('PrivilegesRequired=lowest', text)
        self.assertIn('CloseApplications=no', text)
        self.assertIn('skipifsilent', text)
        self.assertIn('DiskSliceSize=1000000000', text)
        self.assertIn('SavedPreviousExecutable', text)
        self.assertNotIn('[UninstallDelete]', text)
        self.assertNotIn('[InstallDelete]', text)
        self.assertNotIn('taskkill', text.lower())


@unittest.skipUnless(os.environ.get('FRAMEWISE_INSTALLER_INTEGRATION') == '1', 'explicit integration run required')
class InstallerIntegrationTests(unittest.TestCase):
    def test_actual_install_upgrade_uninstall_preserves_external_data(self):
        base = installer.ROOT / '.local/qa/native-delivery/installer-fixture'
        installer.plain_path(base)
        base.mkdir(parents=True, exist_ok=True)
        app = base / 'app'
        (app / 'resources/runtime/licenses').mkdir(parents=True, exist_ok=True)
        (app / 'resources/runtime/licenses/NOTICE.txt').write_text('Isolated installer QA fixture, no model weights.', encoding='utf-8')
        external = base / 'external-user-data'
        external.mkdir(exist_ok=True)
        notes = external / 'notes.json'
        notes.write_text('{"notes":["preserve note and image reference"]}', encoding='utf-8')
        before = installer.sha256(notes)
        installed = base / 'install-profile'
        output = base / 'output'
        commands = []
        for version in ['0.0.1', '0.0.2']:
            (app / 'Framewise.exe').write_text('fixture-only-do-not-launch-' + version, encoding='utf-8')
            report = installer.compile_installer(app, output, installer.DEFAULT_COMPILER, version, QA_ID, 'Framewise Installer QA')
            executable = output / next(item['name'] for item in report['files'] if item['name'].endswith('.exe'))
            command = [str(executable), '/CURRENTUSER', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/DIR=' + str(installed), '/LOG=' + str(base / ('install-' + version + '.log')), '/TASKS=']
            result = subprocess.run(command, capture_output=True, timeout=120, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.assertEqual(result.returncode, 0, f'install {version} failed; inspect QA log')
            self.assertTrue((installed / report['installedRelativeExecutable']).is_file())
            self.assertEqual(installer.sha256(notes), before)
            commands.append({'version': version, 'returncode': result.returncode})
            if version == '0.0.1':
                (installed / 'unowned-user-file.txt').write_text('not installer owned', encoding='utf-8')
        self.assertTrue((installed / 'versions/0.0.1/Framewise.exe').is_file())
        state_bytes = (installed / 'install-state.ini').read_bytes()
        state = state_bytes.decode('utf-16' if state_bytes.startswith((bytes([255, 254]), bytes([254, 255]))) else 'mbcs')
        self.assertIn('PreviousVersion=0.0.1', state)
        self.assertIn('CurrentVersion=0.0.2', state)
        uninstaller = installed / 'unins000.exe'
        result = subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/LOG=' + str(base / 'uninstall.log')], capture_output=True, timeout=120, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(installer.sha256(notes), before)
        self.assertEqual((installed / 'unowned-user-file.txt').read_text(encoding='utf-8'), 'not installer owned')
        self.assertFalse((installed / 'versions/0.0.1/Framewise.exe').exists())
        self.assertFalse((installed / 'versions/0.0.2/Framewise.exe').exists())
        (base / 'integration-result.json').write_text(json.dumps({'installs': commands, 'uninstallReturncode': result.returncode, 'externalNotesPreserved': True, 'unownedInstallFilePreserved': True, 'previousVersionRetainedDuringUpgrade': True, 'fixtureOnly': True}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    unittest.main()


