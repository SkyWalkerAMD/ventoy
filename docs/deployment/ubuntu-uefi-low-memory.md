# Optional Ubuntu 24.04.3 UEFI low-memory entry

This compatibility entry is limited to the Ubuntu Server 24.04.3 amd64 GA
kernel and the inspected `2.12-1ubuntu7.3` GRUB EFI binary. It is not an I226-V
driver fix or a general Intel/AMD compatibility switch.

On the Z790 HERO / 14900KS test machine, the same iVentoy-generated initrd
loaded through native iPXE. In the Ubuntu GRUB console, `initrd` instead failed
with `out of memory` immediately after `trying verifier tpm`. Unloading only
GRUB's `tpm` module and retrying the identical `initrd` command succeeded and
booted to the diagnostic initramfs shell. These observations locate this
failure in the GRUB loading/measurement path. They do not establish that every
firmware memory-allocation failure has the same cause.

The TPM verifier requests a whole-file buffer, which can exhaust GRUB's
available heap despite substantial total machine RAM. The relevant upstream
code is [the verifier allocation](https://github.com/rhboot/grub2/blob/grub-2.12/grub-core/kern/verifiers.c)
and [the TPM module](https://github.com/rhboot/grub2/blob/grub-2.12/grub-core/commands/tpm.c).

## Behavior

The builder appends this UEFI-only menu item after the existing items:

`Ubuntu Server (low-memory compatibility; skips GRUB TPM measurement)`

Selecting it unloads GRUB's TPM verifier for that boot and then uses the
original GA kernel/initrd commands and arguments. The normal entries,
indices, timeout, default selection, HWE entry and firmware TPM settings
remain unchanged. The compatibility path does not provide the normal GRUB
TPM measurements; do not select it when measured-boot policy requires them.
It does not disable Secure Boot verification or change TPM firmware settings.
The observed physical test used Secure Boot disabled; other configurations
have not been accepted by this test.

If unloading or loading fails, the entry returns to UEFI without implicitly
booting a kernel that lacks its initrd. After a failed compatibility load it
attempts to restore the GRUB TPM module before returning. The standard ISO
already provides the same `exit 1` UEFI return command.

The entry lives inside the existing canonical ISO. iVentoy's earlier
manual/automatic script selection, runtime injection and script binding stay
in place. The compatibility item itself does not select an installation
script, disk, filesystem or unattended mode.

## Isolated build and publication

Use Linux with `xorriso`, GNU `cp`, and `grub-script-check` (or
`grub2-script-check`). Supply the SHA-256 of the reviewed current canonical ISO:

```bash
python3 tools/ubuntu-uefi-compat/build.py \
  --source /path/to/ubuntu-24.04.3-live-server-amd64.iso \
  --source-sha256 REVIEWED_SOURCE_SHA256 \
  --output /path/outside/live-iso-inventory/new-candidate
```

The output directory must be new. The builder first requires a reflink clone
and attempts to append only the GRUB menu and its existing media checksum.
Some Ubuntu images have a hidden appended EFI partition that prevents growing
the ISO without overlapping GPT entries. With explicit `--allow-full-repack`,
that specific failure permits a temporary complete candidate using the
original boot metadata and files. The builder records which mode it used and
requires enough free space; it never silently selects this fallback. Do not
use `-boot_image any keep` to hide the error, because stale BIOS/GPT metadata
does not meet the preservation checks. An unsupported release, GRUB binary,
menu or checksum fails closed. No path publishes an entry, modifies the
source or restarts iVentoy.

Before reporting `built-not-published`, it checks GRUB syntax, source identity
and hash, preservation of all original menu bytes, unchanged GA/HWE kernels
and initrds, unchanged visible EFI executables and complete hidden EFI boot
image, the volume label and El Torito loading parameters. Sector locations may
move when xorriso replays boot metadata; the boot parameters may not change.
`result.json` records the candidate hash and these checks.

Publish only after clients have left their installation media. Keep the
current rollback, replace the **same canonical ISO**, regenerate its prepared
entry metadata, and refresh through the normal release process. Do not add a
second public ISO or replace media after preparing release metadata. On the
client, choose the normal iVentoy manual/automatic script, then this optional
GRUB entry when needed.

## Validation boundary

Run the pure editor/refusal tests with:

```bash
python3 scripts/validate_ubuntu_uefi_compat.py
```

The builder's checks are static and do not claim a successful installation.
The console A/B reached an initramfs shell. Before recording hardware
acceptance, check that the normal default entry is preserved and perform a
compatibility-entry unattended install with injection, disk policy and
hard-disk reboot checked on the affected machine. Publishing a candidate for
this controlled test does not itself establish hardware acceptance. Keep the
results with the deployment record for that candidate hash; a later rebuild
does not inherit physical acceptance.

The normal default path still uses GRUB's TPM verifier. On the affected
firmware, select the explicitly named compatibility item; preserving the
default does not mean that its known allocation failure has been fixed.
No other Ubuntu release, HWE kernel or Linux distribution is covered.
