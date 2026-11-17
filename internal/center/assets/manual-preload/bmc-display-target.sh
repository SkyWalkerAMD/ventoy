#!/bin/sh
# The installer command line carries the choice. Ordinary boots do no work.
set -eu
set -f
mode=
for arg in $(cat /proc/cmdline); do
    case "$arg" in
        ventoy.bmc=install|ventoy.bmc=installed)
            [ -z "$mode" ] || { echo 'Conflicting AST/BMC display choices' >&2; exit 1; }
            mode=${arg#*=}
            ;;
    esac
done
[ -n "$mode" ] || exit 0

target=$(readlink -f "${1:?target root required}")
[ "$target" != / ] && [ -f "$target/etc/os-release" ] || exit 1
# Release only mounts made here. Installers sometimes already mount these.
mounted=
trap 'for path in $mounted; do umount "$target/$path"; done' EXIT
trap 'exit 1' HUP INT TERM
for path in dev proc sys; do
    [ -d "$target/$path" ] && [ ! -L "$target/$path" ] || exit 1
    if ! awk -v dir="$target/$path" '$2 == dir { found=1 } END { exit !found }' /proc/mounts; then
        mount -o bind "/$path" "$target/$path"
        mounted="$path $mounted"
    fi
done

chroot "$target" /bin/sh -s -- "$mode" <<'VCBMC'
set -eu
mode=$1
# grubby handles legacy grub.cfg and the newer BLS entries on EL.
if command -v grubby >/dev/null 2>&1; then
    if [ "$mode" = installed ]; then
        grubby --update-kernel=ALL --args=nomodeset
    else
        grubby --update-kernel=ALL --remove-args=nomodeset
    fi
    grubby --info=ALL | awk -F'"' -v keep="$mode" '
        /^args=/ {
            count++
            have = ($2 ~ /(^|[[:space:]])nomodeset([[:space:]]|$)/)
            if (have != (keep == "installed")) bad=1
        }
        END { exit (bad || !count) }'
    exit
fi

# Debian and Ubuntu can copy live parameters into their GRUB defaults.
# Remove only the standalone token from installer-generated assignments.
[ ! -L /etc/default/grub.d ] && [ -d /etc/default ] || exit 1
mkdir -p /etc/default/grub.d
dest=/etc/default/grub.d/zz-ventoy-bmc-display.cfg
tmp=
trap '[ -z "$tmp" ] || rm -f "$tmp"' EXIT
for path in /etc/default/grub /etc/default/grub.d/*.cfg; do
    [ "$path" != "$dest" ] && [ -f "$path" ] || continue
    [ ! -L "$path" ] || continue
    tmp=$(mktemp "$path.ventoy.XXXXXX")
    cp -p "$path" "$tmp"
    sed -E "/^[[:space:]]*(export[[:space:]]+)?GRUB_CMDLINE_LINUX(_DEFAULT)?=/ {
        :again
        s/([[:space:]\"'])nomodeset([[:space:]\"']|$)/\1\2/
        t again
    }" "$path" > "$tmp"
    if cmp -s "$path" "$tmp"; then rm -f "$tmp"; else mv -f "$tmp" "$path"; fi
    tmp=
done
[ ! -L "$dest" ] || exit 1
if [ -f "$dest" ]; then
    grep -Fxq '# Managed by the Ventoy AST/BMC installer choice.' "$dest" || exit 1
fi
if [ "$mode" = installed ]; then
    tmp=$(mktemp /etc/default/grub.d/.ventoy-bmc.XXXXXX)
    printf '%s\n' '# Managed by the Ventoy AST/BMC installer choice.' \
        'GRUB_CMDLINE_LINUX="${GRUB_CMDLINE_LINUX:+$GRUB_CMDLINE_LINUX }nomodeset"' > "$tmp"
    chmod 0644 "$tmp"
    mv -f "$tmp" "$dest"
    tmp=
else
    rm -f "$dest"
fi
if [ -f /boot/grub/grub.cfg ]; then
    update-grub
    awk -v keep="$mode" '
        $1 ~ /^linux(efi|16)?$/ && $2 ~ /(^|\/)vmlinuz([-_.]|$)/ {
            count++
            have=0
            for (i=3; i<=NF; i++) if ($i == "nomodeset") have=1
            if (have != (keep == "installed")) bad=1
        }
        END { exit (bad || !count) }' /boot/grub/grub.cfg
fi
VCBMC
echo "Ventoy AST/BMC display policy applied: $mode"
