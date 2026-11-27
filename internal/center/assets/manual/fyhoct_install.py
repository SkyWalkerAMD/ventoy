"""Install only FYHOCT components through the package's documented interface."""
from __future__ import print_function

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time

from fyhoc_unlock import password_bytes, trusted_binary

PACKAGE = 'sckoct-fyh'
COMPONENTS = ('oc-engine-linux.tar.gz.enc', 'oc-deps-linux.tar.gz.enc')
BACKEND_CONFIG = '/etc/fyhoct/fyhoct.conf'
INSTALL_ERRORS = {
    65: 'component key or archive compatibility check failed',
    66: 'a required local component archive was not accepted',
    69: 'required host dependencies or the container runtime are unavailable',
    75: 'the operation is busy or temporarily unavailable',
    77: 'the host denied an operation required by the installer',
}
READINESS_REASONS = {
    'program_incomplete': 'program files are incomplete',
    'engine_missing': 'engine is missing',
    'deps_missing': 'dependencies are missing',
    'lockdown': 'kernel lockdown is active',
    'platform_unsupported': 'the platform is not supported for this operation',
}


def supported(version):
    match = re.match(r'^(?:[0-9]+:)?([0-9]+)\.([0-9]+)\.([0-9]+)(?:-|$)', version)
    return bool(match and tuple(map(int, match.groups())) >= (1, 2, 6))


def load_key(client):
    response = client.get('fyhoct-install', {})
    try:
        settings = json.loads(response.read(2048).decode('utf-8'))
        if settings.get('enabled') is True:
            key = password_bytes(settings.get('key'))
            if len(key) == 32:
                return key.decode('ascii')
    except (ValueError, RuntimeError, AttributeError):
        pass
    finally:
        response.close()
    raise RuntimeError('FYHOCT installation key is missing or invalid')


def call(binary, args, timeout, directory='/', key=None, read_result=False):
    env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C', 'HOME': '/root'}
    if key is not None:
        env['FYHOCT_DEPS_KEY'] = key
    with open(os.devnull, 'rb+') as null, tempfile.TemporaryFile() as output:
        proc = subprocess.Popen([binary] + args, stdin=null, stderr=null,
                                stdout=output if read_result else null,
                                cwd=directory, env=env, preexec_fn=os.setsid)
        deadline = time.time() + timeout
        try:
            while proc.poll() is None and time.time() < deadline:
                time.sleep(0.1)
            if proc.poll() is None:
                raise RuntimeError('FYHOCT %s timed out' % args[0])
            if proc.returncode:
                hint = INSTALL_ERRORS.get(proc.returncode) if args[0] == 'install' else None
                raise RuntimeError('FYHOCT %s failed (exit %s)%s; see /var/log/fyhoct' %
                                   (args[0], proc.returncode, ': ' + hint if hint else ''))
            if read_result:
                output.seek(0)
                return output.read(1024 * 1024 + 1)
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()


def backend():
    value = None
    try:
        with open(BACKEND_CONFIG) as config:
            for line in config:
                if line.startswith('FYHOCT_BACKEND='):
                    value = line.split('=', 1)[1].strip().strip('\"\'')
    except IOError:
        pass
    return {'native': 'native', 'tain': 'tain', 'container': 'tain', 'rootfs': 'rootfs'}.get(value)


def readiness(binary):
    raw = call(binary, ['api', 'ready', '--api', '1'], 90, read_result=True)
    try:
        envelope = json.loads(raw.decode('utf-8'))
        data = envelope['data']
        if (envelope.get('ok') is True and isinstance(data.get('ready'), bool)
                and isinstance(data.get('components'), dict)):
            return data
    except (ValueError, KeyError, AttributeError, TypeError):
        pass
    raise RuntimeError('FYHOCT returned an invalid readiness response; see /var/log/fyhoct')


def missing_components(data):
    return any(data['components'].get(name) is not True for name in ('engine', 'deps'))


def container_running():
    raw = call(trusted_binary('fyhoct-tain'), ['api-state'], 30, read_result=True)
    lines = raw.splitlines()
    return b'running=1' in lines and b'image=1' in lines


def configure(directory, key):
    binary = trusted_binary('fyhoct')
    try:
        current = backend()
        initialized = bool(current) and not missing_components(readiness(binary))
        if initialized and current == 'tain':
            initialized = container_running()
    except (RuntimeError, OSError):
        initialized = False
    if not initialized:
        print('FYHOCT_INSTALL: initializing the engine and dependencies with the official installer.')
        # FYHOCT picks the deps archive from its working directory. Supply
        # only the two verified releases there so older matching tools files
        # cannot be picked ahead of the intended archive.
        work = tempfile.mkdtemp(prefix='.ventoy-fyhoct-', dir=directory)
        try:
            for name in COMPONENTS:
                os.link(os.path.join(directory, name), os.path.join(work, name))
            call(binary, ['install', '--yes', '--engine', os.path.join(work, COMPONENTS[0])],
                 900, work, key)
        finally:
            shutil.rmtree(work)
    check(binary)


def check(binary):
    data = readiness(binary)
    if data['ready'] is not True or missing_components(data):
        reasons = data.get('blocked_by')
        details = [message for code, message in sorted(READINESS_REASONS.items())
                   if isinstance(reasons, list) and code in reasons]
        raise RuntimeError('FYHOCT is not ready: %s; see /var/log/fyhoct' %
                           (', '.join(details) or 'the official readiness check did not pass'))
    current = backend()
    if not current:
        raise RuntimeError('FYHOCT did not save a supported backend; see /var/log/fyhoct')
    if current == 'tain' and not container_running():
        raise RuntimeError('FYHOCT dependency image or container is not running; see /var/log/fyhoct')
