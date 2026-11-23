#!/usr/bin/env python
"""Install the controller's matching default group and resolve missing dependencies.

Python 2.7.9+ / 3.x, using the installed package manager. All files are downloaded
and checked before a transaction. Distribution compatibility is declared by the
administrator's directory placement; internal package names/versions/architectures
and dependencies are checked locally. Package maintainer scripts are trusted code.
"""
from __future__ import print_function
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
import time
try:
    from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
    from urllib.parse import urlencode, urlsplit
except ImportError:
    from urllib2 import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
    from urllib import urlencode
    from urlparse import urlsplit

HERE = os.path.dirname(os.path.realpath(__file__))
STATE = '/var/lib/ventoy-center/software'
ARCHIVES = '/root/ventoy-tools'
STAGING = '/var/tmp'
RPM_IDS = ('centos', 'rocky', 'almalinux', 'rhel', 'ol', 'scientific', 'anolis')
# Deliver these packages for an operator to install separately. Match the native
# package identity, not the downloaded filename (which can be renamed).
COPY_ONLY_PACKAGES = ('sckoct-fyh', 'sckoct-pub', 'sckoct-pub-suite')
HASH = re.compile(r'^[0-9a-f]{64}$')
NAME = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9.+_-]*$')
FILENAME = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._+~-]{0,240}\.(deb|rpm)$')
ARCHIVE_NAME = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._+~-]{0,240}\.(?:tar\.gz|tgz|zip)\Z')
COPY_NAME = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._+~-]{0,247}\Z')
MAX_FILE = 4 * 1024**3
MAX_TOTAL = 8 * 1024**3


def copy_only(name, policy=COPY_ONLY_PACKAGES):
    return name.split(':', 1)[0] in policy


def run(args, echo=False):
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         env=dict(os.environ, LC_ALL='C', DEBIAN_FRONTEND='noninteractive'))
    if echo:
        chunks = []
        for line in iter(p.stdout.readline, b''):
            chunks.append(line)
            sys.stdout.write(line.decode('utf-8', 'replace'))
            sys.stdout.flush()
        p.wait()
        data = b''.join(chunks).decode('utf-8', 'replace')
    else:
        data = p.communicate()[0].decode('utf-8', 'replace')
    if p.returncode:
        error = RuntimeError('%s failed (exit %s):\n%s' % (args[0], p.returncode, data[-12000:]))
        error.output = data
        raise error
    return data.strip()


def target():
    values = {}
    with open('/etc/os-release') as f:
        for line in f:
            if '=' in line and not line.lstrip().startswith('#'):
                k, v = line.strip().split('=', 1)
                words = shlex.split(v)
                if len(words) == 1:
                    values[k] = words[0]
    distro, version = values.get('ID'), values.get('VERSION_ID', '')
    if distro in ('ubuntu', 'debian'):
        arch = run(['dpkg', '--print-architecture'])
    elif distro in RPM_IDS:
        arch = run(['rpm', '--eval', '%{_arch}'])
    else:
        raise RuntimeError('Unsupported distribution: %s' % distro)
    if not re.match(r'^[0-9]+(\.[0-9]+){0,2}$', version):
        raise RuntimeError('Invalid distribution version')
    return dict(os=distro, version=version, arch=arch)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Software server redirect refused')


class Client(object):
    def __init__(self, config):
        self.origin = config['url'].rstrip('/')
        u = urlsplit(self.origin)
        if (u.username or u.password or u.path or u.query or u.fragment or
                not (u.scheme == 'https' or (u.scheme == 'http' and u.hostname in ('127.0.0.1', '::1')))):
            raise RuntimeError('Software server must be an HTTPS origin')
        self.token = config['token']
        if not HASH.match(self.token):
            raise RuntimeError('Invalid software download credential')
        ca = config.get('ca_file')
        if ca and ca != 'software-ca.crt':
            raise RuntimeError('Invalid software CA path')
        context = ssl.create_default_context(cafile=os.path.join(HERE, ca) if ca else None)
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=context))

    def get(self, endpoint, params):
        request = Request(self.origin + '/software/v1/' + endpoint + '?' + urlencode(params),
                          headers={'Authorization': 'Bearer ' + self.token})
        return self.opener.open(request, timeout=60)

    def manifest(self, wanted):
        response = self.get('manifest', wanted)
        try:
            data = response.read(1024*1024 + 1)
        finally:
            response.close()
        if len(data) > 1024*1024:
            raise RuntimeError('Manifest is too large')
        manifest = json.loads(data.decode('utf-8'))
        validate_manifest(manifest, wanted)
        return manifest

    def download(self, item, dest):
        digest, size = hashlib.sha256(), 0
        response = self.get('package', {'path': item['path'], 'sha256': item['sha256']})
        try:
            with open(dest, 'wb') as f:
                while True:
                    block = response.read(1024*1024)
                    if not block:
                        break
                    size += len(block)
                    if size > item['size']:
                        raise RuntimeError('Package size changed: ' + item['path'])
                    digest.update(block)
                    f.write(block)
        finally:
            response.close()
        if size != item['size'] or digest.hexdigest() != item['sha256']:
            raise RuntimeError('Package checksum mismatch: ' + item['path'])


def copy_name(name):
    return (bool(COPY_NAME.match(name)) and not ARCHIVE_NAME.match(name) and
            not name.lower().startswith('ventoy-linux-setup.run') and
            not name.lower().endswith(('.deb', '.rpm', '.part', '.partial', '.tmp',
                                       '.download', '.crdownload', '.swp', '.bak', '~')))


def validate_manifest(manifest, wanted):
    if manifest.get('schema') != 1 or manifest.get('target') != wanted:
        raise RuntimeError('Software manifest target/schema mismatch')
    archives = manifest.get('archives', [])
    copies = manifest.get('copy_files', [])
    if not isinstance(archives, list) or not isinstance(copies, list) or len(archives) + len(copies) > 256:
        raise RuntimeError('Invalid copy file list')
    seen, total = set(), 0
    for items, match in ((archives, ARCHIVE_NAME.match), (copies, copy_name)):
        for item in items:
            path = item.get('path', '')
            if (not match(path) or '/' in path or path in seen or
                    not HASH.match(item.get('sha256', '')) or
                    not isinstance(item.get('size'), (int, type(MAX_FILE))) or not 0 < item['size'] <= MAX_FILE):
                raise RuntimeError('Invalid copy file in manifest')
            seen.add(path)
            total += item['size']
    if total > MAX_TOTAL:
        raise RuntimeError('Software files exceed 8 GiB')
    group = manifest.get('group')
    if group is None:
        return
    versions = [wanted['version']]
    if wanted['os'] != 'ubuntu':
        versions.append(wanted['version'].split('.')[0])
    if (group.get('os') != wanted['os'] or group.get('arch') != wanted['arch'] or
            group.get('version') not in versions or group.get('errors')):
        raise RuntimeError('Software group is not compatible with this host')
    prefix = '/'.join([group['os'], group['version'], group['arch'], 'default'])
    flat = group.get('id') == 'auto/' + prefix
    if group.get('id') != prefix and not flat:
        raise RuntimeError('Invalid software group identifier')
    files = group.get('files', [])
    if not isinstance(files, list) or not 0 < len(files) or len(files) + len(archives) + len(copies) > 256:
        raise RuntimeError('Default group and copy files must contain 1..256 files')
    ext = '.deb' if wanted['os'] in ('ubuntu', 'debian') else '.rpm'
    for item in files:
        path = item.get('path', '')
        name = path.rsplit('/', 1)[-1]
        if (path != (name if flat else prefix + '/' + name) or not FILENAME.match(name) or not path.endswith(ext) or
                path in seen or not HASH.match(item.get('sha256', '')) or
                not isinstance(item.get('size'), (int, type(MAX_FILE))) or not 0 < item['size'] <= MAX_FILE):
            raise RuntimeError('Invalid package in manifest')
        seen.add(path)
        total += item['size']
    if total > MAX_TOTAL:
        raise RuntimeError('Default group exceeds 8 GiB')


def protected(name):
    patterns = ('kernel* linux-image* linux-headers* linux-modules* linux-generic* linux-virtual* '
                'linux-lowlatency* linux-oem* linux-aws* linux-azure* linux-gcp* linux-gke* '
                'linux-oracle* linux-kvm* linux-raspi* linux-riscv*').split()
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def metadata(file, family, arch, policy=COPY_ONLY_PACKAGES):
    if family == 'deb':
        result = run(['dpkg-deb', '-f', file, 'Package', 'Version', 'Architecture', 'Provides'])
        fields = {}
        for line in result.splitlines():
            if ': ' in line:
                k, v = line.split(': ', 1)
                fields[k.lower()] = v
        name, version, package_arch = fields.get('package', ''), fields.get('version', ''), fields.get('architecture', '')
        provides = fields.get('provides', '')
    else:
        result = run(['rpm', '-qp', '--qf', '%{NAME}\n%{EPOCHNUM}:%{VERSION}-%{RELEASE}\n%{ARCH}\n', file])
        # rpm can emit signature warnings before its query output.
        name, version, package_arch = result.splitlines()[-3:]
    if not NAME.match(name) or not version or package_arch not in (arch, 'all' if family == 'deb' else 'noarch'):
        raise RuntimeError('Invalid package metadata or architecture: ' + os.path.basename(file))
    package = dict(name=name, version=version, arch=package_arch, target_arch=arch, file=file)
    if copy_only(name, policy):
        return package
    if family == 'rpm':
        provides = run(['rpm', '-qp', '--provides', file])
        obsoletes = run(['rpm', '-qp', '--obsoletes', file])
        installed_names = set(k.split(':')[0] for k in installed('rpm'))
        for obsolete in obsoletes.splitlines():
            replaced = obsolete.split()[0] if obsolete.split() else ''
            if replaced in installed_names or protected(replaced):
                raise RuntimeError('RPM would obsolete an installed/protected package: ' + replaced)
    if protected(name) or any(protected(x) for x in re.findall(r'[a-zA-Z0-9][a-zA-Z0-9.+_-]*', provides)):
        raise RuntimeError('Kernel packages cannot be distributed through software setup: ' + name)
    return package


def installed(family):
    result = {}
    if family == 'deb':
        data = run(['dpkg-query', '-W', '-f=${Package}\t${Architecture}\t${Version}\t${db:Status-Status}\n'])
        for line in data.splitlines():
            parts = line.split('\t')
            if len(parts) == 4 and parts[3] == 'installed':
                result[parts[0] + ':' + parts[1]] = parts[2]
    else:
        data = run(['rpm', '-qa', '--qf', '%{NAME}\t%{ARCH}\t%{EPOCHNUM}:%{VERSION}-%{RELEASE}\n'])
        # Keep all installed kernel versions, including installonly packages.
        for line in data.splitlines():
            parts = line.split('\t')
            if len(parts) == 3:
                key = parts[0] + ':' + parts[1]
                result.setdefault(key, []).append(parts[2])
        result = dict((k, '|'.join(sorted(v))) for k, v in result.items())
    return result


def compare_versions(a, b, family):
    if not all(re.match(r'^[A-Za-z0-9:._+~^-]+$', v) for v in (a,b)):
        raise RuntimeError('Invalid package version')
    if a == b:
        return 0
    if family == 'deb':
        for op, value in (('eq', 0), ('gt', 1), ('lt', -1)):
            rc = subprocess.call(['dpkg', '--compare-versions', a, op, b])
            if rc == 0:
                return value
            if rc != 1:
                raise RuntimeError('Cannot compare Debian package versions')
    else:
        def evr(v):
            epoch, rest = v.split(':',1)
            version, release = rest.rsplit('-',1)
            return epoch, version, release
        ea, va, ra = evr(a); eb, vb, rb = evr(b)
        if int(ea) != int(eb):
            return 1 if int(ea) > int(eb) else -1
        try:
            import rpm
            return rpm.labelCompare((ea,va,ra), (eb,vb,rb))
        except ImportError:
            # Native RPM Lua comparator preserves epochs, ~ prereleases, etc.;
            # never approximate package ordering with strings or filenames.
            for x,y in ((va,vb),(ra,rb)):
                result = int(run(['rpm','--eval','%{lua:print(rpm.vercmp("'+x+'", "'+y+'"))}']))
                if result:
                    return 1 if result > 0 else -1
            return 0
    raise RuntimeError('Cannot compare package versions')


def current_version(current, package, family):
    # A noarch/all package may have replaced a native-architecture build.
    arches = (package['arch'],package.get('target_arch',package['arch']),'all' if family=='deb' else 'noarch')
    versions = [v for k,values in current.items() if k.split(':')[0] == package['name'] and k.split(':')[1] in arches for v in values.split('|')]
    latest = None
    for version in versions:
        if latest is None or compare_versions(version,latest,family)>0:
            latest=version
    return latest


def select_latest(candidates, family, arch):
    selected = {}
    for p in candidates:
        old = selected.get(p['name'])
        if old is None:
            selected[p['name']] = p
            continue
        cmp = compare_versions(p['version'],old['version'],family)
        if cmp > 0 or (cmp == 0 and p['arch'] == arch and old['arch'] != arch):
            selected[p['name']] = p
        elif cmp == 0 and p['arch'] == old['arch'] and p.get('sha256') != old.get('sha256'):
            raise RuntimeError('Conflicting builds share the same package name/version/architecture: ' + p['name'])
    return [selected[name] for name in sorted(selected)]


def rpm_scriptlet_failures():
    try:
        with open(os.path.join(STATE, 'rpm-scriptlet-failures.json')) as f:
            return json.load(f)
    except IOError as e:
        if e.errno == 2:
            return dict(packages={}, unknown=False, errors=[])
        raise


def record_rpm_scriptlet_errors(output):
    # RPM 4 / DNF can return zero after a failed %post. Package presence alone
    # does not prove success. LC_ALL=C makes their diagnostics predictable.
    errors = [line.strip() for line in output.splitlines() if
              re.search(r'(?i)(?:scriptlet.*failed|error in .*scriptlet|failed to .*scriptlet)', line)]
    if not errors:
        return
    current = installed('rpm')
    failure = rpm_scriptlet_failures()
    labels = []
    for line in errors:
        match = re.search(r'%[a-z]+\(([^)]+)\).*scriptlet.*failed', line, re.I)
        if match:
            labels.append(match.group(1))
        match = re.search(r'scriptlet in rpm package ([A-Za-z0-9.+_-]+)', line)
        if match:
            labels.append(match.group(1))
    matched = set()
    for key, versions in current.items():
        name, arch = key.split(':', 1)
        identifiers = [name]
        for version in versions.split('|'):
            identifiers += [name + '-' + version + '.' + arch,
                            name + '-' + version.split(':', 1)[-1] + '.' + arch]
        if any(label in identifiers for label in labels):
            failure['packages'][key] = versions
            matched.update(label for label in labels if label in identifiers)
    # An unidentified failure (e.g. an uninstalled trigger owner) still requires
    # review; do not lose it merely because a package/version cannot be mapped.
    if not labels or len(matched) != len(set(labels)):
        failure['unknown'] = True
    failure['errors'] = (failure['errors'] + errors)[-30:]
    save_json(failure, 'rpm-scriptlet-failures.json')
    raise RuntimeError('RPM installation script failed; package records may exist, '
                       'but software installation is incomplete:\n' + '\n'.join(errors))


def run_rpm_transaction(args):
    try:
        output = run(args, echo=True)
    except RuntimeError as error:
        record_rpm_scriptlet_errors(getattr(error, 'output', str(error)))
        raise
    record_rpm_scriptlet_errors(output)


def check_rpm_scriptlets(current, policy=COPY_ONLY_PACKAGES):
    failure = rpm_scriptlet_failures()
    unresolved = [key for key, version in failure['packages'].items()
                  if current.get(key) == version]
    excluded = [key for key in unresolved if copy_only(key, policy)]
    if excluded:
        print('COPY_ONLY_WARNING: previous installation failures remain recorded for %s; '
              'these packages are excluded from installation verification, not repaired.' % ', '.join(sorted(excluded)))
    unresolved = [key for key in unresolved if not copy_only(key, policy)]
    if unresolved or failure['unknown']:
        raise RuntimeError('Unresolved RPM installation script failure: %s. '
                           'Install a corrected package version or repair and review '
                           '%s; an unchanged rerun cannot certify this installation.' %
                           (', '.join(sorted(unresolved)) or 'unidentified scriptlet',
                            os.path.join(STATE, 'rpm-scriptlet-failures.json')))


def verify(packages, family, before=None, policy=COPY_ONLY_PACKAGES):
    if any(copy_only(p['name'], policy) for p in packages):
        raise RuntimeError('Copy-only packages cannot be certified as installed; rerun setup --software to refresh the report')
    after = installed(family)
    if family == 'rpm':
        check_rpm_scriptlets(after, policy)
    for p in packages:
        current = current_version(after,p,family)
        if current is None or compare_versions(current,p['version'],family)<0:
            raise RuntimeError('Installed package verification failed: ' + p['name'])
    if before is not None:
        old_kernel = dict((k, v) for k, v in before.items() if protected(k.split(':')[0]))
        new_kernel = dict((k, v) for k, v in after.items() if protected(k.split(':')[0]))
        if new_kernel != old_kernel:
            raise RuntimeError('Kernel package set changed; inspect software transaction log')
    return after


def transaction(packages, family, work, allow_dependencies=True, policy=COPY_ONLY_PACKAGES):
    if any(copy_only(p['name'], policy) for p in packages):
        raise RuntimeError('Copy-only packages must not enter an installation transaction')
    before = installed(family)
    pending = [p for p in packages if current_version(before,p,family) is None or compare_versions(current_version(before,p,family),p['version'],family)<0]
    for p in packages:
        if p not in pending:
            print('SKIP: %s is already installed at the requested version or newer.' % p['name'])
    if pending:
        files = [p['file'] for p in pending]
        if family == 'deb':
            for folder in ('lists/partial', 'archives/partial', 'sourceparts'):
                os.makedirs(os.path.join(work, folder))
            sources = os.path.join(work, 'sources.list')
            with open(sources, 'w'):
                pass
            base = ['apt-get', '-o', 'Dir::Etc::sourcelist='+sources, '-o', 'Dir::Etc::sourceparts='+os.path.join(work,'sourceparts'),
                    '-o', 'Dir::State::lists=' + os.path.join(work, 'lists'),
                    '-o', 'Dir::Cache::archives=' + os.path.join(work, 'archives'),
                    '-o', 'APT::Get::List-Cleanup=0', '-o', 'Dpkg::Options::=--force-confold',
                    '--no-remove', '--no-install-recommends', '--no-install-suggests']
            try:
                plan = run(base + ['--simulate', 'install'] + files, echo=True)
            except RuntimeError:
                if not allow_dependencies:
                    raise
                print('Resolving missing dependencies from configured repositories (no upgrade command).')
                # Refresh indices only for this explicit invocation. Timers and
                # periodic-update settings remain disabled. No repository added.
                http_timeout = '1200' if os.path.isfile('/etc/apt/apt.conf.d/90ventoy-installer-cache') else '30'
                run(['apt-get', '-o', 'APT::Update::Error-Mode=any', '-o', 'Acquire::Retries=1', '-o', 'Acquire::http::Timeout='+http_timeout, '-o', 'Acquire::https::Timeout=30', 'update'], echo=True)
                base = ['apt-get', '--no-remove', '--no-install-recommends', '--no-install-suggests',
                        '-o', 'Dpkg::Options::=--force-confold']
                plan = run(base + ['--simulate', 'install'] + files, echo=True)
            for line in plan.splitlines():
                if line.startswith('Remv ') or (line.startswith('Inst ') and protected(line.split()[1])):
                    raise RuntimeError('Package transaction would remove software or change the kernel')
                if line.startswith(('Inst ', 'Conf ')) and copy_only(line.split()[1], policy):
                    raise RuntimeError('APT would install or configure a copy-only package: ' + line.split()[1])
            run(base + ['-y', 'install'] + files, echo=True)
        else:
            # First resolve against the supplied set and installed database.
            # Use configured repositories only if dependencies are missing.
            try:
                run(['rpm', '-U', '--test'] + files, echo=True)
            except RuntimeError:
                if not allow_dependencies:
                    raise
                manager = next((p for p in ('/usr/bin/dnf', '/usr/bin/yum') if os.path.isfile(p)), None)
                if not manager:
                    raise RuntimeError('Missing dependencies; yum/dnf is not available')
                # Only this install transaction and its dependencies, never a
                # whole-system update/upgrade/distro-sync. Preserve user locks.
                args = [manager, '-y', '--exclude=kernel*', '--setopt=obsoletes=0', '--setopt=install_weak_deps=False', '--setopt=timeout=30', '--setopt=retries=1']
                args += ['--exclude=' + name for name in policy]
                run(args + ['--setopt=tsflags=test', 'install'] + files, echo=True)
                run_rpm_transaction(args + ['install'] + files)
            else:
                run_rpm_transaction(['rpm', '-Uvh'] + files)
    verify(packages, family, before, policy)
    return len(pending)


def read_state(name, default):
    try:
        with open(os.path.join(STATE, name)) as f:
            return json.load(f)
    except IOError as error:
        if error.errno != 2:
            raise
        return default


def tracked_transaction(packages, family, work, policy=COPY_ONLY_PACKAGES):
    before = installed(family)
    owned = read_state('installed-by-setup.json', {})
    try:
        return transaction(packages, family, work, policy=policy)
    finally:
        after = installed(family)
        updated = dict(owned)
        for package in packages:
            key = package['name'] + ':' + package['arch']
            if key in after and (key not in before or
                                 (key in owned and owned[key] == before.get(key))):
                updated[key] = after[key]
        if updated != owned:
            save_json(updated, 'installed-by-setup.json')


def save_report(data):
    save_json(data, 'last-result.json')


def save_json(data, name):
    if not os.path.isdir(STATE):
        os.makedirs(STATE, 0o700)
    fd, tmp = tempfile.mkstemp(prefix='.result-', dir=STATE)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp, os.path.join(STATE, name))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def archive_matches(item):
    path = os.path.join(ARCHIVES, item['path'].rsplit('/', 1)[-1])
    if not os.path.lexists(path):
        return False
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_size != item['size']:
        return False
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest() == item['sha256']


def archive_directory():
    if not os.path.lexists(ARCHIVES):
        os.makedirs(ARCHIVES, 0o700)
    info = os.lstat(ARCHIVES)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022 or
            os.path.realpath(ARCHIVES) != ARCHIVES):
        raise RuntimeError('Archive destination must be a private, non-symlink directory: ' + ARCHIVES)


def sync_archives(client, items, packages=False):
    if not items:
        return
    archive_directory()
    record = os.path.join(STATE, 'archive-state.json')
    records = {}
    if os.path.exists(record):
        with open(record) as f:
            records = json.load(f)
    for item in items:
        name = item['path'].rsplit('/', 1)[-1]
        dest = os.path.join(ARCHIVES, name)
        if archive_matches(item):
            print('FILE_VERIFIED: %s (unchanged; no download)' % dest)
        else:
            previous = records.get(name)
            if os.path.lexists(dest) and (not previous or not archive_matches(previous)):
                raise RuntimeError('Archive destination was modified or is unmanaged; file preserved: ' + dest)
            space = os.statvfs(ARCHIVES)
            if space.f_bavail * space.f_frsize < item['size'] + 128*1024**2:
                raise RuntimeError('Insufficient free space for archive: ' + name)
            fd, temp = tempfile.mkstemp(prefix='.download-', dir=ARCHIVES)
            os.close(fd)
            try:
                client.download(item, temp)
                os.chmod(temp, 0o600)
                with open(temp, 'rb') as f:
                    os.fsync(f.fileno())
                if os.path.lexists(dest) and (not previous or not archive_matches(previous)):
                    raise RuntimeError('Archive destination changed during download; preserved: ' + dest)
                os.rename(temp, dest)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
            purpose = 'package retained; installation depends on package policy' if packages else 'not extracted or executed'
            print('FILE_SAVED: %s (SHA-256 verified; %s)' % (dest, purpose))
        records[name] = item
        save_json(records, 'archive-state.json')


def verify_archives(items):
    if items:
        # Checks never create or repair the destination.
        if not os.path.isdir(ARCHIVES) or os.path.realpath(ARCHIVES) != ARCHIVES:
            raise RuntimeError('Archive destination is missing or is a symlink')
        for item in items:
            if not archive_matches(item):
                raise RuntimeError('Archive missing or changed: ' + item['path'])
        print('FILES_VERIFIED: %s files in %s' % (len(items), ARCHIVES))


def configure_nodes(client, family):
    import node_join
    nodes = node_join.fetch(client)
    return node_join.configure(nodes, set(name.split(':')[0] for name in installed(family)))


def install_fyhoct(client, config, manifest, wanted, family):
    import fyhoct_install
    if config.get('fyhoct_install') is not True:
        raise RuntimeError('FYHOCT installation is not configured on the center')
    major = wanted['version'].split('.')[0]
    if family == 'rpm' and int(major) < 8:
        raise RuntimeError('FYHOCT requires Enterprise Linux 8 or newer')
    policy = tuple(name for name in COPY_ONLY_PACKAGES if name != fyhoct_install.PACKAGE)
    group = manifest['group']
    prefix = fyhoct_install.PACKAGE + ('_' if family == 'deb' else '-')
    files = [item for item in (group['files'] if group else [])
             if item['path'].rsplit('/', 1)[-1].startswith(prefix)]
    archives = [item for item in manifest.get('archives', []) + manifest.get('copy_files', [])
                if item['path'] in fyhoct_install.COMPONENTS]
    if not files:
        raise RuntimeError('No matching sckoct-fyh package in the center tools library')
    if set(item['path'] for item in archives) != set(fyhoct_install.COMPONENTS):
        raise RuntimeError('FYHOCT component bundles are missing from the center tools library')
    sync_archives(client, files, packages=True)
    verify_archives(files)
    candidates = []
    for item in files:
        path = os.path.join(ARCHIVES, item['path'].rsplit('/', 1)[-1])
        package = metadata(path, family, wanted['arch'], policy)
        if package['name'] != fyhoct_install.PACKAGE or not fyhoct_install.supported(package['version']):
            continue
        if family == 'rpm' and not re.search(r'\.el' + re.escape(major) + r'(?:[._-]|$)', package['version']):
            continue
        candidates.append(package)
    if not candidates:
        raise RuntimeError('No compatible sckoct-fyh 1.2.6 or newer package was found')
    selected = select_latest(candidates, family, wanted['arch'])
    sync_archives(client, archives)
    verify_archives(archives)
    key = fyhoct_install.load_key(client)
    work = tempfile.mkdtemp(prefix='ventoy-fyhoct-', dir=STAGING)
    try:
        tracked_transaction(selected, family, work, policy=policy)
        before_components = installed(family)
        try:
            fyhoct_install.configure(ARCHIVES, key)
        finally:
            verify(selected, family, before_components, policy)
    finally:
        shutil.rmtree(work)
    print('FYHOCT_VERIFIED: engine and dependencies installed; kernel package set preserved.')


def execute(mode):
    wanted = target()
    family = 'deb' if wanted['os'] in ('ubuntu', 'debian') else 'rpm'
    if mode == '--check-software':
        with open(os.path.join(STATE, 'last-result.json')) as f:
            report = json.load(f)
        if report.get('status') != 'verified' or report.get('target') != wanted:
            raise RuntimeError('No successfully installed matching software group to verify')
        if report.get('copy_only_policy') != list(COPY_ONLY_PACKAGES):
            raise RuntimeError('Software delivery policy changed; run setup --software before checking')
        verify(report['packages'], family)
        verify_archives(report.get('archives', []))
        verify_archives(report.get('package_files', []))
        if report.get('fyhoc_unlock'):
            import fyhoc_unlock
            fyhoc_unlock.check()
        if report.get('node_join'):
            import node_join
            node_join.check(report['node_join'])
        print('VERIFIED: %s packages are at the requested version or newer.' % len(report['packages']))
        print('COPY_ONLY_VERIFIED: %s package files retained in %s; installation not checked.' %
              (len(report.get('copy_only_packages', [])), ARCHIVES))
        return
    with open(os.path.join(HERE, 'software-client.json')) as f:
        config = json.load(f)
    if not config.get('enabled'):
        if mode == '--install-fyhoct':
            raise RuntimeError('Controller software library is not configured')
        print('SKIPPED: controller software library is not configured.')
        return
    client = Client(config)
    manifest = client.manifest(wanted)
    if mode == '--install-fyhoct':
        install_fyhoct(client, config, manifest, wanted, family)
        return
    group = manifest['group']
    archives = manifest.get('archives', []) + manifest.get('copy_files', [])
    files = group['files'] if group else []
    print('Default software group: %s (%s packages)' % (group['id'] if group else 'none', len(files)))
    print('Copy-only packages: %s.' % ', '.join(COPY_ONLY_PACKAGES))
    for f in files:
        print('  %s  %s bytes  sha256=%s' % (f['path'].split('/')[-1], f['size'], f['sha256']))
    for f in archives:
        print('  FILE (copy only): %s  %s bytes  sha256=%s' % (f['path'], f['size'], f['sha256']))
    if mode == '--list-software':
        return
    if group is None and not archives and not config.get('node_join'):
        print('SKIPPED: no default software group for %(os)s %(version)s %(arch)s.' % wanted)
        return
    # Immutable manifest hashes plus native installed versions allow repeat runs
    # to avoid retransferring already verified payloads. A replaced/new file
    # invalidates the shortcut and is inspected afresh before any transaction.
    previous = os.path.join(STATE, 'last-result.json')
    unchanged = None
    try:
        with open(previous) as f:
            last = json.load(f)
        if (last.get('status') == 'verified' and last.get('target') == wanted and
                last.get('copy_only_policy') == list(COPY_ONLY_PACKAGES) and
                last.get('manifest', {}).get('group') == group):
            verify(last['packages'], family)
            unchanged = last['packages']
    except (IOError, ValueError, RuntimeError):
        pass
    work = tempfile.mkdtemp(prefix='ventoy-software-', dir=STAGING)
    report = dict(status='failed', target=wanted, group=group['id'] if group else None, manifest=manifest,
                  time=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), packages=[], archives=archives,
                  package_files=files, copy_only_policy=list(COPY_ONLY_PACKAGES), copy_only_packages=[])
    node_join_attempted = False
    try:
        sync_archives(client, archives)
        # Also retain packages whose installed versions already satisfy the
        # group. Old setups discarded them; the first new run backfills copies.
        sync_archives(client, files, packages=True)
        candidates = []
        for item in (files if unchanged is None else []):
            dest = os.path.join(ARCHIVES, item['path'].split('/')[-1])
            p = metadata(dest, family, wanted['arch'])
            p['sha256'] = item['sha256']
            if copy_only(p['name']):
                report['copy_only_packages'].append(p)
                continue
            if family == 'rpm':
                tag = re.search(r'\.el([0-9]+)(?:[._-]|$)', p['version'])
                if tag and tag.group(1) != wanted['version'].split('.')[0]:
                    floor = group.get('rpm_min_el', {}).get(p['name'])
                    if not isinstance(floor, int) or int(tag.group(1)) < floor or int(wanted['version'].split('.')[0]) < int(tag.group(1)):
                        raise RuntimeError('RPM Enterprise Linux release does not match this host: ' + p['name'])
            candidates.append(p)
        report['packages'] = select_latest(candidates, family, wanted['arch']) if unchanged is None else unchanged
        if unchanged is not None:
            report['copy_only_packages'] = last.get('copy_only_packages', [])
        for p in report['copy_only_packages']:
            print('COPY_ONLY: %s %s; retained, not installed or upgraded.' % (p['name'], p['version']))
        changed = tracked_transaction(report['packages'], family, work) if report['packages'] and unchanged is None else 0
        if not report['packages']:
            verify([], family)
        verify_archives(archives)
        verify_archives(files)
        policy = os.path.join(HERE, 'linux-update-policy.sh')
        if os.path.isdir('/var/lib/ventoy-center/kernel-policy'):
            run(['sh', policy, '--check'], echo=True)
        if any(name.split(':')[0] == 'fyhoc' for name in installed(family)):
            import fyhoc_unlock
            report['fyhoc_unlock'] = fyhoc_unlock.configure(client)
        if config.get('node_join'):
            node_join_attempted = True
            report['node_join'] = configure_nodes(client, family)
        report['status'], report['changed'] = 'verified', changed
        if unchanged is not None:
            print('VERIFIED: unchanged software group; installed versions and retained package files checked; no installation needed.')
        print('VERIFIED: %s packages installed; %s changed; kernel package set preserved.' % (len(report['packages']), changed))
        print('COPY_ONLY_VERIFIED: %s package files retained in %s; installation not checked.' %
              (len(report['copy_only_packages']), ARCHIVES))
    except Exception as e:
        report['error'] = str(e)
        # A different package's failed maintainer script must not prevent an
        # already installed, verified node from recovering its center binding.
        # Keep the original software failure; never certify the whole group.
        if config.get('node_join') and not node_join_attempted:
            print('NODE_JOIN_CONTINUE: software is incomplete; checking the installed node independently.')
            try:
                report['node_join'] = configure_nodes(client, family)
            except Exception as join_error:
                report['node_join_error'] = str(join_error)
                report['error'] += '\nNode enrollment also failed: ' + str(join_error)
                raise RuntimeError(report['error'])
        raise
    finally:
        for p in report['packages'] + report['copy_only_packages']:
            p.pop('file', None)
        save_report(report)
        shutil.rmtree(work)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('--software', '--list-software', '--check-software', '--install-fyhoct'):
        raise RuntimeError('Use setup --software, --list-software, --check-software or --install-fyhoct')
    if os.geteuid() != 0:
        raise RuntimeError('Run as root or sudo')
    os.umask(0o077)
    import fcntl
    if not os.path.isdir(STATE):
        os.makedirs(STATE, 0o700)
    with open(os.path.join(STATE, 'lock'), 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        execute(sys.argv[1])


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Software setup FAILED: %s' % exc, file=sys.stderr)
        sys.exit(1)
