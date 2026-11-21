#!/usr/bin/env python
"""Root-only, real fyhoc authentication on a private controlling terminal.

No session-file fabrication and no password in argv, environment, or output.
Python 2.7 / 3.x, including EL7's system Python.
"""
from __future__ import print_function
import errno
import json
import os
import pty
import resource
import select
import signal
import stat
import subprocess
import sys
import tempfile
import termios
import time

KEY = '/etc/ventoy-center/fyhoc-unlock.key'
HELPER = '/usr/local/lib/ventoy-center/fyhoc_unlock.py'
UNIT = '/etc/systemd/system/ventoy-fyhoc-unlock.service'
SERVICE = 'ventoy-fyhoc-unlock.service'
TIMEOUT = 30
STRING = (str, type(u''))


def password_bytes(value):
    if not isinstance(value, STRING):
        raise RuntimeError('Invalid FYHOC credential')
    try:
        key = value.encode('ascii')
    except UnicodeError:
        raise RuntimeError('Invalid FYHOC credential')
    if not 0 < len(key) < 128 or any(c < 33 or c > 126 for c in bytearray(key)):
        raise RuntimeError('Invalid FYHOC credential')
    return key


def trusted_binary(command='fyhoc'):
    # Do not execute a caller-controlled PATH entry as root during authentication.
    for directory in ('/usr/bin', '/usr/local/bin', '/usr/sbin', '/usr/local/sbin'):
        name = os.path.join(directory, command)
        if not os.path.exists(name):
            continue
        real = os.path.realpath(name)
        st = os.stat(real)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022 or not os.access(real, os.X_OK):
            raise RuntimeError('%s executable is not root-owned and protected' % command)
        directory = os.path.dirname(real)
        while directory != '/':
            st = os.stat(directory)
            if st.st_uid != 0 or st.st_mode & 0o022:
                raise RuntimeError('%s executable directory is not protected' % command)
            directory = os.path.dirname(directory)
        return real
    raise RuntimeError('Installed %s executable was not found' % command)


def unlocked(binary):
    # The official command returns success without prompting only when the
    # current boot/version/key session is valid. setsid prevents using our tty.
    with open(os.devnull, 'rb+') as null:
        p = subprocess.Popen([binary, 'unlk'], stdin=null, stdout=null, stderr=null,
                             preexec_fn=os.setsid, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})
        deadline = time.time() + TIMEOUT
        while p.poll() is None and time.time() < deadline:
            time.sleep(0.05)
        if p.poll() is None:
            p.kill(); p.wait()
            raise RuntimeError('FYHOC verification timed out')
        return p.returncode == 0


def authenticate(binary, key):
    if unlocked(binary):
        return
    pid, fd = pty.fork()
    if pid == 0:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        os.execve(binary, [binary, 'unlk'], {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})
    sent, status, output = False, None, b''
    deadline = time.time() + TIMEOUT
    try:
        while time.time() < deadline:
            ready, _, _ = select.select([fd], [], [], 0.1)
            if ready:
                try:
                    data = os.read(fd, 4096)
                except OSError as e:
                    if e.errno != errno.EIO:
                        raise
                    data = b''
                output = (output + data)[-8192:]
                if not sent and b'fyhoc password: ' in output:
                    # Never send a secret while the pty could echo it back.
                    if termios.tcgetattr(fd)[3] & (termios.ECHO | termios.ECHONL):
                        raise RuntimeError('FYHOC password prompt has terminal echo enabled')
                    os.write(fd, key + b'\n')
                    sent = True
            done, result = os.waitpid(pid, os.WNOHANG)
            if done:
                status = result
                break
        if status is None:
            raise RuntimeError('FYHOC unlock timed out')
        if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0 or not unlocked(binary):
            raise RuntimeError('FYHOC unlock failed; check the configured password and package version')
    finally:
        if status is None:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
            os.waitpid(pid, 0)
        os.close(fd)
        # Deliberately never print terminal output, even on unexpected failures.


def private_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory, 0o700)
    st = os.lstat(directory)
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022 or
            os.path.realpath(directory) != directory):
        raise RuntimeError('FYHOC configuration directory is not protected')


def write_private(path, data, mode):
    directory = os.path.dirname(path)
    private_directory(directory)
    if os.path.lexists(path):
        st = os.lstat(path)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            raise RuntimeError('Refusing an unsafe FYHOC configuration destination')
    fd, temporary = tempfile.mkstemp(prefix='.fyhoc-', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.chmod(temporary, mode)
        os.rename(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_key():
    private_directory(os.path.dirname(KEY))
    fd = os.open(KEY, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1:
            raise RuntimeError('FYHOC key must be a root-owned 0600 regular file')
        value = f.read(129).decode('ascii').rstrip('\n')
    return password_bytes(value)


def command(args):
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = p.communicate()
    if p.returncode:
        raise RuntimeError('FYHOC service configuration/check failed: ' + args[1])
    return output.decode('ascii', 'replace').strip()


def configure(client):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    response = client.get('fyhoc-unlock', {})
    try:
        data = response.read(1025)
    finally:
        response.close()
    if len(data) > 1024:
        raise RuntimeError('Invalid FYHOC credential response')
    config = json.loads(data.decode('utf-8'))
    if config.get('enabled') is False:
        print('FYHOC_UNLOCK_SKIPPED: controller automatic unlock is not configured.')
        return False
    if config.get('enabled') is not True:
        raise RuntimeError('Invalid FYHOC credential response')
    key = password_bytes(config.get('password'))
    binary = trusted_binary()
    previous = None
    if os.path.lexists(KEY):
        previous = read_key()
    # A new password must actually be authenticated. An already unlocked boot
    # alone cannot validate a rotated password for the next boot.
    if previous != key:
        command([binary, 'down'])
    try:
        authenticate(binary, key)
    except Exception:
        if previous is not None:
            authenticate(binary, previous)
        raise
    interpreter = os.path.realpath(sys.executable)
    if any(c not in '/abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for c in interpreter):
        raise RuntimeError('Unsupported Python interpreter path')
    write_private(KEY, key + b'\n', 0o600)
    with open(__file__, 'rb') as f:
        helper = f.read()
    write_private(HELPER, helper, 0o700)
    unit = ('[Unit]\nDescription=Unlock installed FYHOC for this boot\n'
            'After=local-fs.target\nBefore=fyhocsys-node.service\n'
            'ConditionPathExists=' + KEY + '\n\n[Service]\nType=oneshot\n'
            'ExecStart=' + interpreter + ' ' + HELPER + '\n'
            'RemainAfterExit=yes\nTimeoutStartSec=70\nUMask=0077\nLimitCORE=0\n'
            '\n[Install]\nWantedBy=multi-user.target\n')
    write_private(UNIT, unit.encode('ascii'), 0o644)
    if os.path.isfile('/usr/sbin/restorecon'):
        command(['/usr/sbin/restorecon', KEY, HELPER, UNIT])
    command(['systemctl', 'daemon-reload'])
    command(['systemctl', 'enable', SERVICE])
    command(['systemctl', 'restart', SERVICE])
    check()
    print('FYHOC_UNLOCK_VERIFIED: unlocked now; automatic unlock enabled for each boot.')
    return True


def check():
    read_key()  # Verify persistence and permissions, without printing it.
    if command(['systemctl', 'is-enabled', SERVICE]) != 'enabled':
        raise RuntimeError('FYHOC boot unlock service is not enabled')
    if command(['systemctl', 'is-active', SERVICE]) != 'active' or not unlocked(trusted_binary()):
        raise RuntimeError('FYHOC is not unlocked for the current boot')


def main():
    if os.geteuid() != 0 or len(sys.argv) != 1:
        raise RuntimeError('Run the FYHOC boot helper as root without arguments')
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    authenticate(trusted_binary(), read_key())
    print('FYHOC_UNLOCK_VERIFIED: current boot authenticated.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Secrets or unexpected terminal output must never reach the journal.
        print('FYHOC_UNLOCK_FAILED: check credential, package and service configuration.', file=sys.stderr)
        sys.exit(1)
