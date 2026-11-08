"""Exercise login-policy transactions; native mode is disposable-container only."""
import argparse
import importlib.util
import json
import os
import shlex
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'internal/center/assets/manual/login-mode.py'
if not SOURCE.exists():  # Explicit read-only mount in the disposable CI container.
    SOURCE = Path('/login-mode.py')


def load():
    spec = importlib.util.spec_from_file_location('login_mode', SOURCE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def transactions():
    if not sys.platform.startswith('linux'):
        print('SKIP: Linux login transaction tests')
        return
    runtime_socket_checks()
    for scenario in ('success', 'repeated', 'wrong-password', 'no-sudo', 'no-user',
                     'locked-user', 'invalid-user', 'noninteractive', 'match-override',
                     'reload-failure', 'post-sudo-failure', 'root-already-locked',
                     'atomic-failure', 'invalid-saved-mode'):
        mod = load()
        with tempfile.TemporaryDirectory(prefix='vc-login-mode-') as temp:
            folder = Path(temp)
            for attr, relative in (('STATE', 'state'), ('CONFIG', 'sshd_config'),
                                   ('CLOUD', 'cloud/config'), ('HELPER', 'lib/login-mode.py'),
                                   ('AUTO_CHECK', 'bin/root-ssh')):
                setattr(mod, attr, folder / relative)
            mod.POLICY = mod.STATE / 'login-policy.json'
            for path in (mod.STATE, mod.CLOUD.parent, mod.HELPER.parent, mod.AUTO_CHECK.parent):
                path.mkdir(mode=0o700, parents=True, exist_ok=True)
            mod.CONFIG.write_text('PermitRootLogin yes\nPasswordAuthentication yes\n')
            mod.CLOUD.write_text('disable_root: false\nssh_pwauth: true\n')
            mod.AUTO_CHECK.write_text('#!/bin/sh\n# BEGIN VENTOY ROOT SSH\necho check\n')
            before = {p: p.read_bytes() for p in (mod.CONFIG, mod.CLOUD, mod.AUTO_CHECK)}
            original_hash = '!$6$fixture$root' if scenario == 'root-already-locked' else '$6$fixture$root'
            hashes = {'root': original_hash, 'user': '$6$fixture$user'}
            calls = []
            probes = [0]
            reloads = [0]
            writes = [0]
            actual_atomic = mod.atomic

            def atomic(*args, **kwargs):
                if scenario == 'atomic-failure' and args[0] == mod.POLICY:
                    writes[0] += 1
                    if writes[0] == 1:
                        raise OSError('fixture publish error')
                # CI can run unprivileged; only the fixture owns these files.
                kwargs.pop('uid', None)
                kwargs.pop('gid', None)
                args = list(args)
                while len(args) < 5:
                    args.append((0o600, os.getuid(), os.getgid())[len(args)-2])
                args[3:] = [os.getuid(), os.getgid()]
                return actual_atomic(*args, **kwargs)

            def snapshot(path):
                if not path.exists():
                    return None
                return path.read_bytes(), path.stat().st_mode & 0o777, os.getuid(), os.getgid()

            def run(args, data=None, env=None, timeout=30):
                calls.append(args)
                if args[:2] == ['getent', 'shadow']:
                    return args[-1] + ':' + hashes[args[-1]] + ':20000:0:99999:7:::\n'
                if args[:2] == ['getent', 'passwd']:
                    if scenario == 'no-user':
                        raise mod.PolicyError('missing user')
                    return args[-1] + ':x:1000:1000::/home/user:/bin/bash\n'
                if args[0] in ('visudo', 'sudo'):
                    if scenario == 'no-sudo':
                        raise mod.PolicyError('no sudo')
                    return ''
                if args[:2] == ['systemctl', 'reload']:
                    reloads[0] += 1
                    if scenario == 'reload-failure' and reloads[0] == 1:
                        raise mod.PolicyError('reload failed')
                    return ''
                if args[0] == 'systemctl':
                    return ''
                if args[0] == '/usr/sbin/sshd':
                    if '-t' in args:
                        return ''
                    path = Path(args[args.index('-f')+1]) if '-f' in args else mod.CONFIG
                    disabled = path.read_text().startswith(mod.BEGIN) and scenario != 'match-override'
                    return 'port 2222\npasswordauthentication yes\npermitrootlogin ' + ('no' if disabled else 'yes') + '\n'
                if args[0] == 'usermod':
                    hashes['root'] = '!' + hashes['root'] if args[1] == '--lock' else hashes['root'][1:]
                    return ''
                raise AssertionError(args)

            from contextlib import contextmanager

            @contextmanager
            def credentials(user, password, port):
                assert password == 'fixture secret' and port == '2222'
                def verify():
                    probes[0] += 1
                    if scenario == 'wrong-password' or (scenario == 'post-sudo-failure' and probes[0] > 1):
                        raise mod.PolicyError('actual SSH/sudo denied')
                yield verify

            if scenario == 'locked-user':
                hashes['user'] = '!locked'
            with mock.patch.object(mod, 'run', run), mock.patch.object(mod, 'snapshot', snapshot), \
                 mock.patch.object(mod, 'atomic', atomic), mock.patch.object(mod, 'credentials', credentials), \
                 mock.patch.object(sys.stdin, 'isatty', return_value=scenario != 'noninteractive'), \
                 mock.patch.object(sys.stdout, 'isatty', return_value=True), \
                 mock.patch.object(mod.getpass, 'getpass', return_value='fixture secret'), \
                 mock.patch.object(mod.time, 'sleep'), \
                 mock.patch.object(mod, 'prepare_ssh_runtime'):
                success = scenario in ('success', 'repeated', 'root-already-locked')
                if scenario == 'invalid-saved-mode':
                    mod.POLICY.write_text('{"schema":1,"mode":"typo","user":"user"}')
                    mod.POLICY.chmod(0o600)
                    try:
                        mod.check()
                    except mod.PolicyError:
                        pass
                    else:
                        raise AssertionError('Invalid policy was silently ignored')
                    continue
                try:
                    mod.restore('root' if scenario == 'invalid-user' else 'user')
                    if scenario == 'repeated':
                        mod.restore('user')
                except (mod.PolicyError, OSError):
                    assert not success, scenario
                else:
                    assert success, scenario
                assert hashes['user'] == ('!locked' if scenario == 'locked-user' else '$6$fixture$user')
                if success:
                    assert hashes['root'].startswith('!')
                    assert mod.saved_policy()['user'] == 'user'
                    assert mod.CLOUD.read_text().count('disable_root: true') == 1
                    assert mod.CONFIG.read_text().count(mod.BEGIN) == 1
                    assert mod.AUTO_CHECK.read_text().count('# BEGIN VENTOY LOGIN MODE GUARD') == 1
                    mod.check()
                    assert not any(c[0] == 'chpasswd' for c in calls)
                    assert probes[0] >= 2
                else:
                    assert hashes['root'] == original_hash, scenario
                    assert not mod.POLICY.exists(), scenario
                    assert all(p.read_bytes() == old for p, old in before.items()), scenario
                    assert not mod.HELPER.exists(), scenario
    print('PASS: optional user login, preflight denial, unchanged passwords, repeated restore, rollback and persisted policy')

    # Exercise the real dispatch used by migrations, --check and boot --resume.
    # Stop at the old root-enabled branch so a failed guard cannot touch the host.
    ssh_source = (ROOT / 'internal/center/assets/manual/manual-ssh.sh').read_text()
    dispatch = ssh_source.split('if [[ $mode == --apply ]]; then', 1)[0]
    # This dispatch-only fixture must not prepare the host's /run. The complete
    # checker and runtime protections run separately in validate_manual_ssh.py.
    assert dispatch.count('\nprepare_sshd_runtime\n') == 1
    dispatch = dispatch.replace('\nprepare_sshd_runtime\n', '\n')
    with tempfile.TemporaryDirectory(prefix='vc-login-dispatch-') as temp:
        folder = Path(temp)
        (folder / 'bin').mkdir()
        helper = folder / 'bin/python3'
        helper.write_text('#!/bin/sh\n[ "$*" = "$FIXTURE/login-mode.py --check" ] || exit 99\necho SAVED_USER_POLICY_CHECKED\n')
        helper.chmod(0o755)
        source = dispatch.replace('export PATH=/usr/sbin:/usr/bin:/sbin:/bin', 'export PATH=' + shlex.quote(str(folder / 'bin')) + ':/usr/sbin:/usr/bin:/sbin:/bin')
        source = source.replace('state=/var/lib/ventoy-center/manual-init', 'state=' + shlex.quote(temp))
        source = source.replace('. /etc/os-release', '. ' + shlex.quote(str(folder / 'os-release')))
        script = folder / 'manual-ssh.sh'
        script.write_text(source + '\necho DEFAULT_ROOT_POLICY\n')
        for os_id, marker, action in [('ubuntu', True, '--apply'), ('debian', True, '--check'),
                                      ('ubuntu', True, '--check'), ('debian', True, '--apply'),
                                      ('debian', False, '--apply'), ('rocky', True, '--apply')]:
            (folder / 'os-release').write_text('ID=' + os_id + '\n')
            policy = folder / 'login-policy.json'
            if marker:
                policy.write_text('{"schema":1,"mode":"user-sudo","user":"user"}')
            elif policy.exists():
                policy.unlink()
            result = subprocess.run(['bash', str(script), action, '0'], capture_output=True, text=True,
                                    env=dict(os.environ, FIXTURE=temp), timeout=10)
            expected = 'SAVED_USER_POLICY_CHECKED' if marker and os_id in ('ubuntu', 'debian') else 'DEFAULT_ROOT_POLICY'
            assert result.returncode == 0 and result.stdout.strip() == expected, result
        # A root permission for only a remote address must not evade localhost
        # checks; follow Includes and reject it before changing any login state.
        mod = load()
        included = folder / 'remote.conf'
        config = folder / 'sshd_config'
        config.write_text('PermitRootLogin no\nInclude ' + str(included) + '\n')
        for text, allowed in [('PermitRootLogin yes\n', True),
                              ('Match Address 192.0.2.0/24\n PermitRootLogin yes\n', False),
                              ('Match User root\n PermitRootLogin no\n', True)]:
            included.write_text(text)
            try:
                mod.check_match_overrides(config)
            except mod.PolicyError:
                assert not allowed
            else:
                assert allowed
    print('PASS: setup/migration/check dispatch preserves user-only choice; new installs and RPM defaults unchanged; remote Match overrides rejected')


def runtime_socket_checks():
    # Exercise user-only policy checks before any connection activates the
    # daemon. No service is started and no listener is contacted by these tests.
    for daemon, socket, expected in [('active', 'inactive', True),
                                     ('inactive', 'active', True),
                                     ('inactive', 'inactive', False),
                                     ('failed', 'active', False),
                                     ('', 'active', False)]:
        mod = load()
        calls = []

        def query(args, **kwargs):
            calls.append(args)
            if args == ['systemctl', 'is-active', '--quiet', 'ssh.service']:
                if daemon != 'active':
                    raise mod.PolicyError('inactive daemon')
            elif args == ['systemctl', 'is-active', '--quiet', 'ssh.socket']:
                if socket != 'active':
                    raise mod.PolicyError('inactive socket')
            elif args == ['systemctl', 'show', 'ssh.service', '-p', 'ActiveState', '--value']:
                return daemon + '\n'
            else:
                raise AssertionError(args)
            return ''

        with mock.patch.object(mod, 'run', query):
            try:
                mod.check_listener()
            except mod.PolicyError:
                assert not expected, (daemon, socket)
            else:
                assert expected, (daemon, socket)
        assert all(args[1] in ('is-active', 'show') for args in calls)

    for shape in ('missing', 'existing', 'concurrent', 'symlink', 'parent-symlink',
                  'parent-writable', 'file', 'writable', 'private', 'owner'):
        mod = load()
        with tempfile.TemporaryDirectory(prefix='vc-login-runtime-') as temp:
            root = Path(temp)
            parent = root / 'run'
            parent.mkdir(mode=0o755)
            parent.chmod(0o755)
            mod.SSH_RUNTIME = runtime = parent / 'sshd'
            sentinel = root / 'untouched'
            sentinel.mkdir(mode=0o700)
            (sentinel / 'marker').write_text('keep\n')
            if shape in ('existing', 'writable', 'private', 'owner'):
                runtime.mkdir(mode=0o755)
                runtime.chmod(0o755)
                (runtime / 'marker').write_text('keep\n')
                if shape == 'writable':
                    runtime.chmod(0o777)
                elif shape == 'private':
                    runtime.chmod(0o700)
            elif shape == 'symlink':
                runtime.symlink_to(sentinel, target_is_directory=True)
            elif shape == 'parent-symlink':
                parent.rmdir()
                parent.symlink_to(sentinel, target_is_directory=True)
            elif shape == 'parent-writable':
                parent.chmod(0o777)
            elif shape == 'file':
                runtime.write_text('keep\n')
            actual_lstat = Path.lstat
            actual_mkdir = Path.mkdir

            def create(path, *args, **kwargs):
                actual_mkdir(path, *args, **kwargs)
                if shape == 'concurrent' and path == runtime:
                    path.chmod(0o755)
                    raise FileExistsError('fixture: daemon created runtime concurrently')

            def metadata(path, *args, **kwargs):
                # Fixtures can run under an unprivileged CI user. Preserve
                # actual file type/mode while modeling root or a foreign owner.
                info = actual_lstat(path, *args, **kwargs)
                from types import SimpleNamespace
                return SimpleNamespace(st_mode=info.st_mode, st_uid=(1000 if shape == 'owner' and path == runtime else 0), st_gid=0)

            calls = []

            def command(args, **kwargs):
                calls.append(args)
                if args[0] == '/sbin/restorecon':
                    assert args[1] == str(runtime)
                    return ''
                if args[0] == '/usr/sbin/sshd':
                    assert runtime.is_dir() and not runtime.is_symlink()
                    if '-T' in args:
                        return 'passwordauthentication yes\nport 22\n'
                    return ''
                raise AssertionError(args)

            expected = shape in ('missing', 'existing', 'concurrent')
            with mock.patch.object(Path, 'lstat', metadata), mock.patch.object(Path, 'mkdir', create), \
                 mock.patch.object(mod, 'run', command):
                try:
                    assert mod.check_ssh('user', restricted=False) == '22'
                except mod.PolicyError:
                    assert not expected, shape
                else:
                    assert expected, shape
            assert (sentinel / 'marker').read_text() == 'keep\n'
            assert sentinel.stat().st_mode & 0o777 == 0o700
            if expected:
                assert runtime.stat().st_mode & 0o777 == 0o755
            else:
                assert not calls, (shape, calls)
            if shape in ('existing', 'writable', 'private', 'owner'):
                assert (runtime / 'marker').read_text() == 'keep\n'
                assert runtime.stat().st_mode & 0o777 == {'writable': 0o777, 'private': 0o700}.get(shape, 0o755)
            if shape == 'file':
                assert runtime.read_text() == 'keep\n'
    print('PASS: ordinary-user checks support idle SSH sockets and reject unsafe runtime paths/failed daemons')


def native():
    # This test intentionally changes accounts/config only inside a disposable
    # container marked by the CI job. Never run against a real installed node.
    if os.geteuid() != 0 or not Path('/run/ventoy-policy-disposable-root').exists() or not Path('/.dockerenv').exists():
        raise RuntimeError('Native login test requires the marked disposable Docker container')
    mod = load()
    if not any(x in Path('/etc/os-release').read_text() for x in ('ID=ubuntu', 'ID=debian')):
        print('SKIP: native user-login policy is Debian/Ubuntu only')
        return
    subprocess.run(['useradd', '-m', '-s', '/bin/bash', 'vc_login_test'], check=True)
    subprocess.run(['chpasswd'], input='vc_login_test:fixture-Login-942\nroot:fixture-Root-872\n', text=True, check=True)
    Path('/etc/sudoers.d/90-ventoy-test').write_text('vc_login_test ALL=(ALL:ALL) ALL\n')
    Path('/etc/sudoers.d/90-ventoy-test').chmod(0o440)
    Path('/run/sshd').mkdir(exist_ok=True)
    mod.private_dir(mod.STATE)
    mod.CLOUD.parent.mkdir(parents=True, exist_ok=True)
    mod.CLOUD.write_text('disable_root: false\nssh_pwauth: true\n')
    mod.AUTO_CHECK.parent.mkdir(parents=True, exist_ok=True)
    mod.AUTO_CHECK.write_text('#!/bin/sh\n# BEGIN VENTOY ROOT SSH\necho old-policy\n')
    mod.CONFIG.write_text('Port 2222\nListenAddress 127.0.0.1\nPermitRootLogin yes\nPasswordAuthentication yes\nUsePAM yes\nPidFile /run/ventoy-test-sshd.pid\n')
    subprocess.run(['ssh-keygen', '-A'], check=True)
    daemon = subprocess.Popen(['/usr/sbin/sshd', '-D', '-e', '-f', str(mod.CONFIG)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    actual_run = mod.run

    def run(args, **kw):
        if args[0] == 'systemctl':
            assert args in (['systemctl', 'is-active', '--quiet', 'ssh.service'], ['systemctl', 'reload', 'ssh.service'])
            assert daemon.poll() is None
            if args[1] == 'reload':
                import signal
                daemon.send_signal(signal.SIGHUP)
                mod.time.sleep(.3)
            return ''
        return actual_run(args, **kw)

    try:
        mod.time.sleep(.4)
        with mock.patch.object(mod, 'run', run), \
             mock.patch.object(sys.stdin, 'isatty', return_value=True), \
             mock.patch.object(sys.stdout, 'isatty', return_value=True), \
             mock.patch.object(mod.getpass, 'getpass', return_value='fixture-Login-942'):
            before = mod.shadow('root')
            # Actual password SSH success before the mode change (root has sudo).
            with mod.credentials('root', 'fixture-Root-872', '2222') as verify:
                verify()
            mod.restore('vc_login_test')
            assert mod.shadow('root') == '!' + before
            with mod.credentials('root', 'fixture-Root-872', '2222') as verify:
                try:
                    verify()
                except mod.PolicyError:
                    pass
                else:
                    raise AssertionError('Root SSH still accepted')
            mod.restore('vc_login_test')
            mod.check()
            assert not list(mod.STATE.glob('login-check.*'))
            print('NATIVE_PASS: actual ordinary-user SSH/sudo, root SSH denied, root shadow locked, repeated run unchanged')
    finally:
        daemon.terminate()
        daemon.wait(timeout=10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--native', action='store_true')
    if parser.parse_args().native:
        native()
    else:
        transactions()
