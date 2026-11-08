#!/usr/bin/env python3
"""Opt-in Ubuntu/Debian user + sudo login, with a verified recovery path.

Never called by an installer. A saved policy is also read by later setup runs.
Only the interactive restore action changes login policy; --check may prepare
the root-owned SSH runtime directory but never changes login configuration.
"""
import argparse
import contextlib
import fcntl
import getpass
import glob
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time

STATE = Path('/var/lib/ventoy-center/manual-init')
POLICY = STATE / 'login-policy.json'
CONFIG = Path('/etc/ssh/sshd_config')
CLOUD = Path('/etc/cloud/cloud.cfg.d/99-ventoy-root-ssh.cfg')
HELPER = Path('/usr/local/lib/ventoy-center/login-mode.py')
AUTO_CHECK = Path('/usr/local/sbin/ventoy-center-root-ssh')
SSH_RUNTIME = Path('/run/sshd')
BEGIN = '# BEGIN VENTOY USER LOGIN'
END = '# END VENTOY USER LOGIN'
AUTO_GUARD = '''# BEGIN VENTOY LOGIN MODE GUARD
if [ -e /var/lib/ventoy-center/manual-init/login-policy.json ] || [ -L /var/lib/ventoy-center/manual-init/login-policy.json ]; then
    exec /usr/bin/python3 /usr/local/lib/ventoy-center/login-mode.py --check
fi
# END VENTOY LOGIN MODE GUARD
'''


class PolicyError(Exception):
    pass


def run(args, data=None, env=None, timeout=30):
    result = subprocess.run(args, input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, timeout=timeout,
                            universal_newlines=True)
    if result.returncode:
        # Do not echo command arguments/input: they may contain authentication
        # data in a future caller. SSH stderr can echo a server's custom banner.
        raise PolicyError('{} failed (exit {}).'.format(Path(args[0]).name, result.returncode))
    return result.stdout


def private_dir(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    s = path.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o077:
        raise PolicyError('Unsafe private state directory: {}.'.format(path))


def snapshot(path):
    if not path.exists() and not path.is_symlink():
        return None
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or s.st_nlink != 1 or s.st_mode & 0o022:
        raise PolicyError('Expected a root-owned, non-writable regular file: {}.'.format(path))
    return (path.read_bytes(), stat.S_IMODE(s.st_mode), s.st_uid, s.st_gid)


def atomic(path, data, mode=0o600, uid=0, gid=0):
    if path.is_symlink():
        raise PolicyError('Unexpected file symlink: {}.'.format(path))
    fd, name = tempfile.mkstemp(prefix='.ventoy-login-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
            os.fchown(stream.fileno(), uid, gid)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, str(path))
    finally:
        if os.path.exists(name):
            os.unlink(name)


def saved_policy():
    saved = snapshot(POLICY)
    if saved is None:
        return None
    if saved[1] & 0o077:
        raise PolicyError('Login policy must be private (mode 0600).')
    obj = json.loads(saved[0].decode('utf-8'))
    if obj.get('schema') != 1 or obj.get('mode') != 'user-sudo':
        raise PolicyError('Unrecognized saved login policy; no changes made.')
    validate_name(obj.get('user', ''))
    return obj


def validate_name(user):
    if not isinstance(user, str) or not re.fullmatch(r'[a-z_][a-z0-9_.-]{0,31}', user) or user in ('root', 'nobody'):
        raise PolicyError('Select an existing ordinary login account, not root.')


def shadow(user):
    result = run(['getent', 'shadow', user]).strip().split(':')
    if len(result) != 9 or result[0] != user:
        raise PolicyError('Cannot inspect the selected local account.')
    return result[1]


def check_user(user):
    validate_name(user)
    entry = run(['getent', 'passwd', user]).strip().split(':')
    if len(entry) != 7 or entry[0] != user or not 1000 <= int(entry[2]) < 65534:
        raise PolicyError('The selected user is missing or is a system account.')
    if entry[6].endswith(('/nologin', '/false', '/true')) or not os.access(entry[6], os.X_OK):
        raise PolicyError('The selected user has no usable login shell.')
    if not shadow(user) or shadow(user).startswith(('!', '*')):
        raise PolicyError('The selected user password is locked or unavailable. Set it before restoring user login.')
    run(['visudo', '-c'])
    run(['sudo', '-l', '-U', user])


def effective(user, config=None):
    args = ['/usr/sbin/sshd', '-T']
    if config is not None:
        args += ['-f', str(config)]
    args += ['-C', 'user={},host=localhost,addr=127.0.0.1'.format(user)]
    return dict(line.split(None, 1) for line in run(args).splitlines() if ' ' in line)


def check_match_overrides(config):
    # A global setting can be overridden by a Match/Include applying only to a
    # remote subnet, invisible in a localhost login probe. Refuse such competing
    # root permissions instead of claiming every root SSH login is disabled.
    def visit(path, in_match=False, stack=()):
        resolved = path.resolve()
        if resolved in stack or len(stack) >= 16:
            raise PolicyError('Recursive SSH Include requires manual review.')
        for line in path.read_text().splitlines():
            words = shlex.split(line, comments=True)
            if not words:
                continue
            keyword = words[0].lower()
            if keyword == 'match':
                in_match = True
            elif keyword == 'include':
                for pattern in words[1:]:
                    if not os.path.isabs(pattern):
                        pattern = '/etc/ssh/' + pattern
                    for name in sorted(glob.glob(pattern)):
                        in_match = visit(Path(name), in_match, stack + (resolved,))
            elif keyword == 'permitrootlogin' and in_match and words[1:] != ['no']:
                raise PolicyError('An SSH Match block permits root login. Remove that override before restoring user-only login.')
        return in_match
    visit(config)


def prepare_ssh_runtime():
    parent = SSH_RUNTIME.parent.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0 or
            parent.st_gid != 0 or parent.st_mode & 0o022):
        raise PolicyError('Unsafe SSH runtime parent: {}.'.format(SSH_RUNTIME.parent))
    if not SSH_RUNTIME.exists() and not SSH_RUNTIME.is_symlink():
        # Explicit chmod is confined to the directory just created by us. Never
        # widen permissions or change ownership of an existing runtime path.
        try:
            SSH_RUNTIME.mkdir(mode=0o755)
        except FileExistsError:
            # A connection may have activated sshd since the existence check.
            # The same type, owner and permission checks still apply below.
            pass
        else:
            SSH_RUNTIME.chmod(0o755)
            if Path('/sbin/restorecon').is_file():
                run(['/sbin/restorecon', str(SSH_RUNTIME)])
    info = SSH_RUNTIME.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_gid != 0 or
            stat.S_IMODE(info.st_mode) != 0o755):
        raise PolicyError('Unsafe SSH runtime directory: {} (expected root:root 0755).'.format(SSH_RUNTIME))


def check_listener():
    try:
        run(['systemctl', 'is-active', '--quiet', 'ssh.service'])
        return
    except PolicyError:
        # Ubuntu can listen on ssh.socket before any client starts ssh.service.
        run(['systemctl', 'is-active', '--quiet', 'ssh.socket'])
        state = run(['systemctl', 'show', 'ssh.service', '-p', 'ActiveState', '--value']).strip()
        if state not in ('inactive', 'activating', 'active', 'reloading'):
            raise PolicyError('The socket-activated SSH daemon is not healthy.')


def check_ssh(user, config=None, restricted=True):
    prepare_ssh_runtime()
    args = ['/usr/sbin/sshd', '-t']
    if config is not None:
        args += ['-f', str(config)]
    run(args)
    if restricted:
        check_match_overrides(CONFIG if config is None else config)
    if restricted and effective('root', config).get('permitrootlogin') != 'no':
        raise PolicyError('Effective root SSH policy is not disabled (check Match overrides).')
    selected = effective(user, config)
    if selected.get('passwordauthentication') != 'yes':
        raise PolicyError('Ordinary user SSH password authentication must already be enabled.')
    port = selected.get('port', '')
    if not port.isdigit() or not 0 < int(port) < 65536:
        raise PolicyError('Cannot determine the local SSH port.')
    return port


def check(policy=None):
    policy = saved_policy() if policy is None else policy
    if policy is None:
        print('LOGIN_MODE: no user-only policy selected; installation defaults are unchanged.')
        return
    check_user(policy['user'])
    check_listener()
    check_ssh(policy['user'])
    if not shadow('root').startswith(('!', '*')):
        raise PolicyError('Root console password is not locked.')
    print('USER_LOGIN_CONFIG_VERIFIED: user={}; root SSH disabled; root console password locked; sudo policy present.'.format(policy['user']))


@contextlib.contextmanager
def credentials(user, password, port):
    # Keep secrets out of arguments, environment values and logs. The temporary
    # root-only file is removed even after a failed SSH/sudo probe.
    with tempfile.TemporaryDirectory(prefix='login-check.', dir=str(STATE)) as temp:
        folder = Path(temp)
        secret = folder / 'password'
        atomic(secret, (password + '\n').encode('utf-8'))
        askpass = folder / 'askpass'
        atomic(askpass, ('#!/bin/sh\nexec /bin/cat -- ' + shlex.quote(str(secret)) + '\n').encode(), 0o700)
        hosts = []
        for path in glob.glob('/etc/ssh/ssh_host_*_key.pub'):
            record = Path(path).read_text().split()
            if len(record) >= 2:
                for host in ('127.0.0.1', '[127.0.0.1]:' + port):
                    hosts.append('{} {} {}'.format(host, record[0], record[1]))
        if not hosts:
            raise PolicyError('No local SSH host keys found; cannot verify a trusted login.')
        known = folder / 'known_hosts'
        atomic(known, ('\n'.join(hosts) + '\n').encode())
        env = dict(os.environ, DISPLAY=':0', SSH_ASKPASS=str(askpass), SSH_ASKPASS_REQUIRE='force', LC_ALL='C')
        command = ['setsid', 'ssh', '-F', '/dev/null', '-p', port,
                   '-o', 'ConnectTimeout=8', '-o', 'NumberOfPasswordPrompts=1',
                   '-o', 'PubkeyAuthentication=no', '-o', 'PreferredAuthentications=password',
                   '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + str(known),
                   user + '@127.0.0.1', 'id -un && sudo -k -S -p "" -u root -- id -u']
        def verify():
            result = run(command, data=password + '\n', env=env, timeout=25)
            if result.splitlines() != [user, '0']:
                raise PolicyError('SSH/sudo did not return the expected user and root identities.')
        yield verify


def candidate_config(text):
    # Retain existing account/password/AllowUsers/Match policy. Prepend the
    # override for old Debian releases that do not Include sshd_config.d.
    text = re.sub(r'(?m)^' + re.escape(BEGIN) + r'\n.*?^' + re.escape(END) + r'\n?', '', text, flags=re.S)
    return BEGIN + '\nPermitRootLogin no\n' + END + '\n' + text


def guarded_auto_check(text):
    if '# BEGIN VENTOY LOGIN MODE GUARD' in text:
        return text
    if '# BEGIN VENTOY ROOT SSH' not in text or not text.startswith('#!/bin/sh\n'):
        raise PolicyError('Unrecognized installer SSH checker; retained without modification.')
    return '#!/bin/sh\n' + AUTO_GUARD + text[len('#!/bin/sh\n'):]


def restore(user):
    validate_name(user)
    # Fail before any account/SSH changes when a recovery login is unavailable.
    check_user(user)
    check_listener()
    port = check_ssh(user, restricted=False)
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise PolicyError('Run this action in an interactive terminal to verify the ordinary user password.')
    print('Selected login account: {}. New logins will use this account, then sudo -i.'.format(user))
    print('Root SSH and root console password login will be disabled. Existing sessions stay open.')
    password = getpass.getpass('Current password for {} (verify SSH and sudo): '.format(user))
    if not password or '\n' in password or '\r' in password:
        raise PolicyError('Password verification canceled; login settings are unchanged.')
    with credentials(user, password, port) as verify:
        verify()
        print('USER_RECOVERY_LOGIN_VERIFIED: SSH password authentication and sudo succeeded.')
        old = {p: snapshot(p) for p in (CONFIG, CLOUD, HELPER, AUTO_CHECK, POLICY)}
        if old[CONFIG] is None:
            raise PolicyError('Missing sshd_config.')
        root_before = shadow('root')
        new = candidate_config(old[CONFIG][0].decode('utf-8')).encode('utf-8')
        auto = None if old[AUTO_CHECK] is None else guarded_auto_check(old[AUTO_CHECK][0].decode('utf-8')).encode('utf-8')
        # Syntax + Match checks against the staged config occur before publishing.
        fd, temp = tempfile.mkstemp(prefix='.ventoy-login-', dir=str(CONFIG.parent))
        os.close(fd)
        try:
            Path(temp).write_bytes(new)
            check_ssh(user, Path(temp))
        finally:
            os.unlink(temp)
        backup = Path(tempfile.mkdtemp(prefix='login-backup.', dir=str(STATE)))
        for i, (path, item) in enumerate(old.items()):
            if item is not None:
                atomic(backup / str(i), item[0])
        atomic(backup / 'files.json', json.dumps({str(i): str(p) for i, p in enumerate(old)}, indent=2).encode())
        policy = {'schema': 1, 'mode': 'user-sudo', 'user': user, 'verified_at': int(time.time())}
        changed = []
        locked = False
        try:
            HELPER.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            for path, data, metadata in (
                (HELPER, Path(__file__).read_bytes(), (0o755, 0, 0)),
                (AUTO_CHECK, auto, None if old[AUTO_CHECK] is None else old[AUTO_CHECK][1:]),
                (CLOUD, b'#cloud-config\ndisable_root: true\nssh_pwauth: true\n', (0o600, 0, 0)),
                (CONFIG, new, old[CONFIG][1:]),
                (POLICY, (json.dumps(policy) + '\n').encode(), (0o600, 0, 0)),
            ):
                if data is None or (path == CLOUD and not CLOUD.parent.is_dir()):
                    continue
                changed.append(path)
                atomic(path, data, *metadata)
            if root_before and not root_before.startswith(('!', '*')):
                # Do not expire root: sudo/system services still need that UID.
                # Mark before the operation so an interrupted command rolls back.
                locked = True
                run(['usermod', '--lock', 'root'])
            run(['systemctl', 'reload', 'ssh.service'])
            check(policy)
            # HUP reload can return before sshd has re-execed. Require a fresh
            # ordinary-user login and sudo after the lock, with bounded retries.
            for attempt in range(3):
                try:
                    verify()
                    break
                except PolicyError:
                    if attempt == 2:
                        raise
                    time.sleep(1)
        except BaseException:
            failures = []
            if locked:
                try:
                    current = shadow('root')
                    if current == '!' + root_before:
                        run(['usermod', '--unlock', 'root'])
                    elif current != root_before:
                        raise PolicyError('Root password changed concurrently; it was not overwritten.')
                except Exception as exc:
                    failures.append(str(exc))
            for path in reversed(changed):
                try:
                    if old[path] is None:
                        if path.exists() or path.is_symlink():
                            path.unlink()
                    else:
                        atomic(path, *old[path])
                except Exception:
                    failures.append('Cannot restore {}.'.format(path))
            try:
                run(['/usr/sbin/sshd', '-t'])
                run(['systemctl', 'reload', 'ssh.service'])
            except Exception:
                failures.append('Could not reload the previous SSH configuration.')
            if failures:
                print('LOGIN_ROLLBACK_INCOMPLETE: keep this session open. Backup: {}. {}'.format(backup, ' '.join(failures)), file=sys.stderr)
            else:
                print('LOGIN_ROLLED_BACK: previous root/SSH settings restored; keep this session open.', file=sys.stderr)
            raise
    print('USER_LOGIN_RESTORED: use {} for SSH/console login and sudo -i for root access.'.format(user))
    print('Root direct login is disabled. Passwords were not reset; future setup/upgrade runs retain this choice.')
    print('Backup: {}. Open another login to verify access before closing this session.'.format(backup))


def main():
    # Parse the command verb separately: it begins with -- but is not an option.
    argv = sys.argv[1:]
    action = argv.pop(0) if argv else '--check'
    if action not in ('--restore-user-login', '--check'):
        raise PolicyError('Unknown login action.')
    options = argparse.ArgumentParser()
    options.add_argument('--login-user', default=None)
    args = options.parse_args(argv)
    if os.geteuid() != 0:
        raise PolicyError('Run as root or with sudo.')
    os.umask(0o077)
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.environ.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LC_ALL='C', SYSTEMD_PAGER='cat')
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if release.get('ID', '').strip('"\'') not in ('ubuntu', 'debian'):
        raise PolicyError('This optional login mode is only for Ubuntu and Debian.')
    if action == '--check':
        check()
        return
    if not Path('/run/systemd/system').is_dir() or any(Path(p).exists() for p in ('/run/anaconda', '/run/casper', '/lib/debian-installer')):
        raise PolicyError('Run after booting the installed system, not in the installer.')
    if os.stat('/').st_ino != os.stat('/proc/1/root').st_ino or os.stat('/').st_dev != os.stat('/proc/1/root').st_dev:
        raise PolicyError('Do not change login policy from a chroot.')
    private_dir(STATE)
    if (STATE / 'lock').is_symlink():
        raise PolicyError('Unexpected lock symlink.')
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = saved_policy()
        restore(args.login_user or (previous['user'] if previous else 'user'))


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print('LOGIN_MODE_FAILED: {}'.format(exc), file=sys.stderr)
        sys.exit(1)
