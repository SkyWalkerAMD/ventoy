"""Software-client boundaries; --native exercises real disposable RPM/DEB roots."""
import copy
import hashlib
import io
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.dont_write_bytecode = True
source = Path(sys.argv.pop()) if len(sys.argv) > 1 and sys.argv[-1].endswith('.py') else Path(__file__).resolve().parents[1] / 'internal/center/assets/manual/software.py'
spec = importlib.util.spec_from_file_location('software', source)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)

if (source.parent / 'fyhoct_install.py').is_file():
    sys.path.insert(0, str(source.parent))

class Boundaries(unittest.TestCase):
    def setUp(self):
        staging = tempfile.TemporaryDirectory()
        self.addCleanup(staging.cleanup)
        patcher = patch.object(client, 'STAGING', staging.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_download_reports_large_file_progress(self):
        data = b'x' * (10 * 1024**2)
        item = dict(path='group/large.tgz', size=len(data), sha256=hashlib.sha256(data).hexdigest())
        with tempfile.TemporaryDirectory() as tmp, patch('sys.stdout', new_callable=io.StringIO) as out:
            dest = Path(tmp) / 'large.tgz'
            transport = type('Transport', (), {'get': lambda *args: io.BytesIO(data)})()
            client.Client.download(transport, item, str(dest))
            self.assertIn('large.tgz 0.0 / 10.0 MiB (0%)', out.getvalue())
            self.assertIn('large.tgz 10.0 / 10.0 MiB (100%)', out.getvalue())
            self.assertEqual(dest.read_bytes(), data)

    @unittest.skipUnless((source.parent / 'uninstall.py').is_file(), 'requires full setup source')
    def test_uninstall_selects_owned_packages_and_unchanged_files(self):
        import uninstall
        wanted = dict(os='ubuntu', version='24.04', arch='amd64')
        before = {'existing:amd64': '1'}
        after = dict(before, **{'owned:amd64': '1'})
        packages = [dict(name=name, arch='amd64') for name in ('owned', 'existing')]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(client, 'STATE', tmp), patch.object(uninstall, 'software', client):
                with patch.object(client, 'installed', side_effect=[before, after]), patch.object(client, 'transaction'):
                    client.tracked_transaction(packages, 'deb', tmp)
                self.assertEqual(uninstall.package_targets(after, wanted, False), [('owned', 'amd64')])
                self.assertEqual(uninstall.package_targets(dict(after, **{'owned:amd64': '2'}), wanted, False), [])
                client.save_report(dict(target=wanted, packages=[dict(name='existing', version='1', arch='amd64')]))
                self.assertEqual(uninstall.package_targets(after, wanted, True), [('existing', 'amd64'), ('owned', 'amd64')])
                payload = b'managed'
                item = dict(path='tool.sh', size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
                client.save_json({'tool.sh': item}, 'archive-state.json')
                (root/'tool.sh').write_bytes(payload)
                with patch.object(client, 'ARCHIVES', os.path.realpath(tmp)):
                    self.assertEqual(uninstall.managed_archives(), [item])
                    (root/'tool.sh').write_bytes(b'edited')
                    self.assertEqual(uninstall.managed_archives(), [])
        self.assertEqual(uninstall.removal_commands('deb', [('owned', 'amd64')])[1],
                         ['dpkg', '--remove', 'owned:amd64'])

    @unittest.skipUnless((source.parent / 'fyhoct_install.py').is_file(), 'requires full setup source')
    def test_fyhoct_receives_verified_bundles_and_key_after_package_install(self):
        import fyhoct_install
        wanted = dict(os='rocky', version='9.2', arch='x86_64')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'software-client.json').write_text('{"enabled":true,"fyhoct_install":true}')
            names = ['sckoct-fyh-1.2.6-1.el9.x86_64.rpm', 'other-1.x86_64.rpm', *fyhoct_install.COMPONENTS]
            payload = b'fixture'
            entries = [dict(path=n, size=len(payload), sha256=hashlib.sha256(payload).hexdigest()) for n in names]
            group = dict(id='flat', **wanted, files=entries[:2])
            manifest = dict(schema=1, target=wanted, group=group, copy_files=entries[2:])
            events = []

            class FakeClient:
                def __init__(self, config): pass
                def manifest(self, target): return manifest
                def download(self, item, dest): Path(dest).write_bytes(payload)
                def get(self, endpoint, params):
                    self_test.assertEqual(endpoint, 'fyhoct-install')
                    events.append('key')
                    return io.BytesIO(json.dumps({'enabled': True, 'key': 'K'*32}).encode())

            self_test = self
            package = dict(name='sckoct-fyh', version='0:1.2.6-1.el9', arch='x86_64', target_arch='x86_64')

            def metadata(path, *args):
                return dict(package, name='other' if Path(path).name == names[1] else package['name'])

            def transaction(packages, *args, **kwargs):
                events.append([p['name'] for p in packages])
                return len(packages)

            def configure(directory, key):
                self.assertEqual(key, 'K'*32)
                for name in fyhoct_install.COMPONENTS:
                    self.assertEqual((Path(directory)/name).read_bytes(), payload)
                events.append('components')

            with patch.object(client, 'HERE', str(root)), patch.object(client, 'STATE', str(root/'state')), \
                 patch.object(client, 'ARCHIVES', str(root/'files')), patch.object(client, 'Client', FakeClient), \
                 patch.object(client, 'target', return_value=wanted), patch.object(client, 'metadata', side_effect=metadata), \
                 patch.object(client, 'transaction', side_effect=transaction), \
                 patch.object(client, 'verify'), patch.object(client, 'installed', return_value={}), \
                 patch.object(fyhoct_install, 'configure', side_effect=configure):
                client.execute('--list-software')
                self.assertEqual(events, [])
                client.execute('--install-fyhoct')
                self.assertEqual(events, ['key', ['sckoct-fyh'], 'components'])
                self.assertFalse((root/'files'/names[1]).exists())
                self.assertFalse((root/'state/last-result.json').exists())
                events.clear()
                client.execute('--software')
            self.assertEqual(events, [['other']])
            report = (root/'state/last-result.json').read_text()
            self.assertEqual([p['name'] for p in json.loads(report)['copy_only_packages']], ['sckoct-fyh'])
            self.assertNotIn('K'*32, report)

    def test_package_files_persist_backfill_and_retry(self):
        for family, wanted in [('deb', dict(os='ubuntu', version='22.04', arch='amd64')),
                               ('rpm', dict(os='rocky', version='9', arch='x86_64'))]:
            with self.subTest(family=family), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root/'software-client.json').write_text('{"enabled":true}')
                name = 'app_1_amd64.deb' if family == 'deb' else 'app-1.x86_64.rpm'
                prefix = '/'.join([wanted['os'], wanted['version'], wanted['arch'], 'default'])
                payload = b'fixture package bytes'
                item = dict(path=prefix+'/'+name, size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
                group = dict(id=prefix, **wanted, files=[item])
                manifest = dict(schema=1, target=wanted, group=group)
                client.validate_manifest(manifest, wanted)
                downloads, installs = [], []
                class FakeClient:
                    def __init__(self, config): pass
                    def manifest(self, target): return manifest
                    def download(self, file, dest):
                        downloads.append(file['path'])
                        Path(dest).write_bytes(payload)
                package = dict(name='app', version='1', arch=wanted['arch'], target_arch=wanted['arch'])
                def metadata(path, *args):
                    self.assertEqual(Path(path).read_bytes(), payload)
                    return dict(package, file=path)
                def install(packages, *args, **kwargs):
                    self.assertEqual(Path(packages[0]['file']), root/'files'/name)
                    installs.append(1)
                    return 1
                with patch.object(client, 'HERE', str(root)), patch.object(client, 'STATE', str(root/'state')), \
                     patch.object(client, 'ARCHIVES', str(root/'files')), patch.object(client, 'Client', FakeClient), \
                     patch.object(client, 'target', return_value=wanted), patch.object(client, 'metadata', side_effect=metadata), \
                     patch.object(client, 'transaction', side_effect=install) as transaction, \
                     patch.object(client, 'verify'), patch.object(client, 'installed', return_value={}):
                    client.execute('--list-software')
                    self.assertFalse((root/'files').exists())
                    client.execute('--software')
                    saved = root/'files'/name
                    self.assertEqual(saved.read_bytes(), payload)
                    self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
                    report_path = root/'state/last-result.json'
                    report = json.loads(report_path.read_text())
                    self.assertEqual(report['package_files'], [item])
                    self.assertNotIn('file', report['packages'][0])
                    client.execute('--check-software')
                    client.execute('--software')
                    self.assertEqual((len(downloads), len(installs)), (1, 1))
                    saved.unlink()
                    with self.assertRaises(RuntimeError): client.execute('--check-software')
                    # Upgrade from a report written by the old temporary-only setup.
                    report.pop('package_files')
                    report_path.write_text(json.dumps(report))
                    client.execute('--software')
                    self.assertEqual((len(downloads), len(installs)), (2, 1))
                    self.assertEqual(saved.read_bytes(), payload)
                    saved.write_bytes(b'user modified package')
                    with self.assertRaisesRegex(RuntimeError, 'modified or is unmanaged'):
                        client.execute('--software')
                    self.assertEqual(saved.read_bytes(), b'user modified package')
                    self.assertEqual(len(installs), 1)
                    saved.write_bytes(payload)
                    # A failed native transaction retains the verified package for retry.
                    transaction.side_effect = RuntimeError('native install failed')
                    with self.assertRaisesRegex(RuntimeError, 'native install failed'):
                        client.execute('--software')
                    self.assertEqual(saved.read_bytes(), payload)
                    self.assertEqual(json.loads(report_path.read_text())['status'], 'failed')
                    transaction.side_effect = install
                    client.execute('--software')
                    self.assertEqual(len(downloads), 2)
                    client.execute('--check-software')

    def test_rpm_scriptlet_failure_with_success_exit_is_not_verified(self):
        warning = ('warning: %post(broken-app-1:1.1.8-1.el10.x86_64) '
                   'scriptlet failed, exit status 1\n'
                   'Error in POSTIN scriptlet in rpm package broken-app\nComplete!')
        package = dict(name='broken-app', arch='x86_64', version='1:1.1.8-1.el10')
        current = {'broken-app:x86_64': package['version']}
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, 'STATE', tmp), \
             patch.object(client, 'installed', return_value=current):
            with patch.object(client, 'run', return_value=warning):
                with self.assertRaisesRegex(RuntimeError, 'installation script failed'):
                    client.run_rpm_transaction(['/usr/bin/dnf', 'install', 'package.rpm'])
            failure = json.loads((Path(tmp)/'rpm-scriptlet-failures.json').read_text())
            self.assertEqual(failure['packages'], current)
            self.assertFalse(failure['unknown'])
            # Both read-only checks and unchanged reruns must retain failure.
            with self.assertRaisesRegex(RuntimeError, 'Unresolved RPM'):
                client.verify([package], 'rpm')
            with patch.object(client, 'run', side_effect=AssertionError('must not reinstall')):
                with self.assertRaisesRegex(RuntimeError, 'Unresolved RPM'):
                    client.transaction([package], 'rpm', tmp)
            current['broken-app:x86_64'] = '1:1.1.9-1.el10'
            fixed = dict(package, version='1:1.1.9-1.el10')
            client.verify([fixed], 'rpm')

    def test_copy_only_failure_is_preserved_but_not_certified(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, 'STATE', tmp):
            marker = Path(tmp)/'rpm-scriptlet-failures.json'
            current = {'sckoct-fyh:x86_64': '1:1.1.8-1.el10'}
            original = json.dumps(dict(packages=current, unknown=False, errors=['prior post failure']))
            marker.write_text(original)
            with patch.object(client, 'installed', return_value=current):
                client.verify([], 'rpm')
                package = dict(name='sckoct-fyh', arch='x86_64', version='1:1.1.8-1.el10')
                with self.assertRaisesRegex(RuntimeError, 'cannot be certified'):
                    client.verify([package], 'rpm')
                with self.assertRaisesRegex(RuntimeError, 'must not enter'):
                    client.transaction([package], 'rpm', tmp)
                self.assertEqual(marker.read_text(), original)
                current['another-app:x86_64'] = '1:1-1'
                marker.write_text(json.dumps(dict(packages=current, unknown=False, errors=[])))
                with self.assertRaisesRegex(RuntimeError, 'Unresolved RPM'):
                    client.verify([], 'rpm')

    def test_copy_only_delivery_reclassifies_legacy_cache_and_skips_upgrades(self):
        for family, wanted in [('deb', dict(os='ubuntu', version='24.04', arch='amd64')),
                               ('rpm', dict(os='rocky', version='10.2', arch='x86_64'))]:
            with self.subTest(family=family), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root/'software-client.json').write_text('{"enabled":true}')
                prefix = '/'.join([wanted['os'], wanted['version'], wanted['arch'], 'default'])
                names = ['ordinary-app'] + list(client.COPY_ONLY_PACKAGES)
                payloads = dict(('renamed-%d.%s' % (i, family), (name+' v1').encode()) for i, name in enumerate(names))
                items = [dict(path=prefix+'/'+file, size=len(data), sha256=hashlib.sha256(data).hexdigest()) for file, data in payloads.items()]
                group = dict(id=prefix, **wanted, files=items)
                manifest = dict(schema=1, target=wanted, group=group)
                client.validate_manifest(manifest, wanted)
                downloads, installs = [], []
                class FakeClient:
                    def __init__(self, config): pass
                    def manifest(self, target): return manifest
                    def download(self, item, dest):
                        downloads.append(item['path'])
                        Path(dest).write_bytes(payloads[Path(dest).name] if Path(dest).name in payloads else payloads[item['path'].rsplit('/', 1)[-1]])
                def metadata(path, *args):
                    name, version = Path(path).read_text().split()
                    return dict(name=name, version=version, arch=wanted['arch'], target_arch=wanted['arch'], file=path)
                def install(packages, *args, **kwargs):
                    installs.append([p['name'] for p in packages])
                    self.assertEqual(installs[-1], ['ordinary-app'])
                    return 1
                (root/'state').mkdir()
                report_path = root/'state/last-result.json'
                report_path.write_text(json.dumps(dict(status='verified', target=wanted, manifest=manifest,
                    packages=[dict(name=n, version='v1', arch=wanted['arch']) for n in names])))
                with patch.object(client, 'HERE', str(root)), patch.object(client, 'STATE', str(root/'state')), \
                     patch.object(client, 'ARCHIVES', str(root/'files')), patch.object(client, 'Client', FakeClient), \
                     patch.object(client, 'target', return_value=wanted), patch.object(client, 'metadata', side_effect=metadata), \
                     patch.object(client, 'transaction', side_effect=install), patch.object(client, 'verify'), \
                     patch.object(client, 'installed', return_value={}):
                    with self.assertRaisesRegex(RuntimeError, 'policy changed'):
                        client.execute('--check-software')
                    client.execute('--software')
                    report = json.loads(report_path.read_text())
                    self.assertEqual([p['name'] for p in report['packages']], ['ordinary-app'])
                    self.assertEqual([p['name'] for p in report['copy_only_packages']], list(client.COPY_ONLY_PACKAGES))
                    self.assertEqual(len(downloads), 4)
                    client.execute('--check-software')
                    client.execute('--software')
                    self.assertEqual((len(installs), len(downloads)), (1, 4))
                    for filename in payloads:
                        self.assertEqual((root/'files'/filename).read_bytes(), payloads[filename])
                    # A new excluded version is copied without entering the transaction.
                    for item in items[1:]:
                        filename = item['path'].rsplit('/', 1)[-1]
                        payloads[filename] = payloads[filename].replace(b'v1', b'v2')
                        item['sha256'] = hashlib.sha256(payloads[filename]).hexdigest()
                    client.execute('--software')
                    self.assertEqual(len(downloads), 7)
                    self.assertTrue(all(p['version']=='v2' for p in json.loads(report_path.read_text())['copy_only_packages']))
                    client.execute('--check-software')

    def test_apt_refuses_copy_only_dependency_or_pending_configuration(self):
        for operation in ('Inst', 'Conf'):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp, \
                 patch.object(client, 'installed', return_value={}), \
                 patch.object(client, 'run', return_value=operation+' sckoct-fyh:amd64 (1.1.8)') as run:
                with self.assertRaisesRegex(RuntimeError, 'copy-only package'):
                    client.transaction([dict(name='ordinary', arch='amd64', version='1', file='/tmp/app.deb')], 'deb', tmp)
                self.assertEqual(run.call_count, 1)
                self.assertIn('--simulate', run.call_args.args[0])

    def test_dnf_excludes_copy_only_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, 'installed', return_value={}), \
             patch.object(client.os.path, 'isfile', return_value=True), patch.object(client, 'verify'), \
             patch.object(client, 'run', side_effect=[RuntimeError('missing dependency'), 'test ok']), \
             patch.object(client, 'run_rpm_transaction') as apply:
            client.transaction([dict(name='ordinary', arch='x86_64', version='1', file='/tmp/app.rpm')], 'rpm', tmp)
            for name in client.COPY_ONLY_PACKAGES:
                self.assertIn('--exclude='+name, apply.call_args.args[0])

    def test_rpm_scriptlet_nonzero_and_unknown_failures(self):
        for text in ('error: %post(app-1-1.noarch) scriptlet failed, exit status 1',
                     'error: failed to exec scriptlet interpreter /bin/sh: Permission denied'):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp, \
                 patch.object(client, 'STATE', tmp), patch.object(client, 'installed', return_value={}):
                error = RuntimeError('rpm failed'); error.output = text
                with patch.object(client, 'run', side_effect=error):
                    with self.assertRaisesRegex(RuntimeError, 'installation script failed'):
                        client.run_rpm_transaction(['rpm', '-Uvh', 'package.rpm'])
                with self.assertRaisesRegex(RuntimeError, 'Unresolved RPM'):
                    client.verify([], 'rpm')

    def test_successful_rpm_output_does_not_create_failure(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, 'STATE', tmp), \
             patch.object(client, 'run', return_value='Running scriptlet: app-1-1.noarch\nComplete!'):
            client.run_rpm_transaction(['rpm', '-Uvh', 'package.rpm'])
            client.check_rpm_scriptlets({})
            self.assertFalse((Path(tmp)/'rpm-scriptlet-failures.json').exists())

    def test_copy_file_manifest(self):
        wanted = dict(os='ubuntu', version='22.04', arch='amd64')
        item = dict(path='centos_opt_static', size=10, sha256='0'*64)
        manifest = dict(schema=1, target=wanted, group=None, copy_files=[item])
        client.validate_manifest(manifest, wanted)
        for name in ('ubuntu-optimize.sh.x', 'driver.tar.xz', 'README.txt'):
            good = copy.deepcopy(manifest); good['copy_files'][0]['path'] = name
            client.validate_manifest(good, wanted)
        for name in ('../tool', 'dir/tool', 'tool\\x', '.hidden', 'tool\n', 'app.deb', 'app.rpm',
                     'onload.tgz', 'app.tar.gz', 'app.zip', 'tool.part', 'tool.partial',
                     'tool.tmp', 'tool.download', 'tool.crdownload', 'tool.swp', 'tool.bak', 'tool~',
                     'ventoy-linux-setup.run', 'ventoy-linux-setup.run.sha256'):
            bad = copy.deepcopy(manifest); bad['copy_files'][0]['path'] = name
            with self.assertRaises(RuntimeError): client.validate_manifest(bad, wanted)
        for count in (2, 257):
            bad = copy.deepcopy(manifest); bad['copy_files'] *= count
            with self.assertRaises(RuntimeError): client.validate_manifest(bad, wanted)

    def test_archive_manifest(self):
        target = dict(os='ubuntu', version='24.04', arch='amd64')
        item = dict(path='ipmitool-1.8.19.tar.gz', size=10, sha256='0'*64)
        manifest = dict(schema=1, target=target, group=None, archives=[item])
        client.validate_manifest(manifest, target)
        for name in ('onload-7.1.3.202.tgz', 'onload-8.1.3.40.tgz', 'exanic-software.zip'):
            supported = copy.deepcopy(manifest); supported['archives'][0]['path'] = name
            client.validate_manifest(supported, target)
        for key, value in [('path', '../app.tar.gz'), ('path', 'nested/app.tar.gz'),
                           ('path', '../app.tgz'), ('path', 'nested/app.zip'),
                           ('path', 'app.tgz.part'), ('path', 'app.zip.part'),
                           ('path', 'app.zip\n'), ('path', 'app.tgz\n'),
                           ('path', 'app.deb'), ('path', 'app.tar.gz\n'), ('size', 0),
                           ('size', 2**40), ('sha256', 'bad')]:
            bad = copy.deepcopy(manifest); bad['archives'][0][key] = value
            with self.assertRaises(RuntimeError): client.validate_manifest(bad, target)
        bad = copy.deepcopy(manifest); bad['archives'] *= 2
        with self.assertRaises(RuntimeError): client.validate_manifest(bad, target)

    @unittest.skipIf(sys.platform == 'win32', 'Linux file ownership and atomic replacement')
    def test_archive_transfer_repeat_replace_and_protection(self):
        # Includes a path-traversing tar member; delivery must preserve the raw
        # bytes without ever extracting or executing anything from the archive.
        import io, tarfile
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as t:
            entry = tarfile.TarInfo('../../must-not-be-extracted')
            entry.size = 4; t.addfile(entry, io.BytesIO(b'data'))
        payload = stream.getvalue()
        class FakeClient:
            calls = 0
            fail = False
            def download(self, item, dest):
                self.calls += 1
                Path(dest).write_bytes(payload)
                if self.fail: raise RuntimeError('transfer interrupted')
        api = FakeClient()
        def item(data): return dict(path='ipmitool.tar.gz', size=len(data), sha256=hashlib.sha256(data).hexdigest())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(client, 'ARCHIVES', str(root/'files')), patch.object(client, 'STATE', str(root/'state')):
                client.sync_archives(api, [item(payload)])
                dest = root/'files/ipmitool.tar.gz'
                self.assertEqual(dest.read_bytes(), payload)
                self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
                self.assertEqual(sorted(x.name for x in (root/'files').iterdir()), ['ipmitool.tar.gz'])
                client.verify_archives([item(payload)])
                client.sync_archives(api, [item(payload)])
                self.assertEqual(api.calls, 1)
                old = payload; payload = b'new raw archive bytes'
                api.fail = True
                with self.assertRaises(RuntimeError): client.sync_archives(api, [item(payload)])
                self.assertEqual(dest.read_bytes(), old)
                api.fail = False
                client.sync_archives(api, [item(payload)])
                self.assertEqual(dest.read_bytes(), payload)
                dest.write_bytes(b'user-modified')
                with self.assertRaises(RuntimeError): client.verify_archives([item(payload)])
                with self.assertRaises(RuntimeError): client.sync_archives(api, [item(payload)])
                self.assertEqual(dest.read_bytes(), b'user-modified')
                dest.unlink(); outside=root/'outside'; outside.write_bytes(payload); dest.symlink_to(outside)
                with self.assertRaises(RuntimeError): client.sync_archives(api, [item(payload)])
                self.assertEqual(outside.read_bytes(), payload)
                dest.unlink(); (root/'files').rmdir(); (root/'files').symlink_to(root, target_is_directory=True)
                with self.assertRaises(RuntimeError): client.sync_archives(api, [item(payload)])

    @unittest.skipIf(sys.platform == 'win32', 'Linux filesystem delivery')
    def test_archive_only_execution_and_readonly_check(self):
        wanted = dict(os='ubuntu', version='24.04', arch='amd64')
        payload = b'archive-only'
        archives = [dict(path=name, size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
                    for name in ('tools.tar.gz', 'onload.tgz', 'exanic.zip')]
        copies = [dict(path=name, size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
                  for name in ('centos_opt_static', 'ubuntu-optimize.sh.x')]
        manifest = dict(schema=1, target=wanted, group=None, archives=archives, copy_files=copies)
        class FakeClient:
            def __init__(self, config): pass
            def manifest(self, target): return manifest
            def download(self, item, dest): Path(dest).write_bytes(payload)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'software-client.json').write_text('{"enabled": true}')
            with patch.object(client, 'ARCHIVES', str(root/'files')), patch.object(client, 'STATE', str(root/'state')), \
                 patch.object(client, 'HERE', str(root)), patch.object(client, 'target', return_value=wanted), \
                 patch.object(client, 'Client', FakeClient), patch.object(client, 'installed', return_value={}), \
                 patch.object(client, 'run', side_effect=AssertionError('unexpected package command')):
                client.execute('--list-software')
                self.assertFalse((root/'files').exists())
                client.execute('--software')
                report = json.loads((root/'state/last-result.json').read_text())
                self.assertEqual((report['status'], report['packages'], report['archives']), ('verified', [], archives + copies))
                self.assertEqual(sorted(p.name for p in (root/'files').iterdir()), ['centos_opt_static', 'exanic.zip', 'onload.tgz', 'tools.tar.gz', 'ubuntu-optimize.sh.x'])
                client.execute('--check-software')
                client.execute('--software')
                manifest['archives'] = []
                client.execute('--software')
                client.execute('--check-software')
                (root/'files/ubuntu-optimize.sh.x').write_bytes(b'user changed tool')
                with self.assertRaises(RuntimeError): client.execute('--software')
                self.assertEqual((root/'files/ubuntu-optimize.sh.x').read_bytes(), b'user changed tool')
                (root/'files/ubuntu-optimize.sh.x').write_bytes(payload)
                manifest['archives'] = archives
                client.execute('--software')
                (root/'files/tools.tar.gz').unlink()
                with self.assertRaises(RuntimeError): client.execute('--check-software')

    def test_manifest_boundaries(self):
        target = dict(os='ubuntu', version='22.04', arch='amd64')
        group = dict(id='auto/ubuntu/22.04/amd64/default', **target, files=[dict(path='app_1_amd64.deb', size=10, sha256='0'*64)])
        manifest = dict(schema=1, target=target, group=group)
        client.validate_manifest(manifest, target)
        for key, value in [('path', '../app.deb'), ('path', '/etc/app.deb'), ('path', 'app.rpm'), ('size', 0), ('size', 2**40), ('sha256', 'wrong')]:
            bad = copy.deepcopy(manifest)
            bad['group']['files'][0][key] = value
            with self.assertRaises(RuntimeError): client.validate_manifest(bad, target)
        for key, value in [('os','debian'), ('version','24.04'), ('arch','arm64')]:
            bad = copy.deepcopy(manifest); bad['group'][key] = value
            with self.assertRaises(RuntimeError): client.validate_manifest(bad,target)
        bad = copy.deepcopy(manifest);bad['group']['files'] *= 2
        with self.assertRaises(RuntimeError): client.validate_manifest(bad,target)

    def test_transport_integrity_and_no_redirect(self):
        class Handler(BaseHTTPRequestHandler):
            redirect = False
            def do_GET(self):
                if self.headers.get('Authorization') != 'Bearer '+'a'*64:
                    self.send_error(401);return
                if self.redirect:
                    self.send_response(302); self.send_header('Location', 'http://example.invalid/secret');self.end_headers();return
                self.send_response(200); self.end_headers();self.wfile.write(b'content')
            def log_message(self,*args): pass
        server = HTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            api = client.Client(dict(url='http://127.0.0.1:'+str(server.server_port),token='a'*64))
            with tempfile.TemporaryDirectory() as temp:
                item=dict(path='app_1_amd64.deb',size=7,sha256=hashlib.sha256(b'content').hexdigest())
                dest=str(Path(temp)/'package');api.download(item,dest)
                self.assertEqual(Path(dest).read_bytes(),b'content')
                item['sha256']='0'*64
                with self.assertRaises(RuntimeError):api.download(item,dest)
                item['size']=1
                with self.assertRaises(RuntimeError):api.download(item,dest)
                Handler.redirect=True
                with self.assertRaises(RuntimeError):api.download(item,dest)
            with self.assertRaises(RuntimeError):client.Client(dict(url='http://192.168.1.2',token='a'*64))
        finally:
            server.shutdown();server.server_close()


def native():
    assert os.geteuid()==0 and Path('/run/ventoy-policy-disposable-root').is_file(), 'Disposable container marker required'
    family='deb' if Path('/usr/bin/dpkg').is_file() else 'rpm'
    arch=client.target()['arch']
    def run(args): return subprocess.check_output(args,stderr=subprocess.STDOUT,universal_newlines=True)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        def package(name,dependency='',version='1',bad_post=False):
            if family=='deb':
                d=root/(name+'-'+version); (d/'DEBIAN').mkdir(parents=True)
                (d/'DEBIAN/control').write_text('Package: '+name+'\nVersion: '+version+'\nArchitecture: all\nMaintainer: QA <qa@example.invalid>\nDescription: disposable software client test\n'+('Depends: '+dependency+'\n' if dependency else ''))
                content=d/'usr/share'/name;content.mkdir(parents=True);(content/'version').write_text(version)
                out=root/(name+'_'+version+'_all.deb');run(['dpkg-deb','--build',str(d),str(out)]);return str(out)
            spec=root/(name+'.spec')
            spec.write_text('Name: '+name+'\nVersion: '+version+'\nRelease: 1\nSummary: software QA\nLicense: MIT\nBuildArch: noarch\n'+('Requires: '+dependency+'\n' if dependency else '')+'%description\nDisposable QA\n%install\nmkdir -p %{buildroot}/usr/share/%{name}\necho %{version} > %{buildroot}/usr/share/%{name}/version\n%files\n/usr/share/%{name}/version\n'+('%post\nexit 1\n' if bad_post else ''))
            run(['rpmbuild','--define','_topdir '+str(root/'build'),'-bb',str(spec)])
            return str(root/'build/RPMS/noarch'/(name+'-'+version+'-1.noarch.rpm'))
        lib=package('ventoy-qa-lib');app=package('ventoy-qa-app','ventoy-qa-lib');broken=package('ventoy-qa-broken','ventoy-qa-missing')
        kernel=package('kernel-ventoy-qa')
        with unittest.TestCase().assertRaises(RuntimeError):client.metadata(kernel,family,arch)
        baseline=client.installed(family)
        pkgs=[client.metadata(f,family,arch) for f in (app,lib)]
        assert client.transaction(pkgs,family,str(root/'transaction'),False)==2
        assert client.transaction(pkgs,family,str(root/'repeat'),False)==0
        newer=client.metadata(package('ventoy-qa-app','ventoy-qa-lib','1.10'),family,arch)
        middle=client.metadata(package('ventoy-qa-app','ventoy-qa-lib','1.9'),family,arch)
        chosen=client.select_latest([pkgs[0],newer,middle],family,arch)
        assert len(chosen)==1 and chosen[0]['version']==newer['version'],'must use native version ordering'
        assert client.transaction(chosen,family,str(root/'upgrade'),False)==1
        assert client.transaction(pkgs,family,str(root/'no-downgrade'),False)==0
        bad=[client.metadata(broken,family,arch)]
        before=client.installed(family)
        with unittest.TestCase().assertRaises(RuntimeError):client.transaction(bad,family,str(root/'broken'),False)
        assert client.installed(family)==before,'dependency failure changed installed packages'
        if family=='rpm':
            broken_post=client.metadata(package('ventoy-qa-scriptlet',bad_post=True),family,arch)
            with unittest.TestCase().assertRaisesRegex(RuntimeError,'script failed'):
                client.transaction([broken_post],family,str(root/'post-failure'),False)
            assert 'ventoy-qa-scriptlet:noarch' in client.installed(family)
            with unittest.TestCase().assertRaisesRegex(RuntimeError,'Unresolved RPM'):
                client.transaction([broken_post],family,str(root/'post-repeat'),False)
            corrected=client.metadata(package('ventoy-qa-scriptlet',version='2'),family,arch)
            assert client.transaction([corrected],family,str(root/'post-fixed'),False)==1
            # Exercise yum/dnf's real dependency fallback against a private file
            # repository, without relying on a public mirror for test packages.
            repo=root/'repo';repo.mkdir()
            shutil.copyfile(package('ventoy-qa-repo-lib'),repo/'library.rpm')
            shutil.copyfile(package('ventoy-qa-scriptlet-repo-lib'),repo/'scriptlet-library.rpm')
            dependent=client.metadata(package('ventoy-qa-repo-app','ventoy-qa-repo-lib'),family,arch)
            run(['createrepo_c',str(repo)])
            repo_dir=Path('/etc/yum.repos.d');repo_dir.mkdir(exist_ok=True)
            moved=[];config=repo_dir/'ventoy-software-qa.repo'
            assert not config.exists()
            try:
                for original in repo_dir.glob('*.repo'):
                    backup=original.with_suffix('.repo.qa-disabled')
                    assert not backup.exists()
                    original.rename(backup);moved.append((original,backup))
                config.write_text('[ventoy-software-qa]\nname=Disposable software QA\nbaseurl=file://'+str(repo)+'\nenabled=1\ngpgcheck=0\n')
                assert client.transaction([dependent],family,str(root/'repo-transaction'),True)==1
                client.verify([dependent],family,baseline)
                assert 'ventoy-qa-repo-lib:noarch' in client.installed(family)
                broken_post=client.metadata(package('ventoy-qa-scriptlet-dnf','ventoy-qa-scriptlet-repo-lib',bad_post=True),family,arch)
                with unittest.TestCase().assertRaisesRegex(RuntimeError,'script failed'):
                    client.transaction([broken_post],family,str(root/'dnf-post-failure'),True)
                assert 'ventoy-qa-scriptlet-dnf:noarch' in client.installed(family)
                with unittest.TestCase().assertRaisesRegex(RuntimeError,'Unresolved RPM'):
                    client.transaction([broken_post],family,str(root/'dnf-post-repeat'),True)
                corrected=client.metadata(package('ventoy-qa-scriptlet-dnf','ventoy-qa-scriptlet-repo-lib',version='2'),family,arch)
                assert client.transaction([corrected],family,str(root/'dnf-post-fixed'),True)==1
            finally:
                if config.exists():config.unlink()
                for original,backup in moved:backup.rename(original)
        client.verify(pkgs,family,baseline)
        print('NATIVE_SOFTWARE_PASS',family,'dependency transaction, idempotence, native version selection, upgrade, no downgrade, missing dependency, kernel rejection')


if __name__=='__main__':
    if '--native' in sys.argv:
        native()
    else:
        unittest.main()
