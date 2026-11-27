"""Test real updater with an isolated transport: no network or system changes."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

if sys.platform != 'linux':
    print('SKIP: Linux runner replacement tests')
    sys.exit(0)

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'internal/center/assets/manual/setup-release.py'


class SetupRelease(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='vc-setup-release-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.target=self.root/'setup.run'
        self.target.write_bytes(b'old runner');self.target.chmod(0o700)
        (self.root/'VERSION').write_text('0.3.0-alpha.48')
        (self.root/'software-client.json').write_text('{"enabled":true}')
        self.data=b'new runner, never executed'
        self.manifest=dict(version='0.3.0-alpha.49',sha256=hashlib.sha256(self.data).hexdigest(),bytes=len(self.data))
        self.calls=[];self.before_download=lambda:None
        test=self
        class Client:
            def __init__(self,config):pass
            def get(self,endpoint,params):
                test.calls.append(endpoint)
                if endpoint=='setup-release':return io.BytesIO(json.dumps(test.manifest).encode())
                test.before_download();return io.BytesIO(test.data)
        fake=types.ModuleType('software');fake.Client=Client;fake.HERE=str(self.root)
        fake.DownloadProgress=mock.Mock()
        patch=mock.patch.dict(sys.modules,{'software':fake});patch.start();self.addCleanup(patch.stop)
        spec=importlib.util.spec_from_file_location('setup_release_test',SOURCE)
        self.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.mod)
        # CI may run as an unprivileged account. Model root ownership only for
        # these fixture files; all real writes stay under this temporary root.
        original_stat=os.stat
        def owned(path,*args,**kwargs):
            st=original_stat(path,*args,**kwargs)
            if str(path).startswith(str(self.root)):
                values=list(st);values[4]=0;return os.stat_result(values)
            return st
        patch=mock.patch.object(self.mod.os,'stat',side_effect=owned);patch.start();self.addCleanup(patch.stop)
        original_lstat=os.lstat
        def lowned(path,*args,**kwargs):
            st=original_lstat(path,*args,**kwargs)
            if str(path).startswith(str(self.root)):
                values=list(st);values[4]=0;return os.stat_result(values)
            return st
        patch=mock.patch.object(self.mod.os,'lstat',side_effect=lowned);patch.start();self.addCleanup(patch.stop)

    def test_check_does_not_download_or_change_file(self):
        self.mod.execute('--check-version',str(self.target))
        self.assertEqual(self.calls,['setup-release']);self.assertEqual(self.target.read_bytes(),b'old runner')

    def test_verified_update_backup_and_idempotent_repeat(self):
        self.mod.execute('--update-setup',str(self.target))
        self.assertEqual(self.target.read_bytes(),self.data)
        backups=list(self.root.glob('setup.run.previous-*'));self.assertEqual(len(backups),1)
        self.assertEqual(backups[0].read_bytes(),b'old runner')
        self.assertEqual(self.target.stat().st_mode&0o777,0o700)
        self.mod.execute('--update-setup',str(self.target));self.assertEqual(len(list(self.root.glob('setup.run.previous-*'))),1)

    def test_current_transferred_runner_repairs_mode_and_stale_checksum(self):
        self.target.write_bytes(self.data);self.target.chmod(0o600)
        sidecar=Path(str(self.target)+'.sha256');sidecar.write_text('stale\n');sidecar.chmod(0o600)
        self.mod.execute('--update-setup',str(self.target))
        self.assertEqual(self.calls,['setup-release'])
        self.assertEqual(self.target.stat().st_mode&0o777,0o700)
        self.assertEqual(sidecar.read_text(),self.manifest['sha256']+'  setup.run\n')

    def test_sidecar_symlink_does_not_overwrite_other_files(self):
        other=self.root/'unrelated';other.write_bytes(b'preserve')
        Path(str(self.target)+'.sha256').symlink_to(other)
        with self.assertRaisesRegex(RuntimeError,'sidecar'):self.mod.execute('--update-setup',str(self.target))
        self.assertEqual(other.read_bytes(),b'preserve')
        self.assertEqual(self.target.read_bytes(),b'old runner')

    def test_bad_checksum_preserves_original(self):
        self.manifest['sha256']='a'*64
        with self.assertRaisesRegex(RuntimeError,'checksum'):self.mod.execute('--update-setup',str(self.target))
        self.assertEqual(self.target.read_bytes(),b'old runner');self.assertFalse(list(self.root.glob('.ventoy-setup-*')))

    def test_changed_target_is_not_overwritten(self):
        self.before_download=lambda:self.target.write_bytes(b'changed by operator')
        with self.assertRaisesRegex(RuntimeError,'changed'):self.mod.execute('--update-setup',str(self.target))
        self.assertEqual(self.target.read_bytes(),b'changed by operator')

    @unittest.skipIf(sys.platform=='win32','symlink permission varies on Windows')
    def test_symlink_and_writable_runner_rejected(self):
        link=self.root/'alias';link.symlink_to(self.target)
        with self.assertRaisesRegex(RuntimeError,'symlink'):self.mod.execute('--update-setup',str(link))
        self.target.chmod(0o666)
        with self.assertRaisesRegex(RuntimeError,'root-owned'):self.mod.execute('--update-setup',str(self.target))

    def test_disabled_center_and_unknown_action(self):
        (self.root/'software-client.json').write_text('{"enabled":false}')
        with self.assertRaisesRegex(RuntimeError,'not configured'):self.mod.execute('--update-setup',str(self.target))
        with self.assertRaisesRegex(ValueError,'Unknown'):self.mod.execute('--anything',str(self.target))


if __name__=='__main__':unittest.main()
