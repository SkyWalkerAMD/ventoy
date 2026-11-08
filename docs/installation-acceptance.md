# PXE installation results and acceptance

The manual and automatic choices share the same ISO and preload. Preparing an
entry is software coverage, not proof of successful installation on every CPU,
NIC, disk controller or firmware combination. Physical acceptance is recorded
separately by the operator.

## Installation results

- The installed system writes `/run/ventoy-install-report.txt` and a persistent
  copy in `/var/lib/ventoy-center/installation-report.txt`. These files contain hostname,
  IPv4 addresses, kernel, RAID status, update-policy check, setup status and hash.
  Reports are uploaded to the center in the background. Boot and login screens
  keep the distribution's normal prompts; Ventoy does not print a setup reminder
  or redraw getty. Running an updated setup removes the two recognized legacy
  Ventoy banner files, while preserving customized files, `/etc/issue` and
  `/etc/motd`. Existing authenticated shells, SSH and network services are not
  restarted.
- Automatic installation checks and full setup execution are separate. Manual
  installation retains the account/network choices made in the installer.
  Ubuntu/Debian update protection applies during installation; the remaining full
  configuration and software installation require `./ventoy-linux-setup.run`.
- Original installer errors are collected from named logs. Automatic failure
  hooks and passive manual-install observers upload bounded, redacted reports to
  the **Installation results and diagnostics** page. Observations do not fail a
  task, authorize disks, or retry a destructive operation. Without networking,
  `/tmp/ventoy-install-diagnostic.log` remains available in the installer.
- Before the existing wipe confirmation, the console previews selected serials,
  firmware, RAID1 layout, filesystem and mount sizes. Capacity tiers use the
  smaller RAID member. `/home` is an estimate allowing for metadata/alignment;
  the installer still verifies actual devices and exact allocation separately.

## Central dependency cache

Optional configuration (example private controller address):

```json
{
  "installer_cache_dir": "/home/ventoy-center/cache/installer-dependencies",
  "installer_cache_listen": "192.168.1.2:26081",
  "installer_cache_url": "http://192.168.1.2:26081",
  "installer_cache_max_bytes": 8589934592
}
```

Port 26081 serves only repository objects, never management APIs, diagnostic
reports or private software credentials. Permit this port from the installation
LAN. The origin must match the controller's private IPv4 address. APT keeps
upstream signature/hash verification; no `trusted=yes` or insecure-repository
option is enabled. Upstreams are fixed official Ubuntu/Debian hosts over HTTPS,
not arbitrary proxy URLs. Only `dists` and `pool` paths are accepted.

The service user must own the cache directory. When using the supplied hardened
systemd service, add that exact directory to `ReadWritePaths` in a service
drop-in, then reload systemd. Keep the rest of the filesystem protection enabled.
Limit the firewall opening to the installation LAN rather than exposing the
listener on every network. Cache misses queue with a bounded wait; existing
objects remain readable while another package downloads.
Cold downloads allow up to ten minutes upstream and five minutes queued; APT's
HTTP timeout is twenty minutes so a slow first fetch can finish before the
installer abandons it. Failed/incomplete downloads are never published.

Ubuntu automatic configs, supported manual Subiquity defaults and Debian mirror
selection use the cache. Native preload hooks rewrite only recognized official
APT mirrors, preserving suites/components and Signed-By. A user-selected custom
mirror remains unchanged. EL installations use their existing ISO DVD package
repositories. This is not a complete offline mirror: the first request for a
missing object still needs upstream access. Metadata expires after ten minutes;
packages/by-hash objects are immutable. An expired index is not silently served
when upstream validation fails. Objects are published atomically after a complete
download, with a 256 MiB object limit and bounded total cache size. Large optional
packages outside the limit require another configured repository.

## Repeatable release and physical acceptance

Every release runs Go unit/race tests, native installer syntax/recipe checks,
the existing isolated storage/update/software tests, and
`scripts/validate_install_support.py`. The latter exercises source rewriting,
inert target hooks, report lifecycle, console redraw and disk-tier previews.
Before production, prepare every enabled entry in an isolated controller and
verify injection hashes, common setup hash, all shared ISO paths and bindings.
Publish only when network installers are idle; retain a rollback snapshot.

For each **OS version × manual/automatic × test platform** record:

1. ISO hash, controller/setup release, UEFI/BIOS, CPU, NIC/driver and disk serials.
2. Clean install and reinstall over the previous OS. Include single disk and
   RAID1/LVM where supported. Check the wipe scope and displayed size allocation;
   an unselected/USB disk must remain unchanged.
3. Manual mode: choose installation settings in the installer; verify that setup
   is preloaded and not reported as executed. Run setup explicitly when testing
   the complete configuration. Automatic mode: wait for first-boot checks.
4. Verify an actual KVM login and a new root SSH connection, hostname, DHCP lease,
   kernel lock, disabled automatic updates, default filesystem and mounts.
5. Capture the first report below, reboot normally from disk, capture a second
   report and compare. Repeat for the other installation mode. No forced reboot
   or power-cycle may substitute for the normal reboot check.
6. Record success/failure and original logs. A successful Intel run is not AMD or
   E610 hardware acceptance. Degraded-array boot recovery is a separate test.

On the installed machine (read-only apart from saving the evidence):

```sh
sudo sh /usr/local/lib/ventoy-install-support/acceptance.sh
```

Copy both saved reports to the review machine and compare:

```sh
python3 scripts/validate_install_acceptance.py first.txt second.txt --require-setup
```

The comparison rejects identical boot IDs, changed kernels/hostnames/filesystems,
missing DHCP/SSH/update-policy checks, degraded RAID and incomplete setup. It
does not authenticate a password, prove hardware fault tolerance or perform
reboots. Keep real SSH/KVM login and disk-size checks in the acceptance record.

| OS / ISO hash | Mode | CPU / NIC / firmware | Storage | First boot | Second boot | SSH / KVM | Setup | Result / evidence |
|---|---|---|---|---|---|---|---|---|
| Fill during acceptance | manual or automatic | Intel / AMD; actual devices | single / RAID1; ext4 / XFS | boot ID | different boot ID | actual login | hash + status | pending until tested |

Physical acceptance of alpha.48 remains **pending operator testing**. Historical
hardware results do not certify this release without repeating these checks.
