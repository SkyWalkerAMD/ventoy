"""Existing-node upgrades: real launch/update flow and isolated installed state.

The transports and OS helpers are inert fixtures. No host accounts, network,
services, kernels or installation files are modified.
"""
import hashlib
import errno
import io
import os
from pathlib import Path
import select
import shlex
import subprocess
import sys
import tarfile
import tempfile
import unittest

if sys.platform != 'linux':
    print('SKIP: Linux existing-node upgrade tests')
    sys.exit(0)
import pty

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'internal/center/assets'
LAUNCHER = (ASSETS / 'manual-launcher.sh').read_text().replace(
    "[[ $EUID == 0 ]] || { echo 'Run with root or sudo.' >&2; exit 1; }", ':')


def bundle(version):
    # Only the root ownership check is modeled for unprivileged CI fixtures.
    updater = (ASSETS / 'manual/setup-release.py').read_text().replace(
        'from software import Client, HERE', '''from software import Client, HERE
def _fixture_owned(original):
    def owned(path, *args, **kwargs):
        st = original(path, *args, **kwargs)
        if str(path).startswith(os.environ['UPGRADE_FIXTURE'] + '/'):
            values = list(st); values[4] = 0; return os.stat_result(values)
        return st
    return owned
os.stat = _fixture_owned(os.stat)
os.lstat = _fixture_owned(os.lstat)''')
    files = {
        'VERSION': version + '\n',
        'software-client.json': '{"enabled":true}',
        'setup-release.py': updater,
        'software.py': '''import io, json, hashlib, os
HERE = os.path.dirname(__file__)
class DownloadProgress:
    def __init__(self, name, total): pass
    def update(self, size): pass
class Client:
    def __init__(self, config): pass
    def get(self, endpoint, params):
        root = os.environ['UPGRADE_FIXTURE']
        with open(root+'/requests','a') as f: f.write(endpoint+'\\n')
        with open(root+'/center.run','rb') as f: data = f.read()
        if endpoint == 'setup-release':
            digest = hashlib.sha256(data).hexdigest()
            if os.environ.get('BAD_CHECKSUM'): digest = '0'*64
            data = json.dumps(dict(version='new',bytes=len(data),sha256=digest)).encode()
        elif endpoint != 'setup-release/download': raise ValueError(endpoint)
        return io.BytesIO(data)
''',
        'install.sh': '#!/bin/bash\nprintf "%s\\n" ' + shlex.quote(version) + ' "$@" >> "$UPGRADE_FIXTURE/applied"\nexit "${APPLY_RC:-0}"\n',
        'root-password.sh': '#!/bin/bash\nexit 99\n',
    }
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, text in files.items():
            data = text.encode()
            item = tarfile.TarInfo('ventoy-manual-setup/' + name)
            item.size = len(data)
            archive.addfile(item, io.BytesIO(data))
    data = stream.getvalue()
    return LAUNCHER.replace('@SETUP_VERSION@', version).replace(
        '@ARCHIVE_SHA256@', hashlib.sha256(data).hexdigest()).encode() + data


class RunnerUpgrade(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='vc-upgrade-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.runner = self.root / 'setup.run'
        self.old, self.new = bundle('old'), bundle('new')
        self.runner.write_bytes(self.old)
        self.runner.chmod(0o700)
        (self.root / 'center.run').write_bytes(self.new)
        self.env = dict(os.environ, UPGRADE_FIXTURE=str(self.root))
        for key in ('BASH_ENV', 'ENV', 'BAD_CHECKSUM', 'APPLY_RC'):
            self.env.pop(key, None)

    def run_setup(self, *args):
        return subprocess.run(['bash', './setup.run', *args], cwd=self.root,
                              env=self.env, capture_output=True, text=True, timeout=20)

    def test_update_then_execute_new_payload_with_options(self):
        result = self.run_setup('--upgrade', '--hostname', 'kept-node', '--keep-passwords')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.runner.read_bytes(), self.new)
        self.assertEqual((self.root / 'applied').read_text(), 'new\n--apply\n--hostname\nkept-node\n--keep-passwords\n')
        backups = list(self.root.glob('setup.run.previous-*'))
        self.assertEqual([p.read_bytes() for p in backups], [self.old])
        self.assertIn('SETUP_UPGRADE:', result.stdout)

    def test_download_only_then_upgrade_already_current_still_applies(self):
        result = self.run_setup('--update-setup')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'applied').exists())
        (self.root / 'requests').unlink()
        result = self.run_setup('--upgrade')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'applied').read_text(), 'new\n--apply\n')
        self.assertEqual((self.root / 'requests').read_text(), 'setup-release\n')

    def test_checksum_failure_never_executes_old_or_new(self):
        self.env['BAD_CHECKSUM'] = '1'
        result = self.run_setup('--upgrade')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.runner.read_bytes(), self.old)
        self.assertFalse((self.root / 'applied').exists())

    def test_invalid_or_offline_options_do_not_contact_center(self):
        for args in [('--upgrade', '--offline'), ('--upgrade', '--check'),
                     ('--upgrade', '--hostname'), ('--upgrade', '--hostname', '--offline'),
                     ('--update-setup', '--offline')]:
            result = self.run_setup(*args)
            self.assertEqual(result.returncode, 2, (args, result.stderr))
            self.assertFalse((self.root / 'requests').exists())
            self.assertFalse((self.root / 'applied').exists())

    def test_new_payload_exit_status_is_preserved(self):
        for status in (1, 3, 4):
            self.env['APPLY_RC'] = str(status)
            result = self.run_setup('--upgrade')
            self.assertEqual(result.returncode, status, result.stdout + result.stderr)


class InstalledMigration(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='vc-migration-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = self.root / 'state'
        self.state.mkdir()
        self.here = self.root / 'payload'
        self.here.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, MIGRATION_FIXTURE=str(self.root), PATH=str(self.bin) + ':' + os.environ['PATH'])
        for key in ('BASH_ENV', 'ENV', 'FAIL_POLICY'):
            self.env.pop(key, None)
        for name, value in [('configured', ''), ('accounts-set', 'user\n'), ('offline', '0\n'),
                            ('keep-passwords', '0\n'), ('software-request', '0\n')]:
            (self.state / name).write_text(value)
        (self.root / 'hostname').write_text('operator-name\n')
        (self.root / 'passwords').write_text('operator-root-and-user-password-hashes\n')
        (self.root / 'network').write_text('existing-static-and-dhcp-profiles\n')
        (self.root / 'os-release').write_text('ID=rocky\nVERSION_ID=9.2\n')
        (self.root / 'sbin').mkdir()
        (self.root / 'cloud').mkdir()
        (self.root / 'systemd').mkdir()
        for name, script in {
            'hostname': 'cat "$MIGRATION_FIXTURE/hostname"',
            'findmnt': 'echo xfs',
            'restorecon': ':',
            'systemctl': '''case "$1" in
get-default) echo multi-user.target;;
*) echo "systemctl $*" >> "$MIGRATION_FIXTURE/actions";;
esac''',
        }.items():
            file = self.bin / name
            file.write_text('#!/bin/sh\n' + script + '\n')
            file.chmod(0o755)
        # Exercise the real --resume state machine. Only machine paths,
        # privilege/runtime guards and helper side effects are isolated.
        source = (ASSETS / 'manual/install.sh').read_text()
        source = source.replace('export PATH=/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C SYSTEMD_PAGER=cat', 'export LC_ALL=C SYSTEMD_PAGER=cat')
        for line in source.splitlines():
            if line.startswith(('[[ $EUID == 0 &&', "[[ $(stat -Lc", '[[ ! -e /run/anaconda')):
                source = source.replace(line, ': # isolated fixture runtime')
        for old, new in {
            '/var/lib/ventoy-center/manual-init': str(self.state),
            '/var/log/ventoy-manual-init.log': str(self.root / 'setup.log'),
            '/etc/os-release': str(self.root / 'os-release'),
            '/etc/hostname': str(self.root / 'hostname'),
            '/etc/cloud/cloud.cfg.d': str(self.root / 'cloud'),
            '/usr/local/sbin/safe-server-init': str(self.root / 'sbin/safe-server-init'),
            '/opt/ventoy-manual': str(self.root / 'opt/ventoy-manual'),
            '/usr/share/ventoy-setup': str(self.root / 'share/ventoy-setup'),
            '/etc/profile.d': str(self.root / 'profile.d'),
            '/etc/systemd/system': str(self.root / 'systemd'),
        }.items():
            source = source.replace(old, new)
        (self.here / 'install.sh').write_text(source)
        for name in ['support-install.sh', 'support-report.sh', 'e610-driver.sh',
                     'manual-network.sh', 'manual-ssh.sh', 'linux-update-policy.sh', 'safe-server-init.sh']:
            text = '#!/bin/sh\necho "' + name + ' $*" >> "$MIGRATION_FIXTURE/actions"\n'
            if name == 'manual-ssh.sh':
                # Never allow a default-password check/reset on an old node.
                text += '[ "$2" = 1 ] || exit 88\n'
            if name == 'linux-update-policy.sh':
                text += '[ "${FAIL_POLICY:-}" != "$1" ] || exit 89\n'
            (self.here / name).write_text(text)
        for name in ('ventoy-setup-completion.sh', 'ventoy-setup-completion.bash'):
            (self.here / name).write_bytes((ASSETS / 'manual' / name).read_bytes())
        (self.here / 'root-password.sh').write_text('''#!/bin/bash
set -eu
case "$1" in
    --prompt) echo FIXTURE_PASSWORD_PROMPT >&2; echo fixture-secret;;
    --apply) IFS= read -r password; [[ $password == fixture-secret ]]; echo FIXTURE_PASSWORD_APPLIED;;
    *) exit 99;;
esac
''')
        self.release('new')

    def release(self, version):
        (self.here / 'VERSION').write_text(version + '\n')
        (self.here / 'ventoy-manual-init.service').write_text('fixture service ' + version + '\n')
        (self.here / 'SHA256SUMS').write_text(''.join(
            hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n'
            for p in sorted(self.here.iterdir()) if p.name != 'SHA256SUMS'))

    def resume(self, mode='--resume', *args):
        result = subprocess.run(['bash', str(self.here / 'install.sh'), mode, *args], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual((self.root / 'hostname').read_text(), 'operator-name\n')
        self.assertEqual((self.root / 'passwords').read_text(), 'operator-root-and-user-password-hashes\n')
        self.assertEqual((self.root / 'network').read_text(), 'existing-static-and-dhcp-profiles\n')
        return result

    def test_full_apply_replaces_installed_payload_and_service_retaining_passwords(self):
        for version in ('new', 'next'):
            self.release(version)
            result = self.resume('--apply', '--offline')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            current = self.root / 'opt/ventoy-manual/current'
            self.assertTrue(current.is_symlink())
            self.assertEqual((current / 'VERSION').read_text(), version + '\n')
            self.assertEqual((self.root / 'systemd/ventoy-manual-init.service').read_text(), 'fixture service ' + version + '\n')
            self.assertEqual((self.state / 'keep-passwords').read_text(), '1\n')
            self.assertEqual((self.state / 'applied-version').read_text(), version + '\n')
            self.assertTrue((self.root / 'profile.d/ventoy-setup-completion.sh').is_file())
            self.assertTrue((self.root / 'share/ventoy-setup/ventoy-setup-completion.bash').is_file())

    def test_full_apply_collects_password_before_configuration(self):
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        with subprocess.Popen(['bash', str(self.here / 'install.sh'), '--apply', '--offline'],
                              env=self.env, stdin=slave, stdout=slave, stderr=slave) as process:
            os.close(slave)
            os.write(master, b'\n')  # Keep the existing hostname.
            output = b''
            while True:
                if not select.select([master], [], [], 10)[0]:
                    process.kill()
                    self.fail('Timed out waiting for fixture output: %r' % output)
                try:
                    output += os.read(master, 65536)
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
                    break
            self.assertEqual(process.wait(timeout=10), 0, output)
        self.assertLess(output.index(b'New hostname'), output.index(b'FIXTURE_PASSWORD_PROMPT'), output)
        self.assertLess(output.index(b'FIXTURE_PASSWORD_PROMPT'), output.index(b'SETUP_STAGE:'), output)
        self.assertLess(output.index(b'VERIFIED:'), output.index(b'FIXTURE_PASSWORD_APPLIED'), output)
        self.assertNotIn(b'fixture-secret', output)

    def test_legacy_configured_node_migrates_once_and_next_version_migrates(self):
        result = self.resume()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        actions = (self.root / 'actions').read_text()
        self.assertIn('manual-ssh.sh --apply 1', actions)
        self.assertIn('linux-update-policy.sh --apply', actions)
        self.assertTrue((self.root / 'sbin/safe-server-init').is_file())
        self.assertEqual((self.state / 'applied-version').read_text(), 'new\n')
        (self.root / 'actions').write_text('')
        self.assertEqual(self.resume().returncode, 0)
        self.assertNotIn('manual-ssh.sh --apply', (self.root / 'actions').read_text())
        self.release('next')
        self.assertEqual(self.resume().returncode, 0)
        self.assertIn('manual-ssh.sh --apply 1', (self.root / 'actions').read_text())
        self.assertEqual((self.state / 'applied-version').read_text(), 'next\n')

    def test_failed_apply_and_failed_verification_retry_migration(self):
        for stage in ('--apply', '--check'):
            self.env['FAIL_POLICY'] = stage
            result = self.resume()
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.state / 'configuration-release').exists())
            self.assertFalse((self.state / 'applied-version').exists())
        self.env.pop('FAIL_POLICY')
        self.assertEqual(self.resume().returncode, 0)
        self.assertEqual((self.root / 'actions').read_text().count('manual-ssh.sh --apply 1'), 3)

    def test_check_does_not_migrate_or_claim_new_version(self):
        result = self.resume('--check')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.state / 'configuration-release').exists())
        self.assertNotIn('--apply', (self.root / 'actions').read_text())


if __name__ == '__main__':
    unittest.main()
