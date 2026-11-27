#!/usr/bin/env bash
# Optional one-time password change, only from the interactive .run launcher.
set +x
set -Eeuo pipefail
umask 077
ulimit -c 0
export PATH=/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C
[[ $EUID == 0 && -t 0 && -t 1 && -t 2 ]] || exit 0
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
state=/var/lib/ventoy-center/manual-init
[[ -d $state && ! -L $state && $(stat -c %u "$state") == 0 ]] || exit 1
[[ ! -L "$state/root-password-custom" ]] || exit 1
if [[ -e "$state/login-policy.json" || -L "$state/login-policy.json" ]]; then
    echo 'Root direct login remains disabled by the selected user/sudo policy; no root password change is offered.'
    exit 0
fi
exec 7>"$state/lock"
flock -n 7 || { echo 'Another setup/check is running; root password unchanged.' >&2; exit 1; }
choice_timeout=60
password_prompt_timeout=120
printf '\nChange the root password now? [y/N] (%ss, default: keep current) ' "$choice_timeout" >&2
if ! IFS= read -r -t "$choice_timeout" choice; then
    printf '\nRoot password retained.\n'
    exit 0
fi
case "$choice" in
    y|Y|yes|YES|Yes) ;;
    *) echo 'Root password retained.'; exit 0;;
esac

password=; confirmation=; matched=0
for attempt in 1 2 3; do
    if ! IFS= read -r -s -t "$password_prompt_timeout" -p 'New root password (input hidden, Enter to cancel): ' password; then
        echo; echo 'Root password change canceled; unchanged.'; exit 0
    fi
    echo
    [[ -n $password ]] || { echo 'Root password retained.'; exit 0; }
    if ! IFS= read -r -s -t "$password_prompt_timeout" -p 'Confirm new root password (input hidden): ' confirmation; then
        echo; echo 'Root password change canceled; unchanged.'; exit 0
    fi
    echo
    if [[ $password == "$confirmation" ]]; then matched=1; break; fi
    echo 'Passwords do not match; nothing changed.'
done
((matched)) || { echo 'Root password unchanged after three attempts.' >&2; exit 2; }
scratch=$(mktemp -d "$state/password-check.XXXXXXXX")
trap 'unset password confirmation; rm -rf -- "$scratch"' EXIT
printf '%s\n' "$password" > "$scratch/root-password"
chmod 0600 "$scratch/root-password"
if ! printf 'root:%s\n' "$password" | chpasswd; then
    echo 'Root password change failed; check the system password policy.' >&2
    exit 1
fi
unset password confirmation
# Keep no password for future boots. This marker prevents a future setup from
# trying the default password against a deliberately customized root account.
printf 'custom root password; do not restore the default\n' > "$state/root-password-custom"
chmod 0600 "$state/root-password-custom"
if ! bash "$here/manual-ssh.sh" --check 0 "$scratch/root-password"; then
    echo 'Root password was changed, but SSH verification failed. Keep this session open and check the error above.' >&2
    exit 1
fi
echo 'ROOT_PASSWORD_VERIFIED: new password applied and actual root SSH login passed; user password unchanged.'
