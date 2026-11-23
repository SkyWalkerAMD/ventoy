#!/usr/bin/env python3
"""Linux release lifecycle. Stage never stops production; activation requires idle media.

All secrets stay in root-only staging/backup files. No ISO content is copied or
deleted. Run --help for commands. Requires Python 3.6+ and systemd.
"""
import argparse
import datetime
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import tarfile
import time
from urllib.parse import urlsplit


def digest(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def read(p):
    return json.loads(Path(p).read_text())


def real(p):
    p = Path(p).absolute()
    if p.resolve() != p:
        raise ValueError('Symlink or noncanonical path: ' + str(p))
    return p


def child(root, name):
    p = real(root / name)
    if root not in p.parents:
        raise ValueError('Path outside managed root')
    return p


def replace(p, data, mode=0o600):
    p = real(p)
    st = p.stat() if p.exists() else None
    tmp = p.with_name(p.name + '.release-next')
    with tmp.open('xb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, (st.st_mode & 0o777) if st else mode)
    if st:
        os.chown(tmp, st.st_uid, st.st_gid)
    os.replace(str(tmp), str(p))
    if shutil.which('restorecon'):
        subprocess.run(['restorecon', str(p)], check=True)


def save(p, data):
    replace(p, (json.dumps(data, indent=2, ensure_ascii=False)+'\n').encode())


class Release:
    def __init__(self, args):
        self.args = args
        self.cfgpath = real(args.config)
        self.cfg = read(self.cfgpath)
        self.root = real(self.cfg['iventoy_root'])
        self.data = real(self.cfg['data_dir'])
        self.state = self.data / 'state.json'
        self.binary = real(args.binary)
        self.base = real(args.releases)
        self.base.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.base, 0o700)
        if not re.match(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$', args.name):
            raise ValueError('Invalid release name')
        self.dir = child(self.base, args.name)
        self.token = Path(self.cfg['admin_token_file']).read_text().strip()

    def api(self, path, body=None, port=None):
        u = urlsplit(self.cfg['public_url'])
        ctx = ssl.create_default_context(cafile=self.cfg.get('bootstrap_ca_file'))
        class LocalHTTPS(http.client.HTTPSConnection):
            def connect(conn):
                # Production may bind only its LAN address. The staging API is
                # deliberately loopback-only, with the production TLS identity.
                sock = socket.create_connection(('127.0.0.1' if port is not None else u.hostname, port or u.port or 443), conn.timeout)
                conn.sock = ctx.wrap_socket(sock, server_hostname=u.hostname)
        conn = LocalHTTPS(u.hostname, timeout=180)
        try:
            conn.request('GET' if body is None else 'POST', path,
                         None if body is None else json.dumps(body),
                         {'Authorization': 'Bearer '+self.token, 'Content-Type': 'application/json'})
            r = conn.getresponse()
            b = r.read()
            if r.status != 200:
                raise RuntimeError('Controller HTTP %s at %s' % (r.status, path))
            return b
        finally:
            conn.close()

    def idle(self):
        jobs = [j['id'] for j in read(self.state)['jobs']
                if j['state'] not in ('installed', 'failed', 'canceled', 'enrolled')]
        connections = subprocess.check_output(['ss', '-Htn', 'state', 'established',
            '( sport = :3260 or sport = :10809 or sport = :12049 or sport = :10445 or sport = :16000 )'], universal_newlines=True)
        if jobs or connections.strip():
            raise RuntimeError('Active tasks or network media clients: publication deferred')

    def healthy(self, version):
        for _ in range(60):
            try:
                if json.loads(self.api('/healthz'))['version'] == version:
                    subprocess.run(['systemctl', 'is-active', '--quiet', 'iventoy.service', 'ventoy-center.service'], check=True)
                    return
            except Exception:
                time.sleep(.5)
        raise RuntimeError('Service health check failed')

    def audit_published(self, count):
        audit = json.loads(self.api('/api/operations/audit', {}))
        entries = audit.get('entries', [])
        if not audit.get('tools_setup_matches') or len(entries) != count or not all(e.get('passed') for e in entries):
            raise RuntimeError('Published setup or entry audit failed')

    def native(self, method, **values):
        url = self.cfg.get('iventoy_url', 'http://127.0.0.1:26000').rstrip('/')
        result = subprocess.run(['curl', '--fail', '--silent', '--show-error', '--max-time', '10',
            '-H', 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8',
            '--data-binary', '@-', url+'/iventoy/json'],
            input=json.dumps(dict(method=method, **values)), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True, check=True)
        return json.loads(result.stdout)

    def network_snapshot(self):
        status = self.native('query_status')['status']
        if status not in ('ready', 'running'):
            raise RuntimeError('iVentoy network is transitioning; publication deferred')
        snapshot = dict(status=status)
        if status == 'running':
            snapshot['start'] = self.network_start()
        return snapshot

    def network_start(self):
        fields = ('ip', 'mask', 'gw', 'pool_begin', 'pool_end', 'dns_server')
        addresses = self.native('sys_ip_list')
        if isinstance(addresses, list):
            host = urlsplit(self.cfg['public_url']).hostname
            selected = [row for row in addresses if row.get('ip') == host]
            if len(selected) != 1:
                raise RuntimeError('Cannot uniquely preserve the iVentoy network interface')
            return {key: selected[0][key] for key in fields}

        def selected_address(version):
            if not addresses['ipv%d_enable' % version]:
                return {}
            selected = [row for row in addresses['ipv%d_list' % version] if row.get('choose')]
            if len(selected) != 1 or not selected[0].get('ip'):
                raise RuntimeError('Cannot uniquely preserve the iVentoy IPv%d interface' % version)
            return selected[0]

        ipv4 = selected_address(4)
        ipv6 = selected_address(6)
        if not (ipv4 or ipv6):
            raise RuntimeError('iVentoy reports running without an enabled IP interface')
        return dict({key: ipv4.get(key, '') for key in fields},
                    ip6=ipv6.get('ip', ''), dns6=ipv6.get('dns_server', ''))

    def restore_network(self, snapshot):
        # systemd active only means the web process is alive; PXE may be ready.
        # Preserve the pre-release choice, including an intentionally idle server.
        changed = False
        for _ in range(60):
            try:
                status = self.native('query_status')['status']
            except (subprocess.CalledProcessError, ValueError, KeyError):
                time.sleep(.5)
                continue
            if status == snapshot['status']:
                start = snapshot.get('start', {})
                if status == 'running' and 'ip6' in start:
                    restored = self.network_start()
                    if (restored['ip'], restored['ip6']) != (start['ip'], start['ip6']):
                        raise RuntimeError('iVentoy did not restore the saved IPv4/IPv6 interfaces')
                return
            if not changed and status in ('ready', 'running'):
                action = 'start_server' if snapshot['status'] == 'running' else 'stop_server'
                result = self.native(action, **(snapshot.get('start', {}) if action == 'start_server' else {}))
                if result.get('result') != 'success':
                    raise RuntimeError('Cannot restore iVentoy network state')
                changed = True
            time.sleep(.5)
        raise RuntimeError('iVentoy network did not restore its previous state')

    def native_view(self, include_images):
        view = dict(config=self.native('get_config_all'))
        if include_images:
            def images(nodes, base=''):
                for node in nodes:
                    path = base + node['name']
                    if node.get('isParent'):
                        yield from images(node.get('children', []), path+'/')
                    else:
                        yield path, node['imgid']
            view['images'] = {}
            for path, image_id in images(self.native('get_img_tree')):
                if path in view['images']:
                    raise ValueError('Duplicate native image path')
                # iVentoy serializes this endpoint; avoid overlapping its work.
                time.sleep(.08)
                view['images'][path] = {k: v for k, v in self.native('get_img_info', id=image_id).items() if k != 'id'}
        return view

    def backup_native(self, network):
        # Native config writes are not atomic. A quick service rollback can
        # interrupt a save and make the next start silently use factory defaults.
        path = real(self.root/'data/config.dat')
        saved = self.dir/'backup/native-config.dat'
        st = path.stat()
        before = digest(path)
        view = self.native_view(network['status'] == 'running')
        replace(saved, path.read_bytes())
        if digest(saved) != before or digest(path) != before:
            raise ValueError('Native configuration changed during backup')
        save(self.dir/'backup/native.json', dict(sha256=before, uid=st.st_uid,
             gid=st.st_gid, mode=st.st_mode & 0o777, view=view))

    def verified_native_backup(self):
        record = read(self.dir/'backup/native.json')
        saved = real(self.dir/'backup/native-config.dat')
        if digest(saved) != record['sha256']:
            raise ValueError('Native configuration backup integrity check failed')
        return record, saved

    def restore_native_file(self):
        record, saved = self.verified_native_backup()
        target = real(self.root/'data/config.dat')
        replace(target, saved.read_bytes())
        os.chown(target, record['uid'], record['gid'])
        os.chmod(target, record['mode'])

    def audit_native(self):
        record, _ = self.verified_native_backup()
        expected = record['view']
        # get_img_info blocks while ready, so preserve its on-disk configuration
        # without starting a server that the operator intentionally stopped.
        if self.native_view('images' in expected) != expected:
            raise RuntimeError('Native settings or image bindings changed after restart')

    def stage(self):
        self.dir.mkdir(mode=0o700)
        (self.dir/'.release-owned').write_text('ventoy-center release schema 1\n')
        stage = self.dir / 'stage'
        for name in ('data', 'iventoy/iso', 'iventoy/data', 'iventoy/user/scripts'):
            (stage / name).mkdir(parents=True, exist_ok=True)
        shutil.copy2(real(self.args.candidate), self.dir / 'ventoy-center')
        os.chmod(self.dir / 'ventoy-center', 0o700)
        cfg = dict(self.cfg)
        cfg.update(listen='127.0.0.1:%d' % self.args.port, data_dir=str(stage/'data'),
                   iso_dir=str(stage/'iventoy/iso'), iventoy_root=str(stage/'iventoy'))
        # The installed server's URL/CA/client capability remain unchanged.
        original = read(self.state)
        state = dict(original, jobs=[], machines=[], pxe_tickets=[])
        state['pxe_entries'] = json.loads(json.dumps(original['pxe_entries']))
        for e in state['pxe_entries']:
            e.pop('preparation', None)
            e['enabled'] = False
            src = child(self.root/'iso', e['iso'])
            dst = child(stage/'iventoy/iso', e['iso'])
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.link(str(src), str(dst))
        (stage/'iventoy/data/iventoy.dat').write_text('Isolated release preparation\n')
        save(stage/'config.json', cfg)
        save(stage/'data/state.json', state)
        with (self.dir/'stage.log').open('wb') as log:
            proc = subprocess.Popen([str(self.dir/'ventoy-center'), 'stage', '--config', str(stage/'config.json')], stdout=log, stderr=subprocess.STDOUT)
            try:
                for _ in range(100):
                    try:
                        version = json.loads(self.api('/healthz', port=self.args.port))['version']
                        break
                    except Exception:
                        if proc.poll() is not None:
                            raise RuntimeError('Staging controller exited; inspect stage.log')
                        time.sleep(.2)
                else:
                    raise RuntimeError('Staging controller did not become ready')
                setup = self.api('/api/linux-manual-setup?format=run', port=self.args.port)
                replace(self.dir/'ventoy-linux-setup.run', setup, 0o700)
                for i, e in enumerate(state['pxe_entries']):
                    self.api('/api/pxe/entries/'+e['id']+'/prepare', {}, self.args.port)
                    print('Prepared %d/%d' % (i+1, len(state['pxe_entries'])), flush=True)
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        entries = read(stage/'data/state.json')['pxe_entries']
        files = {'ventoy-center': digest(self.dir/'ventoy-center'), 'ventoy-linux-setup.run': digest(self.dir/'ventoy-linux-setup.run')}
        for e in entries:
            prep = e['preparation']
            old = next(x for x in original['pxe_entries'] if x['id'] == e['id'])
            previous = old.get('preparation')
            if not previous or prep['script_path'] != previous['script_path'] or prep['iso_path'] != 'iso/'+e['iso']:
                raise ValueError('Release requires existing shared, bound entries')
            if set(prep['files']) != set(previous['files']):
                raise ValueError('Entry filenames changed; migrate bindings separately')
            for name, checksum in prep['files'].items():
                src = child(stage/'iventoy', str(Path(prep['script_path']).parent / name))
                if digest(src) != checksum:
                    raise ValueError('Prepared checksum mismatch')
                files[str(src.relative_to(self.dir))] = checksum
                if name.endswith('.tar.gz'):
                    with tarfile.open(str(src)) as archive:
                        f = archive.extractfile('ventoy-manual-preload/ventoy-linux-setup.run')
                        if f.read() != setup:
                            raise ValueError('Preloaded setup differs from release')
        manifest = dict(schema=1, name=self.args.name, version=version, created=datetime.datetime.utcnow().isoformat()+'Z',
                        source_commit=self.args.commit, files=files, entries=entries, config_sha256=digest(self.cfgpath),
                        previous_version=json.loads(self.api('/healthz'))['version'], entry_count=len(entries))
        save(self.dir/'manifest.json', manifest)
        self.verify()
        print('STAGED: '+str(self.dir), flush=True)

    def verify(self):
        m = read(self.dir/'manifest.json')
        for name, value in m['files'].items():
            if digest(child(self.dir, name)) != value:
                raise ValueError('Release file changed: '+name)
        entries = read(self.state)['pxe_entries']
        if {(e['id'], e['iso'], e['profile']) for e in entries} != {(e['id'], e['iso'], e['profile']) for e in m['entries']}:
            raise ValueError('Production entry inventory changed; restage')
        for e in m['entries']:
            iso = child(self.root/'iso', e['iso']).stat()
            staged = child(self.dir/'stage/iventoy/iso', e['iso']).stat()
            if (iso.st_dev, iso.st_ino, iso.st_size, iso.st_mtime_ns) != (staged.st_dev, staged.st_ino, staged.st_size, staged.st_mtime_ns):
                raise ValueError('ISO changed since staging')
        return m

    def mappings(self, m):
        result = [(self.dir/'ventoy-center', self.binary), (self.dir/'ventoy-linux-setup.run', real(Path(self.cfg['software_dir'])/'ventoy-linux-setup.run'))]
        for e in m['entries']:
            folder = Path(e['preparation']['script_path']).parent
            for name in e['preparation']['files']:
                result.append((child(self.dir/'stage/iventoy', str(folder/name)), child(self.root, str(folder/name))))
        return result

    def activate(self):
        m = self.verify()
        self.idle()
        if digest(self.cfgpath) != m['config_sha256']:
            raise ValueError('Production configuration changed; restage')
        if not self.args.apply:
            print(json.dumps(dict(action='activate', version=m['version'], entries=m['entry_count'], idle=True, apply=False)))
            return
        backup = self.dir/'backup'
        backup.mkdir(mode=0o700)
        state_raw = self.state.read_bytes()
        state = json.loads(state_raw)
        targets = self.mappings(m)
        records = []
        for i, (_, target) in enumerate(targets):
            real(target)
            shutil.copy2(target, backup/str(i))
            st = target.stat()
            records.append(dict(target=str(target), saved=str(i), sha256=digest(target), uid=st.st_uid, gid=st.st_gid, mode=st.st_mode & 0o777))
        save(backup/'entries.json', state['pxe_entries'])
        save(backup/'files.json', records)
        old_public = self.data/'release-status.json'
        save(backup/'release-status.json', read(old_public) if old_public.exists() else {})
        network = self.network_snapshot()
        save(backup/'network.json', network)
        self.backup_native(network)
        self.idle()
        if self.state.read_bytes() != state_raw:
            raise ValueError('State changed during backup; publication deferred')
        if digest(self.root/'data/config.dat') != read(backup/'native.json')['sha256']:
            raise ValueError('Native configuration changed before stop; publication deferred')
        save(self.dir/'transaction.json', dict(state='activating', version=m['version']))
        try:
            subprocess.run(['systemctl', 'stop', 'iventoy.service', 'ventoy-center.service'], check=True)
            if self.state.read_bytes() != state_raw:
                raise ValueError('State changed during stop')
            self.restore_native_file()
            for src, target in targets:
                replace(target, src.read_bytes())
            # The manager hashes the actual tools copy as its service account.
            # Retain root ownership; grant only its state-file group read access.
            # Original owner/mode are recorded above and restored on rollback.
            setup = real(Path(self.cfg['software_dir'])/'ventoy-linux-setup.run')
            os.chown(setup, setup.stat().st_uid, self.state.stat().st_gid)
            os.chmod(setup, 0o740)
            staged = {e['id']: e for e in m['entries']}
            for e in state['pxe_entries']:
                e['preparation'] = staged[e['id']]['preparation']
                e['preparation']['root'] = str(self.root)
            replace(self.state, (json.dumps(state, indent=2)+'\n').encode())
            public = dict(name=m['name'], version=m['version'], previous_version=m['previous_version'],
                          source_commit=m['source_commit'], published=datetime.datetime.utcnow().isoformat()+'Z',
                          setup_sha256=m['files']['ventoy-linux-setup.run'], binary_sha256=m['files']['ventoy-center'],
                          entry_count=m['entry_count'], rollback_available=True, physical_acceptance='pending')
            save(old_public, public)
            st = self.state.stat()
            os.chown(old_public, st.st_uid, st.st_gid)
            subprocess.run(['systemctl', 'start', 'ventoy-center.service', 'iventoy.service'], check=True)
            self.restore_network(network)
            self.audit_native()
            self.healthy(m['version'])
            for src, target in targets:
                if digest(src) != digest(target):
                    raise ValueError('Published file mismatch')
            self.audit_published(m['entry_count'])
            save(self.dir/'transaction.json', dict(state='published', **public))
            print('PUBLISHED '+m['version'], flush=True)
        except Exception:
            self.restore(m)
            raise

    def restore(self, m):
        # Preserve newly created jobs; only restore the same entry inventory.
        records = read(self.dir/'backup/files.json')
        allowed = {str(dst) for _, dst in self.mappings(m)}
        if {r['target'] for r in records} != allowed:
            raise ValueError('Backup destinations differ from managed release')
        for r in records:
            if digest(child(self.dir/'backup', r['saved'])) != r['sha256']:
                raise ValueError('Backup integrity check failed')
        self.verified_native_backup()
        state = read(self.state)
        previous = {e['id']: e for e in read(self.dir/'backup/entries.json')}
        if set(previous) != {e['id'] for e in state['pxe_entries']}:
            raise ValueError('Entry inventory changed; do not overwrite')
        subprocess.run(['systemctl', 'stop', 'iventoy.service', 'ventoy-center.service'], check=True)
        # A stop may flush state. Preserve these latest job updates too.
        state = read(self.state)
        if set(previous) != {e['id'] for e in state['pxe_entries']}:
            subprocess.run(['systemctl', 'start', 'ventoy-center.service', 'iventoy.service'], check=True)
            raise ValueError('Entry inventory changed during stop; services restarted without rollback')
        for r in records:
            target = Path(r['target'])
            replace(target, (self.dir/'backup'/r['saved']).read_bytes())
            os.chown(target, r['uid'], r['gid'])
            os.chmod(target, r['mode'])
        for e in state['pxe_entries']:
            e['preparation'] = previous[e['id']]['preparation']
        save(self.state, state)
        save(self.data/'release-status.json', read(self.dir/'backup/release-status.json'))
        st = self.state.stat()
        os.chown(self.data/'release-status.json', st.st_uid, st.st_gid)
        self.restore_native_file()
        subprocess.run(['systemctl', 'start', 'ventoy-center.service', 'iventoy.service'], check=True)
        self.restore_network(read(self.dir/'backup/network.json'))
        self.audit_native()
        self.healthy(m['previous_version'])
        save(self.dir/'transaction.json', dict(state='rolled-back', version=m['previous_version']))
        print('ROLLED_BACK '+m['previous_version'])

    def rollback(self):
        m = self.verify()
        self.idle()
        status = self.data/'release-status.json'
        current = read(status) if status.exists() else {}
        transaction = read(self.dir/'transaction.json')
        interrupted = transaction.get('state') == 'activating'
        if not interrupted and (current.get('name') != m['name'] or transaction.get('state') != 'published'):
            raise ValueError('Rollback only applies to the currently published release')
        if self.args.apply:
            self.restore(m)
        else:
            print('Rollback verified; add --apply to restore '+m['previous_version'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['stage', 'verify', 'activate', 'rollback'])
    p.add_argument('--config', default='/var/lib/ventoy-center/config.json')
    p.add_argument('--binary', default='/usr/local/bin/ventoy-center')
    p.add_argument('--releases', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--candidate')
    p.add_argument('--commit', default='unknown')
    p.add_argument('--port', type=int, default=26190)
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    if not 1024 <= args.port <= 65535 or (args.command == 'stage' and not args.candidate):
        p.error('stage requires --candidate; --port must be 1024..65535')
    if os.geteuid() != 0:
        p.error('Release lifecycle requires root on the center server')
    os.umask(0o077)
    release = Release(args)
    with (release.base/'release.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = getattr(release, args.command)()
        if args.command == 'verify':
            print('VERIFIED %s entries=%s' % (result['version'], result['entry_count']))


if __name__ == '__main__':
    main()
