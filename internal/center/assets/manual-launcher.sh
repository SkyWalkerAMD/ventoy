#!/usr/bin/env bash
# Ventoy Center complete manual-install configuration package.
set -Eeuo pipefail
# Keep setup and child-tool diagnostics in English without changing the caller.
setup_locale_set=${LC_ALL+x}
setup_user_locale=${LC_ALL-}
export LC_ALL=C
restore_user_locale() {
    if [[ $setup_locale_set == x ]]; then export LC_ALL="$setup_user_locale"; else unset LC_ALL; fi
}
umask 077
if [[ ${1:-} == --version ]]; then echo 'Ventoy setup @SETUP_VERSION@'; exit 0; fi
if (($# == 0)); then set -- --apply; fi
if [[ ${1:---help} == --help || ${1:-} == -h ]]; then
    echo 'Usage: sudo ./ventoy-linux-setup.run [--hostname NAME] [--offline] [--keep-passwords]'
    echo 'Run after installing and booting Linux. Default credentials: user / ventoy, root / ventoy.'
    echo 'No arguments applies and verifies SSH, hostname, DHCP, kernel locking, disabled automatic updates, and matching software.'
    echo 'Interactive full setup asks for hostname and an optional new root password (twice, hidden); Enter keeps the current value.'
    echo '--apply remains a compatible alias; --offline skips software downloads.'
    echo 'Software only: sudo ./ventoy-linux-setup.run --software'
    echo 'Inspect/verify: --check / --list-software / --check-software'
    echo 'Optional Ubuntu/Debian user + sudo login: --restore-user-login [--login-user user]'
    echo 'This verifies the ordinary user password, then disables root SSH and console password login; --check-login checks the saved policy.'
    echo 'Installation defaults stay root-enabled. A restored user-only choice persists across setup and upgrades.'
    echo 'Upgrade and apply current center setup: --upgrade [--hostname NAME] [--keep-passwords]'
    echo 'Runner version: --version / --check-version. Download only: --update-setup (rerun afterward).'
    exit 0
fi
[[ $EUID == 0 ]] || { echo 'Run with root or sudo.' >&2; exit 1; }
# Validate upgrade options before contacting the center. Offline/check modes
# must never silently turn into an online full setup.
upgrade_args=()
if [[ ${1:-} == --upgrade ]]; then
    shift
    while (($#)); do
        case "$1" in
            --hostname)
                (($# >= 2)) && [[ -n $2 && $2 != -* ]] || { echo '--hostname requires a name.' >&2; exit 2; }
                upgrade_args+=(--hostname "$2"); shift;;
            --keep-passwords) upgrade_args+=(--keep-passwords);;
            *) echo "Unsupported upgrade option: $1 (use --update-setup for download only)." >&2; exit 2;;
        esac
        shift
    done
    set -- --upgrade
fi
hostname_before=$(hostname)
interactive_apply=1
case "${1:-}" in --check|--resume|--software|--list-software|--check-software|--restore-user-login|--check-login) interactive_apply=0;; esac
python=
for candidate in python3 /usr/libexec/platform-python python2 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (2,7) else 1)' 2>/dev/null; then
        python=$candidate; break
    fi
done
[[ -n $python ]] || { echo 'Python >=2.7 is required. Install Python from the OS media, then rerun.' >&2; exit 1; }
stage=$(mktemp -d /var/tmp/ventoy-manual.XXXXXXXX)
trap 'rm -rf -- "$stage"' EXIT
"$python" - "$0" "$stage" '@ARCHIVE_SHA256@' <<'PY'
from __future__ import print_function
import hashlib, io, os, shutil, sys, tarfile
with open(sys.argv[1], 'rb') as f:
    while True:
        line=f.readline()
        if not line: raise ValueError('Missing archive marker')
        if line == b'__VENTOY_MANUAL_ARCHIVE__\n': break
    data=f.read(64*1024*1024+1)
if len(data)>64*1024*1024 or hashlib.sha256(data).hexdigest()!=sys.argv[3]:
    raise ValueError('Package checksum mismatch')
root=sys.argv[2]; total=0; seen=set()
with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
    for member in archive:
        name=member.name
        if (not member.isfile() or not name.startswith('ventoy-manual-setup/')
                or '\\' in name or any(p in ('','.','..') for p in name.split('/'))
                or name in seen or member.size<0 or member.size>64*1024*1024):
            raise ValueError('Unsafe archive member')
        seen.add(name); total+=member.size
        if total>256*1024*1024: raise ValueError('Archive too large')
        target=os.path.join(root,name); parent=os.path.dirname(target)
        if not os.path.isdir(parent): os.makedirs(parent)
        with open(target,'wb') as out: shutil.copyfileobj(archive.extractfile(member),out)
        os.chmod(target,0o755 if name.endswith(('.sh','.run')) else 0o644)
PY
setup_rc=0
echo 'Ventoy setup @SETUP_VERSION@'
case "${1:-}" in
    --check-version|--update-setup)
        (($# == 1)) || { echo 'This action takes no additional arguments.' >&2; exit 2; }
        "$python" "$stage/ventoy-manual-setup/setup-release.py" "$1" "$0"
        exit $?;;
    --upgrade)
        # The updater validates HTTPS trust, length, checksum and destination,
        # retaining the previous runner. A failed download must never apply the
        # old payload. Exec the new file even if it was already downloaded: its
        # configuration/services may not yet have been applied on this node.
        "$python" "$stage/ventoy-manual-setup/setup-release.py" --update-setup "$0"
        runner=$(readlink -f -- "$0")
        rm -rf -- "$stage"
        trap - EXIT
        echo 'SETUP_UPGRADE: applying the verified center runner; existing configured account passwords are retained.'
        restore_user_locale
        exec /bin/bash "$runner" --apply "${upgrade_args[@]}";;
esac
bash "$stage/ventoy-manual-setup/install.sh" "$@" || setup_rc=$?
case "${1:-}" in --restore-user-login|--check-login) exit "$setup_rc";; esac
if (( (setup_rc == 0 || setup_rc == 3 || setup_rc == 4) && interactive_apply)) && [[ -t 0 && -t 1 && -t 2 ]]; then
    # Status 4 means system checks reached the software step, which failed.
    # That independent failure must not hide the optional password dialog.
    password_rc=0
    bash "$stage/ventoy-manual-setup/root-password.sh" || password_rc=$?
    if ((password_rc && setup_rc != 4)); then setup_rc=$password_rc; fi
fi
case "$setup_rc" in
    0) echo 'SETUP_SUMMARY: requested checks completed; see /var/log/ventoy-manual-init.log and /var/lib/ventoy-center/software/last-result.json';;
    3) echo 'SETUP_SUMMARY: pending DHCP/driver reboot/firmware; use --check after resolving the pending item';;
    4) echo 'SETUP_SUMMARY: software failed. Review pending system checks above; retry --software after fixing the reported package error';;
    *) echo "SETUP_SUMMARY: incomplete (exit $setup_rc). Inspect the first failed stage before retrying";;
esac
# Return control to the original login. A nested shell would keep both setup
# and a local console session open while waiting for a second exit.
if (((setup_rc == 0 || setup_rc == 3 || setup_rc == 4) && interactive_apply)) && [[ -t 0 && -t 1 && -t 2 ]]; then
    if hostname_after=$(hostname) && [[ "$hostname_before" != "$hostname_after" ]]; then
        echo "HOSTNAME_VERIFIED: $hostname_after. To refresh a cached Bash prompt, run exec bash in your current shell."
    fi
fi
exit "$setup_rc"
__VENTOY_MANUAL_ARCHIVE__
