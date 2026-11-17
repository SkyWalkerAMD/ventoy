# ASPEED installation display compatibility

AST2500 and AST2600 are BMC graphics controllers. A blank remote console while
the installer starts can be caused by a kernel modesetting transition. It is
different from a GRUB `can't allocate initrd` error, a network driver failure,
or an installer crash. The correct kernel argument is `nomodeset`.

The Linux installation media can enable `nomodeset` on existing installer boot
commands with `tools/linux-bmc-display/build.py`. It changes the shared ISO used
by manual and automatic installation; changing only an automatic-install
preload would run too late to protect early display initialization.

The builder covers GRUB `linux`, `linuxefi` and `linux16` commands, and Syslinux
installer `append` lines. It also checks the separate FAT EFI boot image and
updates any installer menu stored there. Existing basic-graphics entries remain
unchanged when they already contain the argument. Kernel paths, initrd paths,
installation arguments, menu order, defaults and the Ubuntu TPM compatibility
entry remain intact. Windows and memory-test media are outside this tool's scope.

`nomodeset` keeps the firmware display instead of enabling accelerated kernel
graphics. This is a compatibility default for installation on BMC consoles;
it is not automatic detection of an ASPEED PCI device. To test native graphics
for one boot, remove the argument with GRUB **e**, or Syslinux **Tab**, before
starting the selected installer. A machine that needs accelerated desktop
graphics may require a different policy after installation.

For Debian/Ubuntu the inserted argument precedes `---` or `--`, rather than
requesting it as an additional installed-system boot option. Other installers
may carry boot arguments into the installed system. Check the installed
`/proc/cmdline` before changing its display policy; the builder does not edit
the installed system's GRUB configuration.

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

The output directory must not already exist. Sources are never modified. The
initial candidate is a reflink, not a hard link. For inspected GRUB hybrid media
whose appended EFI partition prevents growth, `--allow-full-repack` permits an
explicit full rebuild after a free-space check. Failure leaves private evidence
and never publishes a partial image.

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
