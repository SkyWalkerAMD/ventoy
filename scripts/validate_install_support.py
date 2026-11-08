"""Run report/cache hooks in disposable roots; compare previews to native sizing."""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'internal/center/assets/install-support'


def run(script, *args, env=None, ok=True):
    p = subprocess.run(['sh', str(script), *map(str, args)], env=env, text=True, capture_output=True)
    if ok and p.returncode:
        raise AssertionError(p.stdout + p.stderr)
    return p


with tempfile.TemporaryDirectory() as directory:
    base = Path(directory)
    src = base/'support'
    shutil.copytree(ASSETS, src)
    (src/'support-version').write_text('test-release\n')
    (src/'support-cache-url').write_text('http://192.168.1.2:26081/installer-cache\n')
    target = base/'target'
    (target/'etc/apt/sources.list.d').mkdir(parents=True)
    (target/'etc/os-release').write_text('ID=ubuntu\nVERSION_ID=22.04\n')
    (target/'etc/hostname').write_text('keep-my-host\n')
    sources = target/'etc/apt/sources.list.d/ubuntu.sources'
    original = 'Types: deb\nURIs: https://archive.ubuntu.com/ubuntu/\nSuites: jammy jammy-updates\nComponents: main\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n'
    sources.write_text(original)
    custom = target/'etc/apt/sources.list'
    custom.write_text('deb https://archiveXubuntuYcom/ubuntu jammy main\ndeb https://mirror.example/ubuntu jammy main\n')
    run(src/'support-cache.sh', target)
    wanted = original.replace('https://archive.ubuntu.com/ubuntu/', 'http://192.168.1.2:26081/installer-cache/ubuntu/')
    assert sources.read_text() == wanted
    assert sources.with_name(sources.name+'.before-ventoy-cache').read_text() == original
    run(src/'support-cache.sh', target)
    assert sources.read_text() == wanted
    assert custom.read_text().startswith('deb https://archiveXubuntuYcom')
    assert 'trusted=yes' not in sources.read_text()
    apt_config = (target/'etc/apt/apt.conf.d/90ventoy-installer-cache').read_text()
    assert 'Acquire::http::Timeout "1200"' in apt_config
    assert 'Acquire::AllowInsecureRepositories "false"' in apt_config
    installed = run(src/'support-install.sh', target)
    assert not installed.stdout
    assert (target/'etc/hostname').read_text() == 'keep-my-host\n'
    assert (target/'var/lib/ventoy-center/install-mode').read_text() == 'manual\n'
    assert (target/'usr/local/lib/ventoy-install-support/acceptance.sh').stat().st_mode & 0o777 == 0o700
    assert (target/'etc/systemd/system/timers.target.wants/ventoy-install-report.timer').is_symlink()
    profile_banner = target/'etc/profile.d/90-ventoy-install-report.sh'
    issue_banner = target/'etc/issue.d/90-ventoy.issue'
    assert not profile_banner.exists() and not issue_banner.exists()

    # Upgrading setup removes its previous generated banners, never the normal
    # distribution banners or a local customization at the old managed paths.
    profile_banner.parent.mkdir(parents=True)
    issue_banner.parent.mkdir(parents=True)
    profile_banner.write_text('case "$-" in *i*) [ ! -r /run/ventoy-install-report.txt ] || cat /run/ventoy-install-report.txt;; esac\n')
    issue_banner.write_text('\nVentoy installation report | old-release | manual\nSetup: PRELOADED\n')
    (target/'etc/issue').write_text('Distribution console login\n')
    (target/'etc/motd').write_text('Local administrator message\n')
    run(src/'support-install.sh', target)
    assert not profile_banner.exists() and not issue_banner.exists()
    assert (target/'etc/issue').read_text() == 'Distribution console login\n'
    assert (target/'etc/motd').read_text() == 'Local administrator message\n'
    for p in (profile_banner, issue_banner):
        p.write_text('Local customization\n')
    run(src/'support-install.sh', target)
    assert all(p.read_text() == 'Local customization\n' for p in (profile_banner, issue_banner))
    for p in (profile_banner, issue_banner):
        p.unlink()
        p.symlink_to(target/'etc/issue')
    run(src/'support-install.sh', target)
    assert all(p.is_symlink() for p in (profile_banner, issue_banner))
    assert (target/'etc/issue').read_text() == 'Distribution console login\n'
    for p in (profile_banner, issue_banner):
        p.unlink()
    # Never traverse a symlinked banner directory during migration.
    profile_banner.parent.rmdir()
    profile_banner.parent.symlink_to(issue_banner.parent, target_is_directory=True)
    blocked = run(src/'support-install.sh', target, ok=False)
    assert blocked.returncode and 'Unsafe support destination: /etc/profile.d' in blocked.stderr
    profile_banner.parent.unlink()
    (target/'var/lib/ventoy-center/install-mode').write_text('automatic\n')
    run(src/'support-install.sh', target)
    assert (target/'var/lib/ventoy-center/install-mode').read_text() == 'automatic\n'

    # Exercise the real reporter with every system path isolated and service
    # commands stubbed. Never change the runner's getty, hostname, APT or SSH.
    for d in ('run/lock', 'proc/sys/kernel/random', 'usr/local/sbin', 'fake-bin', 'dev'):
        (target/d).mkdir(parents=True, exist_ok=True)
    (target/'proc/sys/kernel/random/boot_id').write_text('boot-one\n')
    (target/'proc/mdstat').write_text('Personalities : [raid1]\n')
    (target/'usr/local/sbin/ventoy-center-update-policy').write_text('#!/bin/sh\nexit 0\n')
    uploads = target/'uploads'
    upload_failure = target/'upload-failure'
    (target/'usr/local/lib/ventoy-install-support/support-diagnostic.sh').write_text('#!/bin/sh\necho attempt >> "'+str(uploads)+'"\n[ ! -f "'+str(upload_failure)+'" ]\n')
    commands = target/'commands'
    stubs = {
        'findmnt': 'echo ext4', 'hostname': 'echo user-host',
        'ip': 'echo "2: eno1 inet 192.0.2.1/24 scope global dynamic eno1"',
        'systemctl': 'echo "$*" >> "'+str(commands)+'"; case "$1" in show) echo ActiveState=inactive;; esac',
        'agetty': 'echo "agetty $*" >> "'+str(commands)+'"; exit 1',
    }
    for name, body in stubs.items():
        p = target/'fake-bin'/name; p.write_text('#!/bin/sh\n'+body+'\n'); p.chmod(0o755)
    source = (ASSETS/'support-report.sh').read_text()
    source = re.sub(r'(?<![\w/])/(var|run|etc|proc|usr|dev)(?=/)', lambda m: str(target)+m[0], source)
    script = base/'report.sh'; script.write_text(source)
    env = dict(os.environ, PATH=str(target/'fake-bin')+':'+os.environ['PATH'])
    console = target/'dev/tty1'
    console.write_text('operator console content\n')
    reported = run(script, env=env)
    assert not reported.stdout
    report = (target/'run/ventoy-install-report.txt').read_text()
    assert 'PENDING / FAILED' in report and 'PRELOADED, NOT EXECUTED' in report
    assert '192.0.2.1/24' in report and 'user-host' in report and 'VERIFIED' in report
    run(script, env=env)
    assert not profile_banner.exists() and not issue_banner.exists()
    assert console.read_text() == 'operator console content\n'
    assert not any('agetty' in line or 'getty@' in line for line in commands.read_text().splitlines())
    assert uploads.read_text().splitlines() == ['attempt']
    assert not any(x.startswith(('restart ', 'kill ', 'start ')) for x in commands.read_text().splitlines())
    (target/'var/lib/ventoy-center/automatic-checks').write_text('boot=boot-one\n')
    (target/'proc/sys/kernel/random/boot_id').write_text('boot-two\n')
    run(script, env=env)
    report = (target/'run/ventoy-install-report.txt').read_text()
    assert 'Acceptance boot: boot-one' in report and 'Current boot: boot-two' in report
    assert not profile_banner.exists() and not issue_banner.exists()
    assert console.read_text() == 'operator console content\n'

    # Setup completion must refresh the center report without console output;
    # a failed upload keeps retrying instead of silently losing it.
    (target/'var/lib/ventoy-center/manual-init').mkdir()
    (target/'var/lib/ventoy-center/manual-init/status').write_text('verified\n')
    upload_failure.touch()
    stops = commands.read_text().splitlines().count('stop ventoy-install-report.timer')
    run(script, env=env)
    assert commands.read_text().splitlines().count('stop ventoy-install-report.timer') == stops
    upload_failure.unlink()
    run(script, env=env)
    assert not any('agetty' in line or 'getty@' in line for line in commands.read_text().splitlines())
    assert not profile_banner.exists() and not issue_banner.exists()
    assert console.read_text() == 'operator console content\n'
    assert uploads.read_text().splitlines() == ['attempt'] * 4
    assert 'Setup result: verified' in (target/'run/ventoy-install-report.txt').read_text()

    # Report scripts are deliberately inert during installation: writing their
    # systemd units must not start any service or run the full setup.
    assert (target/'var/lib/ventoy-center/manual-init/status').read_text() == 'verified\n'

spec = importlib.util.spec_from_file_location('acceptance', ROOT/'scripts/validate_install_acceptance.py')
acceptance = importlib.util.module_from_spec(spec); spec.loader.exec_module(acceptance)
first = dict(boot_id='a',hostname='node',kernel='fixed',rootfs='xfs',mode='automatic',setup_sha256='a'*64,disk_boot='yes',ssh_active='yes',permitrootlogin='yes',passwordauthentication='yes',dhcp_observed='yes',update_policy='verified',raid='healthy-or-syncing',setup='verified boot=a')
second = dict(first,boot_id='b')
assert not acceptance.check(first, second, True)
for changes in ({'boot_id':'a'}, {'boot_id':''}, {'setup_sha256':'unknown'}, {'kernel':'new'}, {'update_policy':'failed'}, {'setup':'failed'}, {'raid':'degraded'}, {'permitrootlogin':'prohibit-password'}):
    assert acceptance.check(first, dict(second, **changes), True), changes

if len(sys.argv) > 1:
    fixtures = Path(sys.argv[1])
    client_source = (fixtures/'pxe/rocky-8/client.py').read_text()
    ns = {'__name__':'preview_test'}; exec(compile(client_source,'client.py','exec'),ns)
    shell_source = (ROOT/'internal/center/templates/storage-preview.sh').read_text()
    for capacity, expected in ((120,1),(239,1),(240,2),(480,4),(960,8),(1920,16),(3840,32)):
        disks = [dict(name='sda',serial='FIRST',size=capacity*10**9),dict(name='sdb',serial='SECOND',size=capacity*2*10**9)]
        for firmware in ('uefi','bios'):
            for fs in ('ext4','xfs'):
                preview=ns['partition_preview'](disks,fs,firmware)
                assert 'FIRST' in preview and 'SECOND' in preview and 'RAID1' in preview
                assert '%9.2f GiB' % (32768*expected/1024) in preview
                command=shell_source+'\nvc_preview %s %s %s RAID1\n' % (capacity*10**9,fs,firmware)
                output=subprocess.check_output(['sh','-eu'],input=command,text=True)
                for size in (1280,8192,16384,32768): assert str(size*expected)+' MiB' in output
    try: ns['partition_preview']([dict(name='sda',serial='a',size=119*10**9)],'xfs','uefi')
    except RuntimeError: pass
    else: raise AssertionError('small disk accepted')

print('INSTALL_SUPPORT_PASS: cache source integrity, inert hooks, quiet two-boot reports, legacy banner migration and preview tiers')
