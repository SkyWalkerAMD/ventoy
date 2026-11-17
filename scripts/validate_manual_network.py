"""Run the actual setup network wrapper with isolated NIC/backend fixtures."""
import os
from pathlib import Path
import re
import subprocess
import tempfile


SOURCE = Path(__file__).resolve().parents[1] / 'internal/center/assets/manual/manual-network.sh'


def check_network(source):
    for renderer in ('networkd', 'NetworkManager'):
        for scenario in ('connected', 'late-carrier', 'generate-failed', 'activation-failed', 'load-failed', 'load-failed-no-carrier'):
            with tempfile.TemporaryDirectory(prefix='vc-manual-network-') as directory:
                root = Path(directory)
                for name in ('bin', 'etc/netplan', 'run', 'sys/class/net/eth0', 'sys/class/net/eth1'):
                    (root / name).mkdir(parents=True, exist_ok=True)
                for nic, mac in [('eth0', '52:54:00:00:00:01'), ('eth1', '52:54:00:00:00:02')]:
                    (root / 'sys/class/net' / nic / 'address').write_text(mac + '\n')
                    (root / 'sys/class/net' / nic / 'carrier').write_text('0\n' if scenario in ('late-carrier', 'load-failed-no-carrier') else '1\n')
                existing = root / 'etc/netplan/00-existing.yaml'
                original = 'network:\n  version: 2\n  ethernets:\n    eth0:\n      addresses: [192.0.2.10/24]\n'
                existing.write_text(original)
                (root / 'safe-server-init.sh').write_text('''
_si_init() { :; }
_si_python_select() { :; }
_si_backend() { SI_BACKEND=netplan; SI_RENDERER=$RENDERER; }
_si_ssh_devices() { :; }
_si_target() { echo "$ROOT/etc/netplan/90-safe-dhcp-$1.yaml"; }
_si_eligible() { [[ $1 == eth1 && ! -e $(_si_target "$1") ]]; }
set-network() { printf 'network:\\n  version: 2\\n  ethernets:\\n    eth1:\\n      dhcp4: true\\n' > "$(_si_target eth1)"; }
''')
                commands = {
                    'sleep': 'exit 0',
                    'ip': '''case "$*" in
link*) printf 'link %s\\n' "$*" >> "$ROOT/events";;
*'dev eth1'*)
    if [ -f "$ROOT/active" ] && [ "$(cat "$ROOT/sys/class/net/eth1/carrier")" = 1 ]; then echo '3: eth1 inet 198.51.100.20/24 scope global eth1'; fi;;
*) echo '2: eth0 inet 192.0.2.10/24 scope global eth0';;
esac''',
                    'netplan': '''[ "$SCENARIO" != generate-failed ] || exit 1
printf 'generate\\n' >> "$ROOT/events"
mkdir -p "$3/run/systemd/network" "$3/run/NetworkManager/system-connections"
printf '[Match]\\nName=eth1\\n[Network]\\nDHCP=ipv4\\n' > "$3/run/systemd/network/10-netplan-eth1.network"
printf '[connection]\\nid=netplan-eth1\\nuuid=fixture-uuid\\n' > "$3/run/NetworkManager/system-connections/netplan-eth1.nmconnection"''',
                    'networkctl': '''printf 'networkctl %s\\n' "$*" >> "$ROOT/events"
if [ "$1" = --no-pager ]; then
    [ -f "$ROOT/active" ] || exit 1
    printf '                Network File: %s/run/systemd/network/10-netplan-eth1.network\\n' "$ROOT"
    exit 0
fi
case "$SCENARIO:$1" in load-failed*:reload) exit 1;; esac
if [ "$1" = reconfigure ]; then
    [ "$SCENARIO" != activation-failed ] || exit 1
    touch "$ROOT/active"
fi''',
                    'nmcli': '''printf 'nmcli %s\\n' "$*" >> "$ROOT/events"
case "$SCENARIO:$*" in load-failed*:'connection load'*) exit 1;; esac
case "$*" in
*'connection up'*) [ "$SCENARIO" != activation-failed ] || exit 1;;
esac
touch "$ROOT/active"''',
                }
                for name, body in commands.items():
                    path = root / 'bin' / name
                    path.write_text('#!/bin/sh\nset -eu\n' + body + '\n')
                    path.chmod(0o700)
                # Redirect absolute host paths, preserving "$temp/run/..."
                # paths produced by isolated netplan generation.
                script = re.sub(r'(?<![A-Za-z0-9_$])/(sys/class/net|var/lib/ventoy-center/manual-init/network|run/systemd/network|run/NetworkManager/system-connections|run/ventoy-netplan)',
                                lambda m: str(root) + m.group(0), source)
                script = script.replace('export PATH=', 'export PATH=' + str(root / 'bin') + ':', 1)
                (root / 'network.sh').write_text(script)
                env = dict(os.environ, ROOT=str(root), RENDERER=renderer, SCENARIO=scenario)
                def run(mode):
                    return subprocess.run(['bash', str(root / 'network.sh'), mode], env=env,
                                          capture_output=True, text=True, timeout=10)
                result = run('--apply')
                success = scenario in ('connected', 'late-carrier')
                assert result.returncode == (0 if success else 3), (renderer, scenario, result.stdout, result.stderr)
                assert existing.read_text() == original
                events = (root / 'events').read_text()
                assert 'eth0' not in events, events
                if success:
                    assert (root / 'active').exists(), (renderer, scenario, 'saved DHCP was never loaded', result.stdout)
                    if scenario == 'late-carrier' and renderer == 'networkd':
                        # Rerun while the secondary cable is still absent. A
                        # global reload here can drop the primary DHCP lease.
                        again = run('--apply')
                        assert again.returncode == 0, (again.stdout, again.stderr)
                        repeated = (root / 'events').read_text()[len(events):]
                        assert 'networkctl reload' not in repeated, repeated
                        assert 'networkctl reconfigure' not in repeated, repeated
                        runtime = root / 'run/systemd/network/10-netplan-eth1.network'
                        runtime.write_text('[Match]\nName=eth1\n[Network]\nDHCP=no\n')
                        changed = run('--apply')
                        assert changed.returncode == 0, (changed.stdout, changed.stderr)
                        assert 'networkctl reload' in (root / 'events').read_text()[len(events):]
                        assert 'DHCP=ipv4' in runtime.read_text()
                        events = (root / 'events').read_text()
                    # Cable insertion after setup must work without running apply
                    # again. A check alone may not activate or bounce interfaces.
                    (root / 'sys/class/net/eth1/carrier').write_text('1\n')
                    checked = run('--check')
                    assert checked.returncode == 0, (renderer, scenario, checked.stdout, checked.stderr)
                    assert 'DHCP_ADDRESS_VERIFIED' in checked.stdout
                    assert run('--apply').returncode == 0
                    assert (root / 'events').read_text() == events, 'Working interface was bounced on rerun'
                    if scenario == 'late-carrier' and renderer == 'NetworkManager':
                        assert 'connection up' not in events, 'Disconnected NM interface blocked activation'
                else:
                    assert 'DHCP_ACTIVATION_PENDING' in result.stdout
                    env['SCENARIO'] = 'connected'
                    (root / 'sys/class/net/eth1/carrier').write_text('1\n')
                    retry = run('--apply')
                    assert retry.returncode == 0, (renderer, scenario, retry.stdout, retry.stderr)
    print('PASS: 12 setup DHCP activation cases; late carrier, retries, failures and existing network preservation')


if __name__ == '__main__':
    check_network(SOURCE.read_text())
