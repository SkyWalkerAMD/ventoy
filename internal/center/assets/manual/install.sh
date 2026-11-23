#!/usr/bin/env bash
# Ventoy Center manual-install setup. Run after booting the installed OS.
set -Eeuo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C SYSTEMD_PAGER=cat
umask 077
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
state=/var/lib/ventoy-center/manual-init
mode=--apply
case "${1:-}" in
    --apply|--resume|--check|--software|--list-software|--check-software|--install-fyhoct|--uninstall|--restore-user-login|--check-login|--help|-h)
        mode=$1; shift;;
esac
name=; offline=0; keep_passwords=0; login_user=; legacy=0
die() { echo "Manual setup: $*" >&2; exit 1; }
while (($#)); do
    case "$1" in
        --hostname) (($# >= 2)) || exit 2; name=$2; shift;;
        --offline) offline=1;;
        --keep-passwords) keep_passwords=1;;
        --include-legacy-packages) legacy=1;;
        --login-user) (($# >= 2)) && [[ -n $2 && $2 != -* ]] || exit 2; login_user=$2; shift;;
        *) die "Unknown argument: $1";;
    esac
    shift
done
case "$mode" in
    --apply|--resume|--check|--software|--list-software|--check-software|--install-fyhoct|--uninstall|--restore-user-login|--check-login) ;;
    --help|-h)
        cat <<'HELP'
sudo ./ventoy-linux-setup.run [--hostname NAME] [--offline] [--keep-passwords]
sudo bash install.sh [--hostname NAME] [--offline] [--keep-passwords]
sudo bash /opt/ventoy-manual/current/install.sh --check
sudo bash ventoy-linux-setup.run --software
sudo bash ventoy-linux-setup.run --list-software
sudo bash ventoy-linux-setup.run --check-software
sudo bash ventoy-linux-setup.run --install-fyhoct
sudo bash ventoy-linux-setup.run --uninstall [--login-user user] [--include-legacy-packages]
sudo bash ventoy-linux-setup.run --restore-user-login [--login-user user]
sudo bash ventoy-linux-setup.run --check-login

Installs E610 support when required; enables root/user SSH password login;
configures unconfigured wired NICs for DHCP and activates new profiles;
locks the installed kernel, disables automatic updates, and verifies results.
No arguments applies the full configuration and installs/verifies the matching
default software group. --apply remains a compatible alias for this default.
Root-level archives and standalone tools from the software library are copied
and verified in /root/ventoy-tools without extraction or execution.
Matching DEB/RPM packages are retained there too, including on installation failure.
Configured sckocstp/fyhocsys 0.8.6+ nodes join their pinned center after installation;
their native services start on boot. Enrollment failures keep the setup retry request.
--software installs that group alone; no account/network/hostname changes.
--install-fyhoct explicitly installs sckoct-fyh and initializes its components.
The current persistent hostname is preserved unless --hostname NAME is given.
An explicit hostname is applied once; later administrator changes are retained.
Interactive full setup asks for a hostname; Enter keeps the current name.
Boot recovery and non-interactive runs do not prompt.
Missing dependencies may be installed from this system's configured repositories.
Default initial credentials: user / ventoy, root / ventoy.
Existing users and configured static networks are preserved. --keep-passwords
retains existing account passwords (root must already have an unlocked password).
Missing packages may be installed, but no system/kernel upgrade is performed.
--offline prohibits package downloads. E610 driver activation may need a reboot;
the installed service resumes setup and verifies it on subsequent boots.
Exit 0 = verified, 1 = failed, 2 = invalid arguments, 3 = pending/reboot required.
Exit 4 = system checks completed, but software installation/verification failed.
Optional Ubuntu/Debian action --restore-user-login verifies an existing user's
password SSH login and sudo, then disables root SSH and console password login.
It changes no passwords or software. Future setup/upgrade runs retain this choice.
New installations still allow direct root login by default. --check-login is read-only.
--uninstall previews and removes setup-owned packages and files after confirmation.
On Ubuntu/Debian it verifies an ordinary user's SSH and sudo before disabling direct root login.
--include-legacy-packages also offers matching packages from the old software report.
HELP
        exit 0;;
    *) exit 2;;
esac
if [[ -n $login_user && $mode != --restore-user-login && $mode != --uninstall ]]; then
    die '--login-user requires --restore-user-login or --uninstall.'
fi
if [[ $legacy == 1 && $mode != --uninstall ]]; then
    die '--include-legacy-packages requires --uninstall.'
fi
if [[ $mode == --uninstall ]]; then
    [[ -z $name && $offline == 0 && $keep_passwords == 0 ]] || die 'Uninstall cannot be combined with full-setup options.'
fi
if [[ $mode == --restore-user-login || $mode == --check-login ]]; then
    [[ -z $name && $offline == 0 && $keep_passwords == 0 ]] || die 'Login actions cannot be combined with full-setup options.'
fi
if [[ $mode == --install-fyhoct ]]; then
    [[ -z $name && $offline == 0 && $keep_passwords == 0 ]] || die '--install-fyhoct does not accept additional options.'
fi
if [[ -n "$name" && $mode != --apply ]]; then
    echo '--hostname requires full setup; run setup --hostname NAME before software-only enrollment.' >&2
    exit 2
fi
[[ $EUID == 0 && -d /run/systemd/system ]] || die 'Run as root in the installed, booted system.'
[[ $(stat -Lc '%d:%i' /) == $(stat -Lc '%d:%i' /proc/1/root) ]] || die 'Do not run in a chroot.'
[[ ! -e /run/anaconda && ! -e /run/casper && ! -e /lib/debian-installer ]] || die 'Do not run in the live installer.'
case "$(findmnt -n -o FSTYPE /)" in overlay|aufs|squashfs|tmpfs|ramfs) die 'Live/container root is not supported.';; esac
. /etc/os-release
case "$ID" in
    ubuntu|debian) family=apt;;
    centos|rocky|almalinux|rhel|ol|scientific|anolis) family=rpm;;
    *) die "Unsupported Linux distribution: $ID";;
esac
mkdir -p "$state"
exec 7>"$state/lock"
flock -n 7 || die 'Another setup/check is running.'
case "$mode" in
    --uninstall)
        (cd "$here" && sha256sum --status -c SHA256SUMS) || die 'Package integrity check failed.'
        uninstall_args=("${VENTOY_UNINSTALL_RUNNER:-}")
        [[ -z $login_user ]] || uninstall_args+=(--login-user "$login_user")
        [[ $legacy == 0 ]] || uninstall_args+=(--include-legacy-packages)
        for python in python3 /usr/libexec/platform-python python2 python; do
            if command -v "$python" >/dev/null && "$python" -c 'import fcntl' 2>/dev/null; then
                "$python" "$here/uninstall.py" "${uninstall_args[@]}"
                exit $?
            fi
        done
        die 'Uninstall requires Python.';;
    --restore-user-login|--check-login)
        [[ $family == apt ]] || die 'This optional login mode is only for Ubuntu and Debian.'
        (cd "$here" && sha256sum --status -c SHA256SUMS) || die 'Package integrity check failed.'
        command -v python3 >/dev/null || die 'Python 3 is required for this login action.'
        login_args=(--check)
        if [[ $mode == --restore-user-login ]]; then
            login_args=(--restore-user-login)
            [[ -z $login_user ]] || login_args+=(--login-user "$login_user")
        fi
        flock -u 7
        exec python3 "$here/login-mode.py" "${login_args[@]}";;
esac
software_action() {
    local python= candidate
    for candidate in python3 /usr/libexec/platform-python python2 python; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import ssl; ssl.create_default_context()' >/dev/null 2>&1; then
            python=$candidate; break
        fi
    done
    [[ -n $python ]] || die 'Software setup requires Python with verified TLS support (2.7.9+ or 3.x).'
    "$python" "$here/software.py" "$1"
}
case "$mode" in
    --software|--list-software|--check-software|--install-fyhoct)
        [[ $offline == 0 || $mode == --check-software ]] || die 'Software download is disabled by --offline.'
        (cd "$here" && sha256sum --status -c SHA256SUMS) || die 'Package integrity check failed.'
        exec > >(tee -a /var/log/ventoy-software.log) 2>&1
        software_action "$mode"
        exit $?;;
esac
choose_hostname() {
    # Read only during an explicit interactive full setup. Boot recovery and
    # software-only/check modes must never wait for console input.
    if [[ -z "$name" && -t 0 && -t 1 ]]; then
        printf 'Current hostname: %s\n' "$(cat /etc/hostname)"
        echo 'Automatic node enrollment uses this hostname; choose a unique name for each machine.'
        local attempt
        for attempt in 1 2 3; do
            read -r -p 'New hostname (Enter to keep current): ' name || {
                echo 'Hostname entry canceled; setup has not been applied.' >&2; exit 2;
            }
            [[ -n "$name" ]] || return 0
            name=${name,,}
            _si_hostname_valid "$name" && return 0
            echo 'Invalid hostname. Use letters, digits, dots and hyphens; no IP address or localhost.' >&2
        done
        echo 'No valid hostname entered; setup has not been applied.' >&2
        exit 2
    fi
    [[ -n "$name" ]] || return 0
    name=${name,,}
    _si_hostname_valid "$name" || { echo 'Invalid --hostname; setup has not been applied.' >&2; exit 2; }
}
if [[ $mode == --apply ]]; then
    (cd "$here" && sha256sum --status -c SHA256SUMS) || die 'Package integrity check failed.'
    # An existing setup owns account policy, not the administrator's current
    # passwords. Upgrades/retries must not reset them or try stale defaults.
    if [[ -f "$state/accounts-set" && $(cat "$state/accounts-set") == user ]]; then
        keep_passwords=1
    fi
    # Load only helper functions; hostname validation does not change the host.
    source "$here/safe-server-init.sh"
    choose_hostname
    # Keep a complete offline copy for automatic post-reboot continuation.
    release=$(sha256sum "$here/SHA256SUMS" | cut -c1-16)
    dest=/opt/ventoy-manual/$release
    [[ ! -L /opt/ventoy-manual && ! -L "$dest" ]] || die 'Unexpected package directory symlink.'
    if [[ "$here" != "$dest" ]]; then
        mkdir -p /opt/ventoy-manual
        if [[ ! -e "$dest" ]]; then
            tmp=$(mktemp -d /opt/ventoy-manual/.stage.XXXXXXXX)
            cp -a "$here/." "$tmp/"
            (cd "$tmp" && sha256sum --status -c SHA256SUMS) || die 'Installed package copy failed validation.'
            mv -T "$tmp" "$dest"
        fi
        (cd "$dest" && sha256sum --status -c SHA256SUMS) || die 'Stored package was modified.'
    fi
    ln -sfn "$dest" /opt/ventoy-manual/current.new
    mv -Tf /opt/ventoy-manual/current.new /opt/ventoy-manual/current
    args=(--resume)
    # This is a one-time request, not a permanent hostname policy. Older
    # releases left hostname-request behind forever; never replay that file.
    if [[ -n "$name" ]]; then
        printf '%s\n' "$name" > "$state/hostname-pending"
    else
        # A new invocation choosing to keep the name cancels an unfinished
        # older request. Only --resume retries a still-pending explicit name.
        rm -f -- "$state/hostname-pending"
    fi
    printf '%s\n' "$offline" > "$state/offline"
    printf '%s\n' "$keep_passwords" > "$state/keep-passwords"
    printf '%s\n' "$((1 - offline))" > "$state/software-request"
    install -m 0644 "$dest/ventoy-manual-init.service" /etc/systemd/system/ventoy-manual-init.service
    if command -v restorecon >/dev/null; then
        restorecon -R /opt/ventoy-manual /etc/systemd/system/ventoy-manual-init.service
    fi
    systemctl daemon-reload
    systemctl enable ventoy-manual-init.service
    systemctl reset-failed ventoy-manual-init.service || true
    flock -u 7
    exec bash "$dest/install.sh" "${args[@]}"
fi
[[ -f "$state/offline" && -f "$state/keep-passwords" ]] || die 'Run setup without arguments (or with --apply) first.'
offline=$(cat "$state/offline"); keep_passwords=$(cat "$state/keep-passwords")
# Old runners can have a configured marker but no versioned migration state.
# The content digest also handles rebuilds with changed embedded policy/config.
(cd "$here" && sha256sum --status -c SHA256SUMS) || die 'Stored package integrity check failed.'
configuration_release=$(sha256sum "$here/SHA256SUMS" | cut -d' ' -f1)
if [[ -f "$state/accounts-set" && $(cat "$state/accounts-set") == user ]]; then keep_passwords=1; fi
export VC_MANUAL_OFFLINE=$offline
exec > >(tee -a /var/log/ventoy-manual-init.log) 2>&1
printf '\n[%s] mode=%s os=%s/%s kernel=%s\n' "$(date -Is)" "$mode" "$ID" "$VERSION_ID" "$(uname -r)"
current_stage=initialization
setup_stage() { current_stage=$1; printf '\nSETUP_STAGE: %s\n' "$current_stage"; }
trap 'rc=$?; flock -u 7; if ((rc != 0 && rc != 3)); then printf "failed stage=%s exit=%s time=%s\n" "$current_stage" "$rc" "$(date -Is)" > "$state/status"; echo "SETUP_FAILED_STAGE: $current_stage (exit $rc)" >&2; fi; if [[ -f "$here/support-report.sh" ]]; then /bin/sh "$here/support-report.sh" || true; fi' EXIT
if [[ $mode == --resume ]]; then
    /bin/sh "$here/support-install.sh" /
    systemctl daemon-reload
    systemctl start ventoy-install-report.timer
fi
printf 'running %s\n' "$(date -Is)" > "$state/status"
pending=0
if [[ $mode == --resume ]]; then
    # A console/SSH login can become available before Ubuntu's first-boot
    # cloud-config job finishes writing SSH and hostname settings. Join that
    # already queued job before applying our explicitly requested settings.
    # Do not start disabled cloud-init, or wait for cloud-final: the latter is
    # ordered after multi-user.target and would deadlock our resume service.
    if [[ $ID == ubuntu ]]; then
        jobs=$(systemctl list-jobs --no-legend --no-pager) || die 'Cannot inspect first-boot initialization.'
        if grep -Eq '(^|[[:space:]])cloud-config\.service([[:space:]]|$)' <<< "$jobs"; then
            echo 'Waiting for the queued Ubuntu cloud-config job before configuring the installed system.'
            timeout 180 systemctl start cloud-config.service || die 'Ubuntu cloud-config did not finish; retry setup after initialization completes.'
        fi
    fi
    # The driver step never unloads a live NIC driver or upgrades the kernel.
    setup_stage 'E610 driver preparation'
    rc=0; bash "$here/e610-driver.sh" --apply "$here/e610" || rc=$?
    case "$rc" in 0) ;; 3) pending=1;; *) die "E610 preparation failed (exit $rc); see log.";; esac
    # The current persistent hostname belongs to the administrator. The saved
    # hostname is an observation only; setup and boot recovery must not undo a
    # later hostnamectl/safe-server-init change, even after an earlier failure.
    setup_stage 'hostname and persistence'
    name=$(cat /etc/hostname)
    [[ ! -f "$state/hostname-pending" ]] || name=$(cat "$state/hostname-pending")
    case "${name,,}" in ''|localhost|localhost.localdomain) name=linux-$(cut -c1-8 /etc/machine-id);; esac
    if [[ -f "$state/hostname-pending" || $(cat /etc/hostname) != "$name" || $(hostname) != "$name" ]]; then
        name=${name,,}
        bash "$here/safe-server-init.sh" hostname "$name" --update-hosts
        [[ $(hostname) == "$name" && $(cat /etc/hostname) == "$name" ]] || die 'Requested hostname was not applied; node enrollment cannot run.'
    fi
    [[ $(hostname) == "$(cat /etc/hostname)" ]] || die 'Hostname verification failed.'
    cat /etc/hostname > "$state/hostname"
    # Consume only after the name was applied and verified. Retire the legacy
    # sticky request as well, without using it as a source for a new name.
    rm -f -- "$state/hostname-pending" "$state/hostname-request"
    if [[ -d /etc/cloud/cloud.cfg.d ]]; then
        printf 'preserve_hostname: true\n' > /etc/cloud/cloud.cfg.d/99-ventoy-manual-hostname.cfg
    fi
    if [[ ! -e "$state/configured" || ! -f "$state/accounts-set" || $(cat "$state/accounts-set") != user ||
          ! -f "$state/configuration-release" || $(cat "$state/configuration-release") != "$configuration_release" ]]; then
        setup_stage 'new setup configuration migration'
        printf 'SETUP_MIGRATION: applying configuration from %s\n' "$(cat "$here/VERSION")"
        if ! command -v python3 >/dev/null && ! command -v python >/dev/null && [[ ! -x /usr/libexec/platform-python ]]; then
            [[ $offline == 0 ]] || die 'Python is required for safe network parsing; install it from the OS media.'
            if [[ $family == apt ]]; then
                apt_timeout=20
                [[ ! -f /etc/apt/apt.conf.d/90ventoy-installer-cache ]] || apt_timeout=1200
                apt-get -o Acquire::Retries=1 -o "Acquire::http::Timeout=$apt_timeout" update
                DEBIAN_FRONTEND=noninteractive apt-get -y --no-upgrade --no-install-recommends install python3
            else
                manager=yum; command -v dnf >/dev/null && manager=dnf
                "$manager" -y --exclude='kernel*' install python3
            fi
        fi
        # DHCP can make package installation possible on an otherwise offline host.
        setup_stage 'DHCP configuration'
        rc=0; bash "$here/manual-network.sh" --apply 7>&- || rc=$?
        case "$rc" in 0) ;; 3) pending=1;; *) die "Network setup failed (exit $rc).";; esac
        setup_stage 'SSH and accounts'
        rc=0; bash "$here/manual-ssh.sh" --apply "$keep_passwords" || rc=$?
        if ((rc != 0)); then
            # Persist the requested update policy even if a missing SSH package
            # must wait until the E610 driver is active after reboot.
            sh "$here/linux-update-policy.sh" --apply
            die "SSH setup/check failed (exit $rc); inspect the log. Kernel/update policy was applied."
        fi
        setup_stage 'kernel lock and automatic-update policy'
        sh "$here/linux-update-policy.sh" --apply
        systemctl set-default multi-user.target
        install -m 0755 "$here/safe-server-init.sh" /usr/local/sbin/safe-server-init
        if command -v restorecon >/dev/null; then restorecon /usr/local/sbin/safe-server-init; fi
        touch "$state/configured"
    else
        # A newly available E610 interface after reboot needs DHCP once.
        setup_stage 'DHCP configuration'
        rc=0; bash "$here/manual-network.sh" --apply 7>&- || rc=$?
        case "$rc" in 0) ;; 3) pending=1;; *) die "Network setup failed (exit $rc).";; esac
    fi
fi
setup_stage 'system verification'
[[ -f "$state/configured" ]] || die 'Initial configuration has not completed.'
[[ -s /etc/hostname && $(hostname) == "$(cat /etc/hostname)" ]] || die 'Hostname verification failed.'
sh "$here/linux-update-policy.sh" --check
bash "$here/manual-ssh.sh" --check "$keep_passwords"
rc=0; bash "$here/manual-network.sh" --check || rc=$?
case "$rc" in 0) ;; 3) pending=1;; *) die "Network verification failed (exit $rc).";; esac
rc=0; bash "$here/e610-driver.sh" --check "$here/e610" || rc=$?
case "$rc" in 0) ;; 3) pending=1;; *) die "E610 verification failed (exit $rc).";; esac
[[ $(systemctl get-default) == multi-user.target ]] || die 'CLI boot target verification failed.'
if [[ $mode == --resume ]]; then
    # Record only after the new policy passed its checks. A failed migration
    # must retry even though an older release left the configured flag behind.
    printf '%s\n' "$configuration_release" > "$state/configuration-release.new"
    mv -f "$state/configuration-release.new" "$state/configuration-release"
    install -m 0600 "$here/VERSION" "$state/applied-version"
    printf 'SETUP_APPLIED_VERSION: %s (system configuration checked; software/pending status follows)\n' "$(cat "$here/VERSION")"
elif [[ ! -f "$state/configuration-release" || $(cat "$state/configuration-release") != "$configuration_release" ]]; then
    die 'This setup version has not been applied. Run full setup or --upgrade first.'
fi
if [[ $mode == --resume && $offline == 0 && -f "$state/software-request" && $(cat "$state/software-request") == 1 ]]; then
    # Only a user invocation of full setup creates this request. Normal subsequent
    # boots never fetch newly published software or upgrade existing packages.
    # Another interface may reach the software server while a secondary NIC
    # awaits DHCP or a driver awaits reboot. Keep pending checks independent
    # of the requested software transaction. Failures retain the retry request.
    if ((pending)); then
        echo 'SYSTEM_PENDING: continuing requested software installation using available networking.'
    fi
    # System checks above have completed. Distinguish a software failure so
    # the interactive launcher can still offer the independent password dialog
    # and refresh a changed hostname without reporting setup as successful.
    setup_stage 'software download, installation and verification'
    software_rc=0
    (software_action --software) || software_rc=$?
    if ((software_rc)); then
        echo 'SOFTWARE_FAILED: system configuration was checked, but software installation is incomplete.' >&2
        echo 'The software request is retained for retry; setup exits with status 4.' >&2
        exit 4
    fi
    printf '0\n' > "$state/software-request"
fi
if ((pending)); then
    echo 'PENDING: settings saved; driver reboot, firmware enrollment, or DHCP lease is still required.'
    echo 'Review the DHCP/E610 messages above. Requested software results are reported separately.'
    printf 'pending %s\n' "$(date -Is)" > "$state/status"
    exit 3
fi
printf 'verified boot=%s time=%s\n' "$(cat /proc/sys/kernel/random/boot_id)" "$(date -Is)" > "$state/status"
echo 'VERIFIED: SSH, hostname, networking, kernel lock, automatic-update disablement, and E610 status.'
