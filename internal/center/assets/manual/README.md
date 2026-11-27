# Ventoy Linux setup

For x86_64 Ubuntu 20-26, Debian 10-13, and CentOS / Rocky / AlmaLinux / RHEL 7-10.
Run after booting the installed OS from disk, not in a live installer or chroot.
Setup configures the existing system; it does not repartition disks or reinstall the OS.
Setup prompts, diagnostics, help, and the network/hostname helper use English.
The E610 offline bundle and its vendor installer messages are retained unchanged.

Packages older than alpha.49 do not recognize upgrade options. Obtain
`ventoy-setup-upgrade.sh` from the center tools directory, place it beside the
old runner, and run `bash ventoy-setup-upgrade.sh` once as root. It verifies the
center with the old package's HTTPS trust, backs up and replaces the runner,
repairs executable permission and its checksum file, then applies current setup
while retaining existing passwords. Use `--update-setup` for download only.
After this one-time migration, use `./ventoy-linux-setup.run --upgrade` normally.
If a file transfer removed executable permission, invoke the updater with
`bash ventoy-linux-setup.run --upgrade`; current setup repairs the permission.

## Run setup

Both manual and PXE automatic installations preload `/root/ventoy-linux-setup.run`.

Optional Ubuntu/Debian ordinary-user login:

```sh
sudo /root/ventoy-linux-setup.run --restore-user-login
# For a different existing administrator account:
sudo /root/ventoy-linux-setup.run --restore-user-login --login-user alice
sudo /root/ventoy-linux-setup.run --check-login
```

This action asks for the selected user's current password (hidden), verifies an
actual local SSH login and sudo access, then disables root SSH and locks root's
console password. The default selected account is `user`. It does not reset any
password, create an account, install software or terminate current sessions.
The ordinary user must already exist with working SSH and sudo; failed checks
leave the login policy unchanged, and failures during the change roll it back.
Open a new ordinary-user session before closing your current session. Use
`sudo -i` after login for root access; BMC web credentials are independent.

This is opt-in. New installations still enable direct root login as before.
The saved user/sudo choice survives setup, `--upgrade` and boot recovery; in this
mode the root-password dialog is skipped so it cannot unlock root accidentally.
`--check-login` checks configuration and account state, without prompting or
claiming a fresh password-login test. Full setup still applies all other policies.
Run as root, or with sudo:

```bash
cd /root
./ventoy-linux-setup.run
# Optionally specify the hostname:
./ventoy-linux-setup.run --hostname server01
```

No arguments applies the system configuration, installs or upgrades matching default
software from the center, and verifies the results. `--apply` is a compatible alias.
`--software` installs software only; `--list-software` previews available packages;
`--check-software` verifies installed software and retained package files.
`--offline` prohibits package downloads. Missing SSH, network parsing tools, or
exact-kernel build dependencies are reported as failures, not successful setup.

Interactive full setup first displays the current hostname. Enter a new name, or
press Enter to retain the current persistent name. `--hostname NAME` skips this
question. An explicit name is applied once; later administrator changes are kept
on reruns and reboot. Non-interactive runs and boot recovery never prompt.
If no name is specified, a generic localhost name is replaced with a machine-based
name. Node enrollment requires a unique hostname, with matching runtime and
persistent values; common defaults such as ubuntu are not accepted for enrollment.

After full setup, an interactive root password prompt lets you enter and confirm
a new password without displaying it. Press Enter to keep the current password.
The new password is tested with an actual local root SSH login. The user account
password is unchanged. Temporary verification files are root-only and deleted
after use; the new password is never logged or retained for boot recovery.
Subsequent checks verify account and SSH policy without storing the plaintext.
Non-interactive runs, boot recovery, and software-only mode do not ask for passwords.

Initial credentials are `user / ventoy` and `root / ventoy`, with SSH password
login enabled. Other existing users are not deleted or renamed. Configured
passwords are retained on reruns. Use `--keep-passwords` on an unconfigured system
to preserve existing user/root passwords; both must already have usable passwords.
In that mode, setup verifies policy; test login separately from your SSH client.

The launcher supports Python 2.7, Python 3, and EL8 platform-python. Minimal
systems do not need a separate tar command. An extracted tar.gz bundle can also
be run with `sudo bash ventoy-manual-setup/install.sh`.

## Upgrade an installed setup

```bash
./ventoy-linux-setup.run --check-version
./ventoy-linux-setup.run --upgrade
```

Since alpha.50, `--upgrade` downloads and verifies the latest setup from the
trusted center, backs up the old file, applies new features, and checks results.
Existing nodes do not need an OS reinstall. Configuration migrations follow the
package contents, even if an older setup previously marked the system complete.
Custom passwords, hostname, and existing networks are retained unless you
explicitly change them. Failed or pending work remains available for retry.

`--update-setup` replaces the file without running it. Nodes using alpha.49 should
run that command, then run the new setup. `--check-version` displays the local,
center, and last verified configuration versions. Boot recovery does not download
a new setup or reinstall center software. Only an explicit full setup, `--upgrade`,
or `--software` requests software updates. No automatic reboot or kernel upgrade
is performed.

## Configuration and software

- Check E610 PCI devices and the effective driver. Keep native support; otherwise
  install the exact OS/kernel offline module, update initramfs, and keep rollback
  backups. The r4 release includes 93 exact OS/kernel targets and delegates to
  its original nested installers. An unsupported kernel stops before changes;
  a module for another kernel is never substituted. Vendor diagnostics are kept
  in the private log printed by setup. Secure Boot enrollment remains pending
  until completed at the console; setup never unloads an active network driver.
- Enable root/user SSH password login, user sudo access, and the SSH service.
  Verify actual local password logins when the password is known. Allow the SSH
  port through an already active firewalld or UFW configuration.
- Set and verify the hostname. Add DHCP to unconfigured hardware wired NICs,
  activate newly created profiles, and check linked interfaces for IPv4 leases.
  Preserve existing DHCP/static networks, Bond/VLAN/Bridge, USB, Wi-Fi, and the
  active SSH interface. Secondary profiles do not take over default routes or DNS.
  Supported backends include NetworkManager, Netplan, systemd-networkd, ifupdown
  with ISC dhclient or Debian 13 dhcpcd, and legacy ifcfg with validated dhclient
  hooks. Complex or uncertain configurations are reported for review.
- Lock the installed kernel packages. Disable APT periodic refresh and
  unattended-upgrades, or yum-cron / DNF automatic upgrades and cache refresh.
  Verify persistent settings and current service state. Explicit package-manager
  commands remain available; missing software dependencies may be installed.
- Default to CLI boot and install a service that resumes pending system
  configuration and verifies it on later boots.
- Download matching DEB/RPM packages from the center and keep copies with their
  original names and mode 0600 in `/root/ventoy-tools/`, including when installation
  fails. Installed equal/newer versions are not reinstalled or downgraded. Missing
  copies are downloaded; matching hashes skip transfers. Locally modified files
  are preserved and reported. Replacing packages in center tools takes effect on
  the next explicit run without rebuilding setup.
- Copy and verify archives and standalone tools in `/root/ventoy-tools/` without
  extracting or executing them. P95 is separate: setup does not install, start,
  stop, or check its helper. Run `bash /root/ventoy-tools/p95-priority-setup.sh`
  manually when needed; use its `--check` to inspect the helper. Existing P95
  installations are left intact.
- When the center has private enrollment settings, invoke the official
  `sckocstp-node` / `fyhocsys-node join --key-file` after successful installation.
  The center and node must support version 0.8.6 or newer. Verify the connection
  configuration, certificate pin, worker, and boot service. The node uses the
  current hostname and native DMI asset identity. Existing enrollment with the
  same center is retained. Enrollment failures preserve the retry request.
  Private keys are neither logged nor embedded in packages; temporary key files
  are deleted after use. The native node service reconnects on boot. Enrollment
  is independent of FYHOC boot-time unlocking.

## Results, reboot, and recovery

`VERIFIED` means all applicable checks in that stage passed.
`E610_NOT_PRESENT` means there is no E610 hardware and
no driver was replaced. Exit 3 / `PENDING` means a driver reboot, MOK enrollment,
or DHCP lease is still required. Exit 4 means system checks finished but software
installation or verification failed. Neither is a fully verified setup.

Setup never unloads a working NIC driver or reboots the machine automatically.
If a new E610 driver requires reboot, schedule a maintenance window. The installed
service then configures newly available NICs and verifies them. Secure Boot may
require manual certificate enrollment in the firmware MOK screen.

```bash
sudo bash /opt/ventoy-manual/current/install.sh --check
sudo cat /var/lib/ventoy-center/manual-init/status
sudo journalctl -u ventoy-manual-init.service
```

Logs: `/var/log/ventoy-manual-init.log` and `/var/log/ventoy-software.log`.
Configuration/account state and backups: `/var/lib/ventoy-center/manual-init/`
(root-only). Hostname backups: `/var/backups/safe-server-init/`.
For E610 rollback, use the installer path printed during installation with
`--rollback`. Source builds use
`/var/lib/e610-ixgbe/manual-OS-KERNEL/payload/install.sh`.
Original vendor files and their checksums are retained unchanged.

To change the hostname later, use `sudo hostnamectl set-hostname server02`.
Add `sudo safe-server-init hostname server02 --update-hosts` if local hosts entries
also need updating. Upgrade and run setup once on nodes with older hostname
recovery behavior so future boots preserve administrator changes.

After an interactive hostname change, setup reports the active hostname and
returns to the original login with its exit status. If Bash still shows the old
name in the prompt, run `exec bash` in that shell or log in again. One `exit`
from the original console login returns it to the login screen. Pending checks
(exit 3) or software failures (exit 4) still allow the optional root password
prompt.

Setup does not downgrade a kernel already changed during manual installation.
Downloading setup alone does not add E610 support to the live ISO installer;
use an adapted image/injection if the installer cannot access the NIC.
