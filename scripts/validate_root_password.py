"""Exercise the real password dialog on a PTY; never change host accounts."""
import errno
import hashlib
import os
from pathlib import Path
import select
import shlex
import subprocess
import sys
import tempfile
import time

if not sys.platform.startswith('linux'):
    print('SKIP: Linux password dialog PTY tests')
    sys.exit(0)
import pty

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'internal/center/assets/manual/root-password.sh').read_text()
SECRET = '  fixture:Pa$$`word\"!  '


def run(entries, expected, password_rc=0, ssh_rc=0, terminal=True, user_login=False, message=None):
    with tempfile.TemporaryDirectory(prefix='vc-root-password-') as folder:
        root = Path(folder)
        state = root / 'state'
        state.mkdir(mode=0o700)
        if user_login:
            (state / 'login-policy.json').write_text('{"schema":1,"mode":"user-sudo","user":"user"}\n')
        binpath = root / 'bin'
        binpath.mkdir()
        source = SOURCE.replace('[[ $EUID == 0 ]] || exit 1', ':')
        source = source.replace('$(stat -c %u "$state") == 0', '$(stat -c %u "$state") == ' + str(os.getuid()))
        source = source.replace('state=/var/lib/ventoy-center/manual-init', 'state=' + shlex.quote(str(state)))
        source = source.replace('password_prompt_timeout=120', 'password_prompt_timeout=1')
        source = source.replace('export PATH=/usr/sbin:/usr/bin:/sbin:/bin', 'export PATH=' + shlex.quote(str(binpath)) + ':/usr/sbin:/usr/bin:/sbin:/bin')
        (root / 'root-password.sh').write_text(source)
        command = binpath / 'chpasswd'
        command.write_text('#!' + sys.executable + '''
import hashlib, os, pathlib, sys
raw = sys.stdin.buffer.read()
assert raw.startswith(b'root:') and raw.endswith(b'\\n')
pathlib.Path(os.environ['FIXTURE_STATE'], 'password-digest').write_text(hashlib.sha256(raw[5:-1]).hexdigest())
sys.exit(int(os.environ['FIXTURE_PASSWORD_RC']))
''')
        command.chmod(0o755)
        (root / 'manual-ssh.sh').write_text('''#!/bin/bash
set -e
test "$1:$2" = --check:0
test "$(stat -c %a "$3")" = 600
test "$(stat -c %a "${3%/*}")" = 700
test "$(sha256sum "$3" | cut -d' ' -f1)" = "$FIXTURE_FILE_SHA"
echo checked > "$FIXTURE_STATE/ssh-checked"
exit "$FIXTURE_SSH_RC"
''')
        env = dict(os.environ, FIXTURE_STATE=str(state), FIXTURE_PASSWORD_RC=str(password_rc), FIXTURE_SSH_RC=str(ssh_rc),
                   FIXTURE_FILE_SHA=hashlib.sha256((SECRET + '\n').encode()).hexdigest())
        args = ['/bin/bash', '-ec', '''
password=$(bash "$1" --prompt)
if [[ -n $password ]]; then
    printf '%s\n' "$password" | bash "$1" --apply
fi
''', 'setup-password-fixture', str(root / 'root-password.sh')]
        if not terminal:
            p = subprocess.run(args, env=env, capture_output=True, timeout=10)
            assert p.returncode == 0 and not list(state.iterdir())
            return
        pid, fd = pty.fork()
        if pid == 0:
            os.execve(args[0], args, env)
        output = b''
        sent = 0
        status = None
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                ready, _, _ = select.select([fd], [], [], .05)
                if ready:
                    try:
                        output += os.read(fd, 65536)
                    except OSError as e:
                        if e.errno != errno.EIO:
                            raise
                prompts = sum(output.count(prompt) for prompt in (
                    b'New root password (Enter to keep current; input hidden): ',
                    b'Confirm new root password (input hidden): ',
                ))
                if sent < prompts and sent < len(entries):
                    value = entries[sent]
                    os.write(fd, b'\x04' if value is None else (value + '\n').encode())
                    sent += 1
                done, result = os.waitpid(pid, os.WNOHANG)
                if done:
                    status = result
                    break
            assert status is not None, output
        finally:
            if status is None:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
            os.close(fd)
        assert os.waitstatus_to_exitcode(status) == expected, output
        if message:
            assert message in output, output
        assert b'[y/N]' not in output, output
        if entries == ['']:
            assert b'Confirm new root password' not in output, output
        assert SECRET.encode() not in output, 'Password was echoed'
        assert not list(state.glob('password-check.*')), 'Plaintext scratch was retained'
        changed = (state / 'root-password-custom').exists()
        assert changed == (password_rc == 0 and entries[-2:] == [SECRET, SECRET]), output
        if changed:
            assert (state / 'password-digest').read_text() == hashlib.sha256(SECRET.encode()).hexdigest()
            assert SECRET not in (state / 'root-password-custom').read_text()
            assert (state / 'ssh-checked').exists()
            assert ('ROOT_PASSWORD_VERIFIED' in output.decode()) == (ssh_rc == 0)
        else:
            assert not (state / 'ssh-checked').exists()


run([SECRET, SECRET], 0)
run(['mismatch-one', 'mismatch-two', SECRET, SECRET], 0)
run(['one', 'two'] * 3, 2)
run([''], 0, message=b'Root password retained.')
run([None], 0, message=b'Root password change canceled; unchanged.')
run([], 0, message=b'Root password change canceled; unchanged.')
run([SECRET, None], 0, message=b'Root password change canceled; unchanged.')
run([SECRET], 0, message=b'Root password change canceled; unchanged.')
run([SECRET, SECRET], 1, password_rc=17)
run([SECRET, SECRET], 1, ssh_rc=19)
run([], 0, terminal=False)
run([], 0, user_login=True)
print('PASS: hidden password confirmation, exact whitespace, blank/cancel/retry, failures, SSH verification and secret cleanup')
