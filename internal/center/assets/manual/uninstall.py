"""Remove software and files owned by an installed Ventoy setup."""
from __future__ import print_function

import argparse
import errno
import filecmp
import fcntl
import hashlib
import os
import re
import runpy
import shutil
import stat
import sys

import software


def package_targets(current, wanted, include_legacy):
    owned = software.read_state('installed-by-setup.json', {})
    if include_legacy:
        report = software.read_state('last-result.json', {})
        if report.get('target') == wanted:
            legacy = report.get('packages', []) + [
                p for p in report.get('copy_only_packages', []) if p['name'] == 'sckoct-fyh']
            for package in legacy:
                key = package['name'] + ':' + package['arch']
                owned.setdefault(key, package['version'])
    result = []
    for key, version in sorted(owned.items()):
        name, sep, arch = key.partition(':')
        if not sep or not software.NAME.match(name) or not software.NAME.match(arch) or software.protected(name):
            raise RuntimeError('Unexpected package in setup ownership record')
        if key in current and current[key] == version:
            result.append((name, arch))
        elif key in current:
            print('PRESERVED_PACKAGE: %s (version changed outside setup)' % key)
    return result


def removal_commands(family, packages):
    if family == 'deb':
        # Use dpkg directly so dependency resolution cannot select additional
        # packages for removal. dpkg still checks reverse dependencies.
        # Architecture-independent DEBs have to be addressed without :all.
        specs = [name if arch == 'all' else name + ':' + arch for name, arch in packages]
        return ['dpkg', '--no-act', '--remove'] + specs, ['dpkg', '--remove'] + specs
    specs = [name + '.' + arch for name, arch in packages]
    return ['rpm', '-e', '--test'] + specs, ['rpm', '-e'] + specs


def unlink(path):
    try:
        os.unlink(path)
    except OSError as error:
        if error.errno != errno.ENOENT:
            raise


def remove_empty(path):
    try:
        os.rmdir(path)
    except OSError as error:
        if error.errno not in (errno.ENOENT, errno.ENOTEMPTY, errno.EEXIST):
            raise


def managed_archives():
    if not os.path.lexists(software.ARCHIVES):
        return []
    if not os.path.isdir(software.ARCHIVES) or os.path.realpath(software.ARCHIVES) != software.ARCHIVES:
        raise RuntimeError('Unexpected tools directory; files preserved')
    result = []
    for name, item in sorted(software.read_state('archive-state.json', {}).items()):
        if (not software.NAME.match(name) and not software.copy_name(name)) or name != item['path'].rsplit('/', 1)[-1]:
            raise RuntimeError('Unexpected file in setup ownership record')
        path = os.path.join(software.ARCHIVES, name)
        if software.archive_matches(item):
            result.append(item)
        elif os.path.lexists(path):
            print('PRESERVED_FILE: %s (changed since transfer)' % path)
    return result


def remove_units(names):
    for name in names:
        path = '/etc/systemd/system/' + name
        if os.path.isfile(path) and not os.path.islink(path):
            software.run(['systemctl', 'disable', '--now', name], echo=True)
            unlink(path)
    software.run(['systemctl', 'daemon-reload'])


def remove_payloads():
    root = '/opt/ventoy-manual'
    if not os.path.isdir(root) or os.path.realpath(root) != root:
        return
    current = os.path.join(root, 'current')
    for name in os.listdir(root):
        if not re.match(r'^[0-9a-f]{16}$', name):
            continue
        path = os.path.join(root, name)
        checksums = os.path.join(path, 'SHA256SUMS')
        if os.path.islink(path) or os.path.islink(checksums) or not os.path.isfile(checksums):
            continue
        with open(checksums, 'rb') as f:
            if hashlib.sha256(f.read()).hexdigest()[:16] != name:
                continue
        if os.path.islink(current) and os.path.realpath(current) == path:
            unlink(current)
        shutil.rmtree(path)
    remove_empty(root)


def remove_runners(runner):
    standard = '/root/ventoy-linux-setup.run'
    for path in set(filter(None, (runner, standard))):
        directory, name = os.path.split(os.path.abspath(path))
        if os.path.realpath(directory) != directory:
            continue
        for entry in os.listdir(directory):
            if entry != name and not re.match(re.escape(name) + r'\.previous-[0-9a-f]{12}$', entry):
                continue
            candidate = os.path.join(directory, entry)
            info = os.lstat(candidate)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_size > 64*1024*1024:
                continue
            with open(candidate, 'rb') as f:
                header = f.read(32*1024)
            if b'__VENTOY_MANUAL_ARCHIVE__\n' in header and b'Ventoy setup ' in header:
                unlink(candidate + '.sha256')
                unlink(candidate)
    for name, title in (('README-ventoy-setup.txt', b'Ventoy Linux setup'),
                        ('README-ventoy-software.txt', b'Ventoy node software')):
        path = os.path.join('/root', name)
        if os.path.isfile(path) and not os.path.islink(path):
            with open(path, 'rb') as f:
                managed = f.read(len(title)) == title
            if managed:
                unlink(path)


def uninstall(args):
    wanted = software.target()
    family = 'deb' if wanted['os'] in ('ubuntu', 'debian') else 'rpm'
    if args.login_user and family != 'deb':
        raise RuntimeError('--login-user is only supported on Ubuntu and Debian')
    current = software.installed(family)
    packages = package_targets(current, wanted, args.include_legacy_packages)
    archives = managed_archives()
    print('Packages to remove: %s' % (', '.join(name for name, _ in packages) or 'none'))
    print('Managed files to remove: %s' % len(archives))
    print('The setup runner, saved setup payloads and setup services will be removed.')
    if args.include_legacy_packages:
        print('Legacy candidates may include packages originally installed outside setup.')
    if family == 'deb':
        print('Direct root SSH and console password login will be disabled after verifying a sudo user.')
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError('Uninstall requires an interactive terminal')
    if packages:
        check, remove = removal_commands(family, packages)
        software.run(check, echo=True)
    sys.stdout.write('Type yes to uninstall: ')
    sys.stdout.flush()
    if sys.stdin.readline().strip() != 'yes':
        print('UNINSTALL_CANCELED')
        return
    if family == 'deb':
        # install.sh holds manual-init/lock for the entire operation.
        import resource
        from pathlib import Path
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        login = runpy.run_path(os.path.join(software.HERE, 'login-mode.py'))
        login['private_dir'](Path('/var/lib/ventoy-center/manual-init'))
        previous = login['saved_policy']()
        login['restore'](args.login_user or (previous['user'] if previous else 'user'))
    remove_units(('ventoy-manual-init.service', 'ventoy-fyhoc-unlock.service',
                  'ventoy-install-report.timer', 'ventoy-install-report.service'))
    if packages:
        if package_targets(software.installed(family), wanted, args.include_legacy_packages) != packages:
            raise RuntimeError('Installed packages changed during confirmation; rerun uninstall')
        software.run(remove, echo=True)
        after = software.installed(family)
        if any(name + ':' + arch in after for name, arch in packages):
            raise RuntimeError('Package removal verification failed; inspect the package manager output')
    for item in archives:
        if software.archive_matches(item):
            unlink(os.path.join(software.ARCHIVES, item['path'].rsplit('/', 1)[-1]))
    remove_empty(software.ARCHIVES)
    for path in ('/etc/ventoy-center/fyhoc-unlock.key',
                 '/usr/local/lib/ventoy-center/fyhoc_unlock.py',
                 '/var/lib/ventoy-center/manual-init/software-request'):
        unlink(path)
    for name in ('archive-state.json', 'installed-by-setup.json', 'last-result.json'):
        unlink(os.path.join(software.STATE, name))
    helper = '/usr/local/sbin/safe-server-init'
    if (os.path.isfile(helper) and not os.path.islink(helper) and
            filecmp.cmp(helper, os.path.join(software.HERE, 'safe-server-init.sh'), shallow=False)):
        unlink(helper)
    remove_payloads()
    remove_runners(args.runner)
    print('UNINSTALL_COMPLETE: setup-managed packages and files removed.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('runner')
    parser.add_argument('--login-user')
    parser.add_argument('--include-legacy-packages', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Run as root or sudo')
    if not os.path.isdir(software.STATE):
        os.makedirs(software.STATE, 0o700)
    with open(os.path.join(software.STATE, 'lock'), 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        uninstall(args)


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print('UNINSTALL_FAILED: %s' % exc, file=sys.stderr)
        sys.exit(1)
