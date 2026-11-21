"""Install only FYHOCT components through the package's documented interface."""
from __future__ import print_function

import json
import os
import re
import signal
import subprocess
import tempfile
import time

from fyhoc_unlock import password_bytes, trusted_binary

PACKAGE = 'sckoct-fyh'
COMPONENTS = ('oc-engine-linux.tar.gz.enc', 'oc-deps-linux.tar.gz.enc')


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
                raise RuntimeError('FYHOCT command timed out')
            if proc.returncode:
                raise RuntimeError('FYHOCT command failed (exit %s)' % proc.returncode)
            if read_result:
                output.seek(0)
                return output.read(1024 * 1024 + 1)
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()


def ready(binary):
    try:
        data = json.loads(call(binary, ['api', 'ready', '--api', '1'], 90,
                               read_result=True).decode('utf-8'))
        components = data['data']['components']
        return (data.get('ok') is True and components.get('engine') is True
                and components.get('deps') is True)
    except (ValueError, KeyError, AttributeError, TypeError, RuntimeError):
        return False


def configure(directory, key):
    binary = trusted_binary('fyhoct')
    if not ready(binary):
        call(binary, ['install', '--yes', '--engine', os.path.join(directory, COMPONENTS[0])],
             900, directory, key)
    check()
    print('FYHOCT_VERIFIED: engine and dependencies installed.')


def check():
    if not ready(trusted_binary('fyhoct')):
        raise RuntimeError('FYHOCT engine or dependencies are not ready; rerun setup --software')
