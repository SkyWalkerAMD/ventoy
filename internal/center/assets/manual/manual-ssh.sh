#!/usr/bin/env bash
set -Eeuo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C
umask 077
mode=${1:---check}; keep=${2:-0}; root_password_file=${3:-}
state=/var/lib/ventoy-center/manual-init
die() { echo "SSH: $*" >&2; exit 1; }
. /etc/os-release
case "$ID" in ubuntu|debian) family=apt; service=ssh;; *) family=rpm; service=sshd;; esac
case "$mode" in --apply|--check) ;; *) exit 2;; esac
# Socket activation can leave ssh.service inactive until the first connection.
# /run is recreated on every boot, so a previous apply cannot prepare this
# directory for a later --check. Create only the expected empty runtime path;
# never follow a link or repair an existing unsafe directory by chmod/chown.
prepare_sshd_runtime() {
    local permissions
    [[ -d /run && ! -L /run && $(stat -c '%u:%g' /run) == 0:0 ]] || die 'Unsafe SSH runtime parent: /run.'
    permissions=$(stat -c '%a' /run)
    [[ $permissions =~ ^[0-7]{3,4}$ ]] && (( (8#$permissions & 0022) == 0 )) || die 'Unsafe SSH runtime parent permissions: /run.'
    if [[ ! -e /run/sshd && ! -L /run/sshd ]]; then
        if mkdir -m 0755 /run/sshd 2>/dev/null; then
            if command -v restorecon >/dev/null; then restorecon /run/sshd; fi
        else
            # A first incoming connection may start sshd concurrently. Validate
            # its directory below; do not fail merely because it appeared.
            [[ -e /run/sshd || -L /run/sshd ]] || die 'Cannot create SSH runtime directory: /run/sshd.'
        fi
    fi
    [[ -d /run/sshd && ! -L /run/sshd && $(stat -c '%a:%u:%g' /run/sshd) == 755:0:0 ]] || die 'Unsafe SSH runtime directory: /run/sshd (expected root:root 0755).'
}
ssh_listener_active() {
    local state
    systemctl is-active --quiet "$service.service" && return 0
    [[ $family == apt ]] && systemctl is-active --quiet ssh.socket || return 1
    # An idle socket is valid; an already failed daemon must remain a failure.
    state=$(systemctl show "$service.service" -p ActiveState --value) || return 1
    case "$state" in inactive|activating|active|reloading) return 0;; *) return 1;; esac
}
prepare_sshd_runtime
# An explicit user-only choice survives full setup, migration, --check and boot
# recovery. Never recreate passwords or prepend root=yes in this mode.
if [[ $family == apt && ( -e "$state/login-policy.json" || -L "$state/login-policy.json" ) ]]; then
    here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
    exec python3 "$here/login-mode.py" --check
fi
if [[ $mode == --apply ]]; then
    if ! command -v sshd >/dev/null || ! command -v ssh >/dev/null || ! command -v sudo >/dev/null; then
        [[ ${VC_MANUAL_OFFLINE:-0} == 0 ]] || die 'SSH/sudo packages missing in offline mode. Install from your OS media and rerun.'
        if [[ $family == apt ]]; then
            apt_timeout=20
            [[ ! -f /etc/apt/apt.conf.d/90ventoy-installer-cache ]] || apt_timeout=1200
            apt-get -o Acquire::Retries=1 -o "Acquire::http::Timeout=$apt_timeout" update
            DEBIAN_FRONTEND=noninteractive apt-get -y --no-upgrade --no-install-recommends install openssh-server openssh-client sudo
        else
            manager=yum; command -v dnf >/dev/null && manager=dnf
            "$manager" -y --exclude='kernel*' install openssh-server openssh-clients sudo
        fi
    fi
    # Older setup versions marked completion for admin. Apply the new account
    # once, preserving that existing user and its files rather than renaming it.
    [[ -f "$state/accounts-set" && $(cat "$state/accounts-set") == user ]] || {
        backup=$(mktemp -d "$state/accounts-backup.XXXXXXXX")
        cp -p /etc/passwd /etc/shadow /etc/group /etc/gshadow "$backup/"
        if ! getent passwd user >/dev/null; then
            [[ $keep == 0 ]] || die '--keep-passwords requires an existing user account.'
            useradd -m -s /bin/bash user
        fi
        uid=$(id -u user)
        ((uid >= 1000 && uid != 65534)) || die 'Existing user is a system account; retained.'
        group=wheel; [[ $family != apt ]] || group=sudo
        getent group "$group" >/dev/null || groupadd "$group"
        usermod -a -G "$group" user
        printf 'user ALL=(ALL:ALL) ALL\n' > "$backup/sudoers.new"
        visudo -cf "$backup/sudoers.new"
        [[ ! -L /etc/sudoers.d/90-ventoy-manual-user ]] || die 'Unexpected sudoers symlink.'
        [[ ! -f /etc/sudoers.d/90-ventoy-manual-user ]] || cp -p /etc/sudoers.d/90-ventoy-manual-user "$backup/"
        install -m 0440 "$backup/sudoers.new" /etc/sudoers.d/90-ventoy-manual-user
        if command -v restorecon >/dev/null; then restorecon /etc/sudoers.d/90-ventoy-manual-user; fi
        visudo -c
        if [[ $keep == 0 ]]; then
            {
                printf 'user:ventoy\n'
                [[ -f "$state/root-password-custom" ]] || printf 'root:ventoy\n'
            } | chpasswd
        fi
        printf 'user\n' > "$state/accounts-set"
    }
    cfg=/etc/ssh/sshd_config
    [[ -f $cfg && ! -L $cfg ]] || die 'sshd_config must be a regular file.'
    ssh-keygen -A
    backup=$(mktemp -d "$state/ssh-backup.XXXXXXXX")
    cp -p "$cfg" "$backup/sshd_config"
    tmp=$(mktemp /etc/ssh/.ventoy-manual.XXXXXXXX)
    trap 'rm -f "$tmp"' EXIT
    {
        printf '%s\n' '# BEGIN VENTOY MANUAL SSH' 'PermitRootLogin yes' 'PasswordAuthentication yes' '# END VENTOY MANUAL SSH'
        sed '/^# BEGIN VENTOY MANUAL SSH$/,/^# END VENTOY MANUAL SSH$/d' "$cfg"
    } > "$tmp"
    chmod --reference="$cfg" "$tmp"; chown --reference="$cfg" "$tmp"
    sshd -t -f "$tmp"
    mv -f "$tmp" "$cfg"
    command -v restorecon >/dev/null && restorecon "$cfg"
    if [[ -d /etc/cloud/cloud.cfg.d ]]; then
        [[ ! -f /etc/cloud/cloud.cfg.d/99-ventoy-root-ssh.cfg ]] || cp -p /etc/cloud/cloud.cfg.d/99-ventoy-root-ssh.cfg "$backup/"
        printf 'disable_root: false\nssh_pwauth: true\n' > /etc/cloud/cloud.cfg.d/99-ventoy-root-ssh.cfg
    fi
    # Preserve an already enabled socket activation path. Enabling ssh.service
    # as well creates the sshd alias and reloads systemd on Ubuntu 24.04; that
    # can leave the socket-activated listener outside the unit's MainPID. A
    # reload then updates only the new listener, leaving old login policy live.
    enable_ssh() {
        if [[ $family == apt ]] && systemctl is-enabled --quiet ssh.socket && systemctl is-active --quiet ssh.socket; then
            return 0
        fi
        systemctl enable "$service.service"
    }
    if ! sshd -t || ! enable_ssh || ! systemctl start "$service.service" || ! systemctl reload "$service.service"; then
        cp -p "$backup/sshd_config" "$cfg"
        command -v restorecon >/dev/null && restorecon "$cfg"
        sshd -t && systemctl reload "$service.service" || true
        die "SSH activation failed; original daemon config restored from $backup."
    fi
    port=$(sshd -T | awk '$1=="port" && !seen++ {print $2}')
    [[ $port =~ ^[0-9]+$ ]] || die 'Cannot determine SSH port.'
    if command -v firewall-cmd >/dev/null && firewall-cmd --state >/dev/null 2>&1; then
        zones=$(firewall-cmd --get-active-zones | awk '/^[^ ]/ {print $1}')
        [[ -n $zones ]] || zones=$(firewall-cmd --get-default-zone)
        for zone in $zones; do
            firewall-cmd --zone="$zone" --add-port="$port/tcp"
            firewall-cmd --permanent --zone="$zone" --add-port="$port/tcp"
        done
    elif command -v ufw >/dev/null && ufw status | grep -qx 'Status: active'; then
        ufw allow "$port/tcp"
    fi
fi
sshd -t
ssh_listener_active || die 'Neither a healthy SSH service nor its activation socket is active.'
effective=$(sshd -T -C user=root,host=localhost,addr=127.0.0.1)
grep -qx 'permitrootlogin yes' <<< "$effective" || die 'Effective root login policy is not yes.'
grep -qx 'passwordauthentication yes' <<< "$effective" || die 'Effective password authentication is not yes.'
port=$(awk '$1=="port" {print $2;exit}' <<< "$effective")
for user in root user; do
    secret=$(getent shadow "$user" | cut -d: -f2)
    case "$secret" in ''|'!'*|'*'*) die "$user password is unavailable or locked.";; esac
done
sudo -l -U user >/dev/null
if [[ $keep == 0 ]]; then
    # Test actual password authentication; do not confuse sshd -T with a login.
    # /run is mounted noexec by the installed security policy on some systems.
    scratch=$(mktemp -d "$state/ssh-check.XXXXXXXX")
    trap 'rm -rf -- "$scratch"' EXIT
    printf '#!/bin/sh\nprintf "%%s\\n" ventoy\n' > "$scratch/askpass"
    chmod 0700 "$scratch/askpass"
    if [[ -n $root_password_file ]]; then
        [[ -f $root_password_file && ! -L $root_password_file &&
            $(stat -c '%a:%u:%h' "$root_password_file") == 600:0:1 &&
            ${root_password_file%/*/*} == "$state" &&
            ${root_password_file##*/} == root-password ]] || die 'Invalid temporary root password file.'
        # The directory is generated by mktemp, never a caller-provided shell
        # expression. Only the short-lived root-only file contains plaintext.
        [[ ${root_password_file%/*} == "$state"/password-check.* &&
            $root_password_file != *[!a-zA-Z0-9_./-]* ]] || die 'Invalid password file path.'
        printf '#!/bin/sh\ncat -- "%s"\n' "$root_password_file" > "$scratch/root-askpass"
        chmod 0700 "$scratch/root-askpass"
    fi
    for key in /etc/ssh/ssh_host_*_key.pub; do
        [[ -f $key ]] || continue
        awk -v host="[127.0.0.1]:$port" '{print host " " $1 " " $2}' "$key" >> "$scratch/known_hosts"
        awk '{print "127.0.0.1 " $1 " " $2}' "$key" >> "$scratch/known_hosts"
    done
    login_accounts=(root user)
    # Changing root's password must not test or alter a retained user password.
    [[ -z $root_password_file ]] || login_accounts=(root)
    for user in "${login_accounts[@]}"; do
        askpass=$scratch/askpass
        if [[ $user == root && -n $root_password_file ]]; then
            askpass=$scratch/root-askpass
        elif [[ $user == root && -f "$state/root-password-custom" ]]; then
            echo "SSH_ACCOUNT_CONFIG_VERIFIED user=root port=$port; custom password retained, no plaintext stored for later login tests."
            continue
        fi
        # Some units reload with kill -HUP, which returns before sshd has
        # re-executed and read its new configuration. Still require a real
        # password login; allow that brief transition only during --apply.
        attempts=1; [[ $mode != --apply ]] || attempts=3
        result=''; verified=0
        for ((attempt=1; attempt<=attempts; attempt++)); do
            if result=$(DISPLAY=:0 SSH_ASKPASS="$askpass" SSH_ASKPASS_REQUIRE=force setsid ssh -F /dev/null -p "$port" \
                -o ConnectTimeout=8 -o NumberOfPasswordPrompts=1 -o PubkeyAuthentication=no -o PreferredAuthentications=password \
                -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$scratch/known_hosts" "$user@127.0.0.1" 'id -un' </dev/null 2>"$scratch/login-error"); then
                if [[ $result == "$user" ]]; then verified=1; break; fi
            fi
            ((attempt == attempts)) || sleep 1
        done
        if ((verified == 0)); then
            cat "$scratch/login-error" >&2
            die "$user actual SSH password login failed."
        fi
        echo "SSH_PASSWORD_LOGIN_VERIFIED user=$user port=$port"
    done
else
    echo "SSH_CONFIG_VERIFIED port=$port; retained passwords require a client-side login test."
fi
