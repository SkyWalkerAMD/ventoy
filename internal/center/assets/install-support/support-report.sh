#!/bin/sh
# Read-only checks plus report files; never restarts getty/SSH/network services.
set -eu
export LC_ALL=C
umask 077
state=/var/lib/ventoy-center
mkdir -p "$state" /run/lock
exec 9>/run/lock/ventoy-install-report.lock
flock -n 9 || exit 0
boot=$(cat /proc/sys/kernel/random/boot_id)
tmp=$(mktemp /run/ventoy-install-report.XXXXXX)
trap 'rm -f "$tmp"' EXIT HUP INT TERM
mode=$(cat "$state/install-mode" 2>/dev/null || printf unknown)
release=$(cat "$state/install-release" 2>/dev/null || printf unknown)
kernel=$(uname -r)
rootfs=$(findmnt -n -o FSTYPE / 2>/dev/null || printf unknown)
case "$rootfs" in overlay|squashfs|iso9660|tmpfs|unknown) exit 0;; esac
initializing=no
for unit in cloud-init.service cloud-config.service cloud-final.service ventoy-center-bootstrap.service; do
    status=$(systemctl show "$unit" -p ActiveState 2>/dev/null | sed -n 's/^ActiveState=//p')
    [ "$status" != activating ] || initializing=yes
done
# A queued cloud-final/bootstrap must also settle before the final report.
if systemctl list-jobs --no-legend --no-pager 2>/dev/null | grep -Eq 'cloud-(init|config|final)|ventoy-center-bootstrap'; then initializing=yes; fi
{
    printf '\nVentoy installation report | %s | %s\n' "$release" "$mode"
    printf 'Booted installed system: %s | kernel %s | root filesystem %s\n' "$(hostname)" "$kernel" "$rootfs"
    ip -4 -o addr show scope global 2>/dev/null | awk '{print "IPv4: " $2 " " $4}'
    printf 'First-boot initialization: %s\n' "$initializing"
    if [ "$mode" = automatic ]; then
        if [ -f "$state/automatic-checks" ]; then
            printf 'Automatic installation checks: PASSED (SSH policy, filesystem, kernel/update policy).\n'
            printf 'Acceptance boot: '; sed -n 's/^boot=//p' "$state/automatic-checks"
            printf 'Current boot: %s (current update policy checked separately below).\n' "$boot"
        else
            printf 'Automatic installation checks: PENDING / FAILED; inspect journalctl -u ventoy-center-bootstrap.\n'
        fi
    else
        printf 'Manual installation: accounts and network follow your installer choices.\n'
    fi
    policy=/usr/local/sbin/ventoy-center-update-policy
    if [ -f "$policy" ]; then
        if /bin/sh "$policy" --check > "$state/report-update-check.log" 2>&1; then
            printf 'Kernel lock and automatic updates: VERIFIED.\n'
        else
            printf 'Kernel lock and automatic updates: NEEDS ATTENTION (report-update-check.log).\n'
        fi
    else
        printf 'Kernel lock and automatic updates: not independently verified here; run setup.\n'
    fi
    if [ -f /proc/mdstat ] && grep -q '^md' /proc/mdstat; then
        printf 'Software RAID (initial synchronization is not an installation failure):\n'
        cat /proc/mdstat
    fi
    if [ -f "$state/manual-init/status" ]; then
        printf 'Setup result: '; head -n 1 "$state/manual-init/status"
    else
        printf 'Setup: PRELOADED, NOT EXECUTED. Run /root/ventoy-linux-setup.run to configure hostname, passwords, SSH, DHCP and software.\n'
    fi
    if [ -f /root/ventoy-linux-setup.run.sha256 ]; then
        printf 'Preloaded setup SHA-256: '; cut -d ' ' -f 1 /root/ventoy-linux-setup.run.sha256
    fi
    printf 'Console login: enter your system username. If boot logs covered the login prompt, press Enter.\n'
    printf 'Full report: /run/ventoy-install-report.txt\n\n'
} > "$tmp"
chmod 0644 "$tmp"
mv -f "$tmp" /run/ventoy-install-report.txt
cp /run/ventoy-install-report.txt "$state/installation-report.txt"
chmod 0600 "$state/installation-report.txt"
# Keep reports available on disk and in the center without modifying login
# banners, redrawing getty or writing into an operator's console.
# Upload changed results after setup too. Keep the timer when an upload fails
# so an early DHCP race cannot silently lose the first-boot result.
uploaded=yes
if [ "$initializing" = no ]; then
    digest=$(sha256sum /run/ventoy-install-report.txt | cut -d ' ' -f 1)
    if [ "$(cat /run/ventoy-install-report-uploaded 2>/dev/null || true)" != "$digest" ]; then
        if /bin/sh /usr/local/lib/ventoy-install-support/support-diagnostic.sh result 'Installed system boot report' >/dev/null 2>&1; then
            printf '%s\n' "$digest" > /run/ventoy-install-report-uploaded
        else uploaded=no; fi
    fi
fi
# Once settled and saved, refresh at the next boot or explicitly after setup.
if [ "$initializing" = no ] && [ "$uploaded" = yes ]; then systemctl stop ventoy-install-report.timer || true; fi
