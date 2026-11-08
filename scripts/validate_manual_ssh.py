"""Exercise the real SSH checker in an isolated filesystem before first connect."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'internal/center/assets/manual/manual-ssh.sh'


def checks():
    if not sys.platform.startswith('linux'):
        print('SKIP: isolated SSH runtime/socket checks require Linux')
        return
    original = SOURCE.read_text()
    cases = [
        # Name, daemon state, socket state, runtime shape, expected exit.
        ('before-first-connect', 'inactive', 'active', 'missing', 0),
        ('concurrent-first-connect', 'inactive', 'active', 'concurrent', 0),
        ('traditional-service', 'active', 'inactive', 'missing', 0),
        ('existing-runtime', 'active', 'inactive', 'existing', 0),
        ('no-listener', 'inactive', 'inactive', 'existing', 1),
        ('failed-daemon', 'failed', 'active', 'existing', 1),
        ('unknown-daemon', '', 'active', 'existing', 1),
        ('invalid-sshd-config', 'inactive', 'active', 'missing', 255),
        ('linked-runtime', 'inactive', 'active', 'symlink', 1),
        ('linked-parent', 'inactive', 'active', 'parent-symlink', 1),
        ('writable-parent', 'inactive', 'active', 'parent-writable', 1),
        ('non-directory', 'inactive', 'active', 'file', 1),
        ('writable-runtime', 'inactive', 'active', 'writable', 1),
        ('private-runtime', 'inactive', 'active', 'private', 1),
        ('foreign-owner', 'inactive', 'active', 'owner', 1),
    ]
    for name, daemon, socket, shape, expected in cases:
        with tempfile.TemporaryDirectory(prefix='vc-ssh-runtime-') as temp:
            root = Path(temp)
            (root / 'etc').mkdir()
            (root / 'etc/os-release').write_text('ID=ubuntu\n')
            parent = root / 'run'
            parent.mkdir(mode=0o755)
            parent.chmod(0o755)
            runtime = parent / 'sshd'
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

            # Run the actual --check path. All paths are in this fixture; only
            # external service/account queries and root ownership are modeled.
            # No SSH connection, host account, unit or network setting is touched.
            mocks = r'''
stat() {
    case "$2" in
        '%u:%g') printf '0:0\n';;
        '%a:%u:%g')
            mode=$(command stat -c '%a' "$3")
            owner=0; [[ $FIXTURE_SHAPE != owner ]] || owner=1000
            printf '%s:%s:0\n' "$mode" "$owner";;
        *) command stat "$@";;
    esac
}
command() {
    if [[ $1 == -v && $2 == restorecon ]]; then return 1; fi
    builtin command "$@"
}
mkdir() {
    if [[ $FIXTURE_SHAPE == concurrent && ${!#} == "$FIXTURE/run/sshd" ]]; then
        command mkdir -m 0755 "$FIXTURE/run/sshd"
        return 1
    fi
    command mkdir "$@"
}
systemctl() {
    printf '%s\n' "$*" >> "$FIXTURE/services"
    case "$*" in
        'is-active --quiet ssh.service') [[ $FIXTURE_DAEMON == active ]];;
        'is-active --quiet ssh.socket') [[ $FIXTURE_SOCKET == active ]];;
        'show ssh.service -p ActiveState --value') printf '%s\n' "$FIXTURE_DAEMON";;
        *) echo 'Unexpected service mutation' >&2; return 99;;
    esac
}
sshd() {
    printf '%s\n' "$*" >> "$FIXTURE/sshd-calls"
    [[ -d "$FIXTURE/run/sshd" && ! -L "$FIXTURE/run/sshd" ]] || return 255
    [[ $FIXTURE_CASE != invalid-sshd-config ]] || return 255
    case "$1" in
        -t) :;;
        -T) printf 'permitrootlogin yes\npasswordauthentication yes\nport 22\n';;
        *) return 99;;
    esac
}
getent() {
    [[ $1 == shadow ]] || return 99
    printf '%s:fixture-nonsecret-hash:20000:0:99999:7:::\n' "$2"
}
sudo() { [[ "$*" == '-l -U user' ]]; }
'''
            source = original.replace('/run', str(parent)).replace('/etc/', str(root / 'etc') + '/')
            source = source.replace('/var/lib/ventoy-center/manual-init', str(root / 'state'))
            script = root / 'check.sh'
            script.write_text(mocks + '\n' + source)
            env = dict(os.environ, FIXTURE=temp, FIXTURE_CASE=name,
                       FIXTURE_DAEMON=daemon, FIXTURE_SOCKET=socket, FIXTURE_SHAPE=shape)
            result = subprocess.run(['bash', str(script), '--check', '1'],
                                    env=env, capture_output=True, text=True, timeout=10)
            assert result.returncode == expected, (name, result.returncode, result.stdout, result.stderr)
            assert (sentinel / 'marker').read_text() == 'keep\n'
            assert sentinel.stat().st_mode & 0o777 == 0o700
            if expected == 0:
                assert runtime.stat().st_mode & 0o777 == 0o755
                assert 'SSH_CONFIG_VERIFIED' in result.stdout
                assert 'SSH_PASSWORD_LOGIN_VERIFIED' not in result.stdout
            else:
                assert 'SSH_CONFIG_VERIFIED' not in result.stdout
            if shape in ('existing', 'writable', 'private', 'owner'):
                assert (runtime / 'marker').read_text() == 'keep\n'
                expected_mode = {'writable': 0o777, 'private': 0o700}.get(shape, 0o755)
                assert runtime.stat().st_mode & 0o777 == expected_mode
            if shape == 'symlink':
                assert runtime.is_symlink()
            if shape == 'file':
                assert runtime.read_text() == 'keep\n'
            if (root / 'services').exists():
                assert not any(line.startswith(('start ', 'stop ', 'restart ', 'reload ', 'enable '))
                               for line in (root / 'services').read_text().splitlines())
            if shape not in ('missing', 'existing', 'concurrent'):
                assert not (root / 'sshd-calls').exists(), name
    print('PASS: first-connection SSH socket, safe runtime creation, unchanged unsafe paths and real failure exits')


if __name__ == '__main__':
    checks()
