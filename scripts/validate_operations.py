"""Exercise lifecycle failure/rollback and retention in disposable directories."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

if sys.platform != 'linux':
    print('SKIP: Linux deployment lifecycle tests')
    sys.exit(0)
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'deploy'))
import release
import maintenance


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='vc-release-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.iv=self.root/'iventoy';self.data=self.root/'data';self.base=self.root/'releases'
        for p in [self.iv/'iso',self.iv/'data',self.iv/'user/scripts/menu',self.data,self.root/'tools']:
            p.mkdir(parents=True)
        self.native_config=self.iv/'data/config.dat';self.native_config.write_bytes(b'valid native settings and bindings');self.native_config.chmod(0o600)
        self.binary=self.root/'ventoy-center';self.binary.write_bytes(b'old binary')
        (self.root/'admin').write_text('fixture-only')
        self.setup=self.root/'tools/ventoy-linux-setup.run';self.setup.write_bytes(b'old setup')
        self.script=self.iv/'user/scripts/menu/user-data';self.script.write_bytes(b'old script')
        (self.iv/'iso/test.iso').write_bytes(b'fake ISO')
        self.cfg=self.root/'config.json'
        self.cfg.write_text(json.dumps(dict(iventoy_root=str(self.iv),data_dir=str(self.data),admin_token_file=str(self.root/'admin'),software_dir=str(self.root/'tools'))))
        self.entry=dict(id='entry',iso='test.iso',profile='ubuntu-22.04',preparation=dict(root=str(self.iv),script_path='user/scripts/menu/user-data',files={'user-data':release.digest(self.script)}))
        release.save(self.data/'state.json',dict(jobs=[],pxe_entries=[self.entry]))
        self.r=release.Release(SimpleNamespace(config=str(self.cfg),binary=str(self.binary),releases=str(self.base),name='alpha49',apply=True))
        self.r.dir.mkdir();(self.r.dir/'.release-owned').write_text('owned')
        for name,body in [('ventoy-center',b'new binary'),('ventoy-linux-setup.run',b'new setup'),('stage/iventoy/user/scripts/menu/user-data',b'new script')]:
            p=self.r.dir/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
        (self.r.dir/'stage/iventoy/iso').mkdir(parents=True)
        os.link(self.iv/'iso/test.iso',self.r.dir/'stage/iventoy/iso/test.iso')
        entry=json.loads(json.dumps(self.entry));entry['preparation']['files']['user-data']=release.digest(self.r.dir/'stage/iventoy/user/scripts/menu/user-data')
        entry['preparation']['release']='new'
        self.manifest=dict(schema=1,name='alpha49',version='new',previous_version='old',source_commit='fixture',entry_count=1,config_sha256=release.digest(self.cfg),entries=[entry],files={n:release.digest(self.r.dir/n) for n in ['ventoy-center','ventoy-linux-setup.run','stage/iventoy/user/scripts/menu/user-data']})
        release.save(self.r.dir/'manifest.json',self.manifest)
        self.calls=[]
        self.patch=mock.patch.object(release.subprocess,'run',side_effect=lambda args,**kwargs:self.calls.append(args))
        self.patch.start();self.addCleanup(self.patch.stop)
        self.check=mock.patch.object(release.subprocess,'check_output',return_value='')
        self.check.start();self.addCleanup(self.check.stop)
        self.health=mock.patch.object(self.r,'healthy');self.health.start();self.addCleanup(self.health.stop)
        self.audit=mock.patch.object(self.r,'audit_published');self.audit.start();self.addCleanup(self.audit.stop)
        self.network=mock.patch.object(self.r,'network_snapshot',return_value={'status':'running','start':{'ip':'192.168.1.2'}});self.network.start();self.addCleanup(self.network.stop)
        self.restore_net=mock.patch.object(self.r,'restore_network');self.restore_net.start();self.addCleanup(self.restore_net.stop)
        self.native_view=mock.patch.object(self.r,'native_view',return_value={'config':{'dhcp_mode':4,'sb_level':0},'images':{'test.iso':{'auto_scripts':['old script']}}});self.native_view.start();self.addCleanup(self.native_view.stop)

    def test_publish_and_rollback_preserve_jobs_and_modes(self):
        self.binary.chmod(0o755)
        self.setup.chmod(0o700)
        self.r.activate()
        self.assertEqual(self.binary.read_bytes(),b'new binary')
        self.assertEqual(self.setup.stat().st_mode&0o777,0o740)
        self.assertEqual(self.setup.stat().st_gid,self.r.state.stat().st_gid)
        self.r.audit_published.assert_called_once_with(1)
        state=release.read(self.r.state);state['jobs']=[dict(id='new-observation',state='installed')];release.save(self.r.state,state)
        self.r.rollback()
        self.assertEqual(self.binary.read_bytes(),b'old binary')
        self.assertEqual(self.setup.read_bytes(),b'old setup')
        self.assertEqual(self.setup.stat().st_mode&0o777,0o700)
        self.assertEqual(self.script.read_bytes(),b'old script')
        self.assertEqual(self.binary.stat().st_mode&0o777,0o755)
        self.assertEqual(release.read(self.r.state)['jobs'],state['jobs'])
        self.assertEqual((self.iv/'iso/test.iso').read_bytes(),b'fake ISO')
        self.assertEqual(self.r.restore_network.call_count,2)

    def test_native_save_interrupted_by_stop_is_restored_before_start(self):
        original=self.native_config.read_bytes()
        def service(args,**kwargs):
            self.calls.append(args)
            if args[:2]==['systemctl','stop']:self.native_config.write_bytes(b'partial native save')
            elif args[:2]==['systemctl','start']:self.assertEqual(self.native_config.read_bytes(),original)
        release.subprocess.run.side_effect=service
        self.r.activate()
        self.r.rollback()
        self.assertEqual(self.native_config.read_bytes(),original)
        self.assertEqual(self.native_config.stat().st_mode&0o777,0o600)

    def test_native_binding_reset_is_detected_and_rolled_back(self):
        expected=self.r.native_view.return_value
        self.r.native_view.side_effect=[expected,{'config':{'dhcp_mode':0,'sb_level':1},'images':{}},expected]
        with self.assertRaisesRegex(RuntimeError,'bindings changed'):self.r.activate()
        self.assertEqual(release.read(self.r.dir/'transaction.json')['state'],'rolled-back')
        self.assertEqual(self.binary.read_bytes(),b'old binary')

    def test_tampered_native_backup_blocks_rollback_before_stop(self):
        self.r.activate();self.calls.clear()
        (self.r.dir/'backup/native-config.dat').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'Native configuration backup integrity'):self.r.rollback()
        self.assertFalse(any('stop' in c for c in self.calls))

    def test_native_view_uses_paths_and_does_not_read_images_when_ready(self):
        config={'dhcp_mode':4,'sb_level':0}
        tree=[{'name':'Ubuntu','isParent':True,'children':[{'name':'test.iso','imgid':9}]}]
        info={'id':9,'auto_scripts':['/script'],'injection':'/preload'}
        with mock.patch.object(self.r,'native',side_effect=[config,tree,info]),mock.patch.object(release.time,'sleep'):
            self.assertEqual(release.Release.native_view(self.r,True),{'config':config,'images':{'Ubuntu/test.iso':{'auto_scripts':['/script'],'injection':'/preload'}}})
        with mock.patch.object(self.r,'native',return_value=config) as native:
            self.assertEqual(release.Release.native_view(self.r,False),{'config':config})
            native.assert_called_once_with('get_config_all')

    def test_native_config_change_during_backup_blocks_before_stop(self):
        expected=self.r.native_view.return_value
        def changing(*args):
            self.native_config.write_bytes(b'new operator settings')
            return expected
        self.r.native_view.side_effect=changing
        with self.assertRaisesRegex(ValueError,'changed during backup'):self.r.activate()
        self.assertFalse(any('stop' in c for c in self.calls))

    def test_network_snapshot_preserves_configured_interface(self):
        self.r.cfg['public_url']='https://192.168.1.2:26080'
        network=dict(ip='192.168.1.2',mask='255.255.254.0',gw='192.168.1.1',pool_begin='192.168.1.10',pool_end='192.168.1.200',dns_server='192.168.1.1')
        with mock.patch.object(self.r,'native',side_effect=[{'status':'running'},[network]]):
            self.assertEqual(release.Release.network_snapshot(self.r),{'status':'running','start':network})

    def test_restore_network_starts_pxe_after_ready_process(self):
        snapshot={'status':'running','start':{'ip':'192.168.1.2','mask':'255.255.254.0'}}
        with mock.patch.object(self.r,'native',side_effect=[release.subprocess.CalledProcessError(7,['curl']),{'status':'ready'},{'result':'success'},{'status':'running'}]) as native, mock.patch.object(release.time,'sleep'):
            release.Release.restore_network(self.r,snapshot)
            self.assertIn(mock.call('start_server',**snapshot['start']),native.call_args_list)
        with mock.patch.object(self.r,'native',return_value={'status':'ready'}) as native:
            release.Release.restore_network(self.r,{'status':'ready'})
            native.assert_called_once_with('query_status')

    def test_dual_stack_snapshot_and_fallback_use_native_selection(self):
        self.r.cfg['public_url']='https://center.example.test:26080'
        ipv4=dict(ip='192.0.2.10',mask='255.255.255.0',gw='192.0.2.1',
                  pool_begin='',pool_end='',dns_server='')
        ipv6=dict(ip='2001:db8::10',choose=True)
        addresses=dict(ipv4_enable=True,ipv6_enable=True,
                       ipv4_list=[dict(ip='192.0.2.20',choose=False),dict(ipv4,choose=True)],
                       ipv6_list=[ipv6])
        expected=dict(status='running',start=dict(ipv4,ip6=ipv6['ip'],dns6=''))
        with mock.patch.object(self.r,'native',side_effect=[{'status':'running'},addresses]):
            self.assertEqual(release.Release.network_snapshot(self.r),expected)
        with mock.patch.object(self.r,'native',side_effect=[
            {'status':'ready'},{'result':'success'},{'status':'running'},addresses,
        ]) as native, mock.patch.object(release.time,'sleep'):
            release.Release.restore_network(self.r,expected)
            self.assertIn(mock.call('start_server',**expected['start']),native.call_args_list)
        with mock.patch.object(self.r,'native',side_effect=[
            {'status':'running'},dict(addresses,ipv6_enable=False),
        ]):
            with self.assertRaisesRegex(RuntimeError,'did not restore'):
                release.Release.restore_network(self.r,expected)

    def test_failed_pxe_restore_rolls_back(self):
        self.r.restore_network.side_effect=[RuntimeError('PXE not running'),None]
        with self.assertRaisesRegex(RuntimeError,'PXE not running'):self.r.activate()
        self.assertEqual(self.binary.read_bytes(),b'old binary')
        self.assertEqual(release.read(self.r.dir/'transaction.json')['state'],'rolled-back')

    def test_api_uses_production_bind_and_loopback_staging(self):
        self.r.cfg['public_url']='https://192.168.1.2:26080'
        response=mock.Mock(status=200)
        response.read.return_value=b'{"status":"ok"}'
        with mock.patch.object(release.ssl,'create_default_context') as tls, mock.patch.object(release.socket,'create_connection') as dial, mock.patch.object(release.http.client.HTTPSConnection,'request',autospec=True,side_effect=lambda conn,*a,**kw:conn.connect()), mock.patch.object(release.http.client.HTTPSConnection,'getresponse',return_value=response):
            self.r.api('/healthz')
            self.assertEqual(dial.call_args[0][0],('192.168.1.2',26080))
            self.r.api('/healthz',port=26190)
            self.assertEqual(dial.call_args[0][0],('127.0.0.1',26190))
            self.assertEqual(tls.return_value.wrap_socket.call_args[1]['server_hostname'],'192.168.1.2')

    def test_failed_health_rolls_back(self):
        self.r.healthy.side_effect=[RuntimeError('candidate unhealthy'),None]
        with self.assertRaisesRegex(RuntimeError,'unhealthy'):self.r.activate()
        self.assertEqual(self.binary.read_bytes(),b'old binary')
        self.assertEqual(release.read(self.r.dir/'transaction.json')['state'],'rolled-back')

    def test_failed_service_file_audit_rolls_back(self):
        self.setup.chmod(0o700)
        self.r.audit_published.side_effect=RuntimeError('Published setup or entry audit failed')
        with self.assertRaisesRegex(RuntimeError,'audit failed'):self.r.activate()
        self.assertEqual(self.setup.read_bytes(),b'old setup')
        self.assertEqual(self.setup.stat().st_mode&0o777,0o700)
        self.assertEqual(release.read(self.r.dir/'transaction.json')['state'],'rolled-back')

    def test_service_file_audit_requires_setup_and_all_entries(self):
        for report in [{'tools_setup_matches':False,'entries':[{'passed':True}]},
                       {'tools_setup_matches':True,'entries':[]},
                       {'tools_setup_matches':True,'entries':[{'passed':False}]}]:
            with mock.patch.object(self.r,'api',return_value=json.dumps(report).encode()):
                with self.assertRaisesRegex(RuntimeError,'audit failed'):
                    release.Release.audit_published(self.r,1)
        report={'tools_setup_matches':True,'entries':[{'passed':True}]}
        with mock.patch.object(self.r,'api',return_value=json.dumps(report).encode()):
            release.Release.audit_published(self.r,1)

    def test_active_task_blocks_before_stop(self):
        state=release.read(self.r.state);state['jobs']=[dict(id='running',state='installing')];release.save(self.r.state,state)
        with self.assertRaisesRegex(RuntimeError,'Active tasks'):self.r.activate()
        self.assertFalse(any('stop' in c for c in self.calls))
        self.assertEqual(self.binary.read_bytes(),b'old binary')

    def test_tampered_release_and_configuration_fail_before_stop(self):
        self.cfg.write_text(self.cfg.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'configuration changed'):self.r.activate()
        self.assertFalse(any('stop' in c for c in self.calls))
        (self.r.dir/'ventoy-center').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'Release file changed'):self.r.verify()

    def test_backup_tamper_and_foreign_release_rollback_rejected(self):
        self.r.activate();self.calls.clear()
        (self.r.dir/'backup/0').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'integrity'):self.r.rollback()
        self.assertFalse(any('stop' in c for c in self.calls))
        release.save(self.data/'release-status.json',dict(name='another'))
        with self.assertRaisesRegex(ValueError,'currently published'):self.r.rollback()

    def test_retention_mounts_symlinks_and_last_iso_link(self):
        for i in range(4):
            p=self.base/('old'+str(i));p.mkdir();(p/'.release-owned').touch();release.save(p/'manifest.json',dict(name=p.name,schema=1,version='old'))
            os.utime(p/'manifest.json',(100+i,100+i))
        rows,unknown=maintenance.inventory(self.base,'old0',[],now=2000000)
        candidates={r['name'] for r in rows if r['eligible']}
        self.assertEqual(candidates,{'old1','old2'})
        p=self.base/'old1';(p/'lonely.iso').write_bytes(b'only copy')
        self.assertFalse(maintenance.safe_tree(p,[])[0])
        p=self.base/'old2';(p/'outside').symlink_to(self.root)
        self.assertFalse(maintenance.safe_tree(p,[])[0])
        self.assertFalse(maintenance.safe_tree(self.r.dir,[self.r.dir/'stage'])[0])
        (self.base/'foreign').mkdir()
        self.assertIn('foreign',maintenance.inventory(self.base,'old0',[],now=2000000)[1])


if __name__=='__main__':unittest.main()
