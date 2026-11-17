#!/bin/sh
# Installer completion hook: stage the package, never execute it.
set -eu
src=${0%/*}
[ "$src" != "$0" ] || src=.
src=$(CDPATH= cd -- "$src" && pwd)
target=${1:-${TARGET_MOUNT_POINT:-/target}}
[ "$target" != / ] && [ -d "$target" ] && [ -f "$target/etc/os-release" ] || {
    echo 'Ventoy preload: installed target root is missing' >&2; exit 1;
}
target=$(readlink -f "$target")
[ "$target" != / ] || exit 1
# No symlink in the destination may redirect a write outside the target.
for dir in "$target/root" "$target/var" "$target/var/lib" "$target/var/lib/ventoy-center"; do
    [ ! -L "$dir" ] || { echo "Ventoy preload: unsafe directory $dir" >&2; exit 1; }
done
cd "$src"
sha256sum -c setup.sha256 || exit 1
mkdir -p "$target/root" "$target/var/lib/ventoy-center"
dest=$target/root/ventoy-linux-setup.run
status=$target/var/lib/ventoy-center/manual-setup-preloaded
[ ! -L "$status" ] || exit 1
if [ -e "$dest" ] || [ -L "$dest" ]; then
    [ -f "$dest" ] && [ ! -L "$dest" ] || {
        echo 'Ventoy preload: existing setup differs; retained' >&2; exit 1;
    }
    if ! cmp -s ventoy-linux-setup.run "$dest"; then
        # A baked ISO can contain an older, still inert managed preload. Only
        # replace it when both ownership records match its actual contents and
        # setup has never been applied. Preserve custom/unmarked files.
        previous=$(sha256sum "$dest" | cut -d ' ' -f 1)
        record=$target/root/ventoy-linux-setup.run.sha256
        [ -f "$status" ] && [ "$(head -n 1 "$status")" = PRELOADED_ONLY ] &&
            grep -Fxq "sha256=$previous" "$status" &&
            [ -f "$record" ] && [ ! -L "$record" ] &&
            [ "$(cat "$record")" = "$previous  ventoy-linux-setup.run" ] &&
            [ ! -e "$target/var/lib/ventoy-center/manual-init" ] &&
            [ ! -L "$target/var/lib/ventoy-center/manual-init" ] || {
                echo 'Ventoy preload: existing setup differs; retained' >&2; exit 1;
            }
        backup=$dest.preload-backup.$previous
        [ ! -e "$backup" ] && [ ! -L "$backup" ] || exit 1
        ln "$dest" "$backup"
        tmp=$(mktemp "$target/root/.ventoy-setup.XXXXXX")
        trap 'rm -f "$tmp"' EXIT HUP INT TERM
        cp ventoy-linux-setup.run "$tmp"
        chmod 0700 "$tmp"
        mv -f "$tmp" "$dest"
        trap - EXIT HUP INT TERM
        cp setup.sha256 "$record"
        chmod 0600 "$record"
        echo 'Ventoy preload: refreshed unused managed setup; previous copy retained.'
    fi
else
    tmp=$(mktemp "$target/root/.ventoy-setup.XXXXXX")
    trap 'rm -f "$tmp"' EXIT HUP INT TERM
    cp ventoy-linux-setup.run "$tmp"
    chmod 0700 "$tmp"
    # Publish without overwriting an existing file, including a concurrent one.
    ln "$tmp" "$dest"
    rm -f "$tmp"
    trap - EXIT HUP INT TERM
fi
[ "$(sha256sum "$dest" | cut -d ' ' -f 1)" = "$(cut -d ' ' -f 1 setup.sha256)" ]
for name in README-ventoy-setup.txt README-ventoy-software.txt ventoy-linux-setup.run.sha256; do
    [ ! -e "$target/root/$name" ] && [ ! -L "$target/root/$name" ] || continue
    case "$name" in
        README-ventoy-software.txt) cp software-README.txt "$target/root/$name" ;;
        README-ventoy-setup.txt) cp README.txt "$target/root/$name" ;;
        *) cp setup.sha256 "$target/root/$name" ;;
    esac
    chmod 0600 "$target/root/$name"
done
printf '%s\n' 'PRELOADED_ONLY' "sha256=$(cut -d ' ' -f 1 setup.sha256)" \
    'run=sudo /root/ventoy-linux-setup.run' \
    'software=sudo /root/ventoy-linux-setup.run --software' > "$status"
chmod 0600 "$status"
/bin/sh "$src/target-update-policy.sh" "$target"
/bin/sh "$src/bmc-display-target.sh" "$target"
/bin/sh "$src/support-cache.sh" "$target"
/bin/sh "$src/support-install.sh" "$target"
echo 'Ventoy setup preloaded; run it after installation for SSH, DHCP and software.'
# Only the live installer's read-only ISO shutdown is prepared. This helper
# skips non-Casper installers and never applies the staged target setup.
/bin/sh "$src/ubuntu-reboot.sh"
