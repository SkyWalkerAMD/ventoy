# ASPEED installation display compatibility

AST2500 and AST2600 are BMC graphics controllers. A blank remote console while
the installer starts can be caused by a kernel modesetting transition. It is
different from a GRUB `can't allocate initrd` error, a network driver failure,
or an installer crash. The correct kernel argument is `nomodeset`.

After choosing manual or automatic installation in iVentoy, use the regular
installer entry for normal graphics. Select **AST/BMC display compatibility
(install only)** if the BMC console goes blank. Select **AST/BMC display
compatibility (keep after install)** when the installed system also needs the
firmware display. Narrow menus shorten these labels to **AST/BMC (install
only)** and **AST/BMC (keep after install)**. Both choices use `nomodeset`
while starting the installer.
Use a matching Ventoy Center preload to apply the selected policy before the
installed system boots.

The builder covers GRUB `linux`, `linuxefi` and `linux16` commands in both
`/boot/grub` and `/boot/grub2`, EFI menus, and Syslinux
installer `append` lines. It also checks the separate FAT EFI boot image and
updates any installer menu stored there. The two choices use the standard
installer kernel and initrd. Debian uses its text installer for these choices.
Existing entries and their order, including the distribution's safe graphics
and Ubuntu's TPM compatibility entries, are preserved.

`nomodeset` keeps the firmware display and disables native display modesetting.
Select compatibility based on what happens on the console. The installer
completion hook removes inherited `nomodeset` for **install only** and ensures
it is present for **keep after install**. Verify the installed system's
`/proc/cmdline` after reboot.

## Build and verification

Run on an isolated Linux build host with Python 3, xorriso, GNU cp with reflink
support, mtools, and a GRUB syntax checker. Enterprise Linux media additionally
requires `implantisomd5` and `checkisomd5`.

```sh
python3 scripts/validate_bmc_display.py
python3 tools/linux-bmc-display/build.py \
  --source /srv/media/linux-original.iso \
  --source-sha256 EXPECTED_SHA256 \
  --output /srv/staging/linux-bmc-display
```

The output directory must not already exist. Use source media from before the
global `nomodeset` change. Verified rollback originals can be used when
replacing a previously published image. The matching production preloads must
include `bmc-display-target.sh`.

The initial candidate is a reflink. For inspected GRUB hybrid media
whose appended EFI partition prevents growth, `--allow-full-repack` permits an
explicit full rebuild after a free-space check. Failure leaves private evidence
and never publishes a partial image.

For the recognized hidden-BIOS/visible-EFI hybrid layout, a replay failure can
instead use xorriso's `keep` mode on a fresh reflink. It verifies the original
system area and hidden BIOS bytes before updating only the validated ISOLINUX
boot-info table's PVD reference. Otherwise a loader from a previous ISO session
would continue to read old menus. The payload checksum stays unchanged.
This preserves the existing
partition geometry while appending the ISO session; it does not repair or
expand an existing hybrid partition table. BIOS and UEFI boot checks are
required before publishing such a candidate.

The builder verifies GRUB syntax, changed-file readback, media checksums, the
ISO file inventory, volume label, El Torito boot loading parameters, EFI extent,
EFI executable contents and retained kernel/initrd/driver files. It records
source and candidate SHA-256 values in `result.json`. Publication still requires
an idle PXE service, a rollback copy, matching preparation source metadata and
verification that native image/script bindings remain unchanged.

Successful image construction is not physical AST2500/AST2600 acceptance. Test
both manual and automatic installation on the affected BMC, including installer
display and the reboot into the installed system. Record hardware acceptance
separately from syntax, checksum and virtual-machine checks.

References: [Linux kernel parameters](https://docs.kernel.org/admin-guide/kernel-parameters.html),
[Debian installer boot parameters](https://www.debian.org/releases/stable/amd64/ch05s03.en.html).
