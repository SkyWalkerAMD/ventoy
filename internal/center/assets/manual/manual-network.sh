#!/usr/bin/env bash
# Use the supplied conservative planner, then activate ONLY the new interfaces.
set -Eeuo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C SYSTEMD_PAGER=cat
umask 077
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
source "$here/safe-server-init.sh"
mode=${1:---check}
state=/var/lib/ventoy-center/manual-init/network
die() { echo "DHCP: $*" >&2; exit 1; }
[[ $mode == --apply || $mode == --check ]] || exit 2
mkdir -p "$state"
_si_init
_si_python_select
_si_backend
_si_ssh_devices
activate() {
    local nic=$1 target temp filename uuid loaded
    case "$SI_BACKEND" in
        nm)
            uuid=$(nmcli -t -f connection.uuid connection show "safe-dhcp-$nic" | cut -d: -f2-)
            nmcli --wait 45 connection up uuid "$uuid" ifname "$nic";;
        netplan)
            # Generate in isolation. Publish only the new NIC's backend file,
            # avoiding netplan apply and a global NetworkManager reload.
            temp=$(mktemp -d /run/ventoy-netplan.XXXXXXXX) || return 1
            target=$(_si_target "$nic") || { rm -rf "$temp"; return 1; }
            if ! mkdir -p "$temp/etc/netplan" || ! cp -p "$target" "$temp/etc/netplan/"; then rm -rf "$temp"; return 1; fi
            if ! netplan generate --root-dir "$temp"; then rm -rf "$temp"; return 1; fi
            if [[ $SI_RENDERER == networkd ]]; then
                filename=10-netplan-$nic.network
                [[ -f "$temp/run/systemd/network/$filename" ]] || { rm -rf "$temp"; return 1; }
                loaded=$(networkctl --no-pager status "$nic" 2>/dev/null | sed -n 's/^[[:space:]]*Network File: //p') || loaded=
                # A saved, already loaded profile needs no global reload on
                # reruns. In particular, an unplugged secondary NIC must not
                # disturb the DHCP lease used to download setup/software.
                if cmp -s "$temp/run/systemd/network/$filename" "/run/systemd/network/$filename" &&
                   [[ $loaded == "/run/systemd/network/$filename" ]]; then
                    if [[ $(cat "/sys/class/net/$nic/carrier" 2>/dev/null || true) == 1 ]]; then
                        networkctl reconfigure "$nic" || { rm -rf "$temp"; return 1; }
                    fi
                    rm -rf "$temp"; return 0
                fi
                if ! install -d -m 0755 /run/systemd/network ||
                   ! install -m 0644 "$temp/run/systemd/network/$filename" "/run/systemd/network/$filename" ||
                   ! networkctl reload || ! networkctl reconfigure "$nic"; then rm -rf "$temp"; return 1; fi
            else
                filename=netplan-$nic.nmconnection
                [[ -f "$temp/run/NetworkManager/system-connections/$filename" ]] || { rm -rf "$temp"; return 1; }
                if ! install -d -m 0755 /run/NetworkManager/system-connections ||
                   ! install -m 0600 "$temp/run/NetworkManager/system-connections/$filename" "/run/NetworkManager/system-connections/$filename" ||
                   ! nmcli connection load "/run/NetworkManager/system-connections/$filename"; then rm -rf "$temp"; return 1; fi
                uuid=$(sed -n 's/^uuid=//p' "/run/NetworkManager/system-connections/$filename")
                # Load autoconnect now even if link negotiation/cable insertion
                # happens later; an explicit up would time out without carrier.
                if [[ $(cat "/sys/class/net/$nic/carrier" 2>/dev/null || true) == 1 ]]; then
                    if [[ -n $uuid ]]; then nmcli --wait 45 connection up uuid "$uuid" ifname "$nic" || { rm -rf "$temp"; return 1; }
                    else nmcli --wait 45 connection up "netplan-$nic" ifname "$nic" || { rm -rf "$temp"; return 1; }; fi
                fi
            fi
            rm -rf "$temp";;
        networkd) networkctl reload && networkctl reconfigure "$nic";;
        ifupdown|el-ifcfg) timeout 50 ifup "$nic";;
        *) return 1;;
    esac
}
pending=0
if [[ $mode == --check ]]; then
    for item in /sys/class/net/*; do
        nic=${item##*/}; rc=0
        _si_eligible "$nic" || rc=$?
        if ((rc == 0 || rc == 2)); then
            echo "DHCP_CONFIGURATION_PENDING nic=$nic reason=${SI_REASON:-unconfigured interface}"
            pending=1
        fi
    done
fi
if [[ $mode == --apply ]]; then
    # Plan the whole operation before writes using the original eligibility
    # rules. Existing configurations (including inactive ones) are preserved.
    candidates=()
    for item in /sys/class/net/*; do
        nic=${item##*/}; rc=0
        _si_eligible "$nic" || rc=$?
        if ((rc == 0)); then candidates+=("$nic")
        elif ((rc == 2)); then echo "DHCP_REVIEW_REQUIRED nic=$nic reason=$SI_REASON"; pending=1; fi
    done
    if ((${#candidates[@]})); then
        # ISC dhclient provides a per-interface hook for secondary route/DNS
        # isolation. Unknown legacy clients are retained for manual review.
        if [[ $SI_BACKEND == ifupdown || $SI_BACKEND == el-ifcfg ]]; then
            has_network=0; _si_has_existing_network || has_network=$?
            if command -v dhclient >/dev/null && grep -q 'dhclient-enter-hooks.d' /sbin/dhclient-script; then
                hook=/etc/dhcp/dhclient-enter-hooks.d/ventoy-manual-secondary
                [[ ! -L $hook && ( ! -e $hook || -f $hook ) ]] || die 'Unexpected DHCP hook path.'
                mkdir -p /etc/dhcp/dhclient-enter-hooks.d
                # This hook is read only by ISC's client for the named new
                # interfaces; it leaves pre-existing interfaces untouched.
                if [[ -f $hook ]]; then
                    grep -qx '# Managed by Ventoy manual setup' "$hook" || die 'DHCP hook name already in use.'
                else
                    cat > "$hook" <<'HOOK'
# Managed by Ventoy manual setup
if grep -Fxq -- "${interface:-}" /var/lib/ventoy-center/manual-init/network/secondary 2>/dev/null; then
    unset new_routers new_domain_name_servers new_domain_name new_domain_search
    unset new_static_routes new_classless_static_routes new_rfc3442_classless_static_routes
    unset new_ms_classless_static_routes new_ntp_servers new_host_name
fi
HOOK
                    chmod 0644 "$hook"
                fi
                primary=
                if ((has_network == 1)); then
                    primary=${candidates[0]}
                    for nic in "${candidates[@]}"; do
                        [[ $(cat "/sys/class/net/$nic/carrier" 2>/dev/null || true) != 1 ]] || { primary=$nic; break; }
                    done
                elif ((has_network != 0)); then die 'Could not inspect existing network.'; fi
                for nic in "${candidates[@]}"; do
                    [[ $nic == "$primary" ]] || printf '%s\n' "$nic" >> "$state/secondary"
                done
                set-network --allow-legacy-secondary
            elif [[ $SI_BACKEND == ifupdown ]] && command -v dhcpcd >/dev/null; then
                cfg=/etc/dhcpcd.conf
                [[ -f $cfg && ! -L $cfg ]] || die 'dhcpcd.conf must be a regular file.'
                if sed '/^# BEGIN VENTOY DHCP INTERFACE$/,/^# END VENTOY DHCP INTERFACE$/d' "$cfg" | grep -Eq '^[[:space:]]*(interface|profile|ssid|include|static|allowinterfaces|denyinterfaces)[[:space:]]'; then
                    die 'Existing custom dhcpcd device policy requires review; retained.'
                fi
                [[ -e "$state/dhcpcd.conf.before" ]] || cp -p "$cfg" "$state/dhcpcd.conf.before"
                primary=
                if ((has_network == 1)); then
                    primary=${candidates[0]}
                    for nic in "${candidates[@]}"; do
                        [[ $(cat "/sys/class/net/$nic/carrier" 2>/dev/null || true) != 1 ]] || { primary=$nic; break; }
                    done
                elif ((has_network != 0)); then die 'Could not inspect existing network.'; fi
                for nic in "${candidates[@]}"; do
                    # Do not merge into a pre-existing per-device dhcpcd policy.
                    if grep -Eq "^[[:space:]]*interface[[:space:]]+$nic([[:space:]]|$)" "$cfg"; then
                        die "Existing dhcpcd policy for $nic; retained."
                    fi
                    {
                        printf '\n# BEGIN VENTOY DHCP INTERFACE\ninterface %s\nnoipv6\n' "$nic"
                        if [[ $nic != "$primary" ]]; then
                            printf 'nogateway\nnooption routers,static_routes,classless_static_routes,ms_classless_static_routes\nnohook resolv.conf,hostname,timesyncd.conf\nmetric 20000\n'
                        fi
                        printf '# END VENTOY DHCP INTERFACE\n'
                    } >> "$cfg"
                done
                set-network --allow-legacy-secondary
            elif ((has_network == 1)); then
                primary=${candidates[0]}
                for nic in "${candidates[@]}"; do [[ $(cat "/sys/class/net/$nic/carrier" 2>/dev/null || true) != 1 ]] || { primary=$nic; break; }; done
                candidates=("$primary")
                set-network --iface "$primary"
            else
                echo 'DHCP_REVIEW_REQUIRED: legacy secondary interfaces retained to protect existing routes/DNS.'
                pending=1; candidates=()
            fi
        else
            set-network
        fi
        for nic in "${candidates[@]}"; do
            printf '%s\t%s\t%s\n' "$nic" "$(cat "/sys/class/net/$nic/address")" "$SI_BACKEND" >> "$state/managed.tsv"
        done
    fi
    if [[ -f "$state/managed.tsv" ]]; then
        sort -u "$state/managed.tsv" -o "$state/managed.tsv"
        while IFS=$'\t' read -r nic mac backend; do
            [[ -d /sys/class/net/$nic && $(cat "/sys/class/net/$nic/address") == "$mac" ]] || { pending=1; continue; }
            [[ $backend == "$SI_BACKEND" ]] || die 'Network backend changed; review existing managed profiles.'
            # Existing, now working connections must not be bounced on reruns.
            [[ -z $(ip -4 -o addr show dev "$nic" scope global) ]] || continue
            # A newly discovered NIC can be administratively DOWN, in which
            # case carrier cannot be read until it is brought up. Only touch
            # interfaces whose newly created profile is recorded above.
            ip link set dev "$nic" up
            sleep 1
            # networkd must load the new .network even without carrier. Saving
            # YAML alone leaves it unmanaged until a reboot/netplan apply.
            # Netplan's NM backend likewise needs its autoconnect profile loaded.
            if [[ $SI_BACKEND != netplan && $SI_BACKEND != networkd && $(cat "/sys/class/net/$nic/carrier" 2>/dev/null || true) != 1 ]]; then
                echo "DHCP_SAVED_NO_CARRIER nic=$nic"; continue
            fi
            if ! activate "$nic"; then echo "DHCP_ACTIVATION_PENDING nic=$nic"; pending=1; fi
        done < "$state/managed.tsv"
    fi
fi
# Verify persistent managed DHCP plus actual addresses separately. A saved file
# does not prove a lease; connected managed interfaces must obtain IPv4.
if [[ -f "$state/managed.tsv" ]]; then
    while IFS=$'\t' read -r nic mac backend; do
        [[ -d /sys/class/net/$nic && $(cat "/sys/class/net/$nic/address") == "$mac" ]] || { pending=1; continue; }
        case "$backend" in
            nm) [[ $(nmcli -t -f ipv4.method connection show "safe-dhcp-$nic") == ipv4.method:auto ]] || die "$nic persistent DHCP changed.";;
            netplan) grep -q 'dhcp4: true' "$(_si_target "$nic")" || die "$nic persistent DHCP changed.";;
            networkd) grep -qx 'DHCP=ipv4' "$(_si_target "$nic")" || die "$nic persistent DHCP changed.";;
            ifupdown) grep -qx "iface $nic inet dhcp" "$(_si_target "$nic")" || die "$nic persistent DHCP changed.";;
            el-ifcfg) grep -qx 'BOOTPROTO=dhcp' "$(_si_target "$nic")" || die "$nic persistent DHCP changed.";;
        esac
        carrier=$(cat "/sys/class/net/$nic/carrier" 2>/dev/null || true)
        address=$(ip -4 -o addr show dev "$nic" scope global)
        if [[ $mode == --apply && $carrier == 1 && -z $address ]]; then
            for ((i=0;i<15;i++)); do
                sleep 2
                address=$(ip -4 -o addr show dev "$nic" scope global)
                [[ -z $address ]] || break
            done
        fi
        if [[ $carrier == 1 && -z $address ]]; then echo "DHCP_LEASE_PENDING nic=$nic"; pending=1
        elif [[ -n $address ]]; then echo "DHCP_ADDRESS_VERIFIED $address"
        else echo "DHCP_SAVED_NO_CARRIER nic=$nic"; fi
    done < "$state/managed.tsv"
fi
ip -4 -o addr show scope global
[[ -n $(ip -4 -o addr show scope global) ]] || { echo 'NETWORK_PENDING: no usable IPv4 address.'; pending=1; }
((pending == 0)) || exit 3
echo 'NETWORK_VERIFIED: existing configured interfaces retained; new managed DHCP profiles checked.'
