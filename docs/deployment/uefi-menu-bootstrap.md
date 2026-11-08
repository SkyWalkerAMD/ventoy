# Optional UEFI menu bootstrap

`tools/uefi-menu-bootstrap/build.py` builds a separate iPXE ISO for machines that
need a native PCIe network driver before entering the existing iVentoy menu. It
does not replace server boot files, change DHCP or select an operating system.
The MAC and menu-loader URL are supplied when building; no site-specific values
or credentials belong in the repository.

The optional `--preserve-firmware-usb` flag selects upstream `ipxe-legacy.efi`.
Despite its name, this is an **x86_64 UEFI** application. It retains native PCI
network drivers but omits USB drivers, allowing firmware to keep handling USB
keyboards and BMC-emulated input. Do not use this variant for a network adapter
that requires iPXE's native USB drivers. Without the flag, the tool builds full
`ipxe.efi`.

Upstream documents the AMI USB input problem and recommends the no-USB target in
[iPXE issue #1643](https://github.com/ipxe/ipxe/issues/1643). Enabling iPXE's own
USB keyboard driver alone does not establish that keyboard input survives a
subsequent chain to another EFI application.

## Build

Use Linux with Python 3.8 or newer, Git, Make, GCC/binutils, xorriso and mtools. Provide a clean
local checkout of the [official iPXE source](https://github.com/ipxe/ipxe) and an
official iPXE ISO containing `/esp.img`. Obtain and review these inputs separately;
the build tool does not fetch code or install dependencies.

```sh
python3 tools/uefi-menu-bootstrap/build.py \
  --ipxe-source /path/to/ipxe \
  --ipxe-commit FULL_REVIEWED_40_CHARACTER_COMMIT \
  --base-iso /path/to/official-ipxe.iso \
  --base-iso-sha256 REVIEWED_64_CHARACTER_SHA256 \
  --loader-url http://pxe.example.test:16000/hboot/loader/iventoy_loader_uefi.efi \
  --mac 02:00:00:00:00:01 \
  --preserve-firmware-usb \
  --output /path/to/new-build-directory
```

The output directory must not exist. Source and output paths may contain only
ASCII letters, digits, `/`, `_`, `.` and `-`, because upstream Make expands the
embedded-script path. Local source changes, nonempty ignored local headers,
a mismatched commit/hash and invalid MAC/URL values stop the build.
HTTP(S) URLs must not contain credentials, queries or iPXE variable expansion.
HTTPS continues to use iPXE's existing certificate validation; this tool does not
disable it.

The embedded script looks for the specified MAC among `net0` through `net31`,
requests DHCP only on that adapter, discards unused images, and chains the menu
loader. A missing adapter or network error stops in the iPXE shell. There is no
default operating system in the script. The existing iVentoy menu's own settings
still apply after the chain succeeds.

Only the ISO's x86_64 UEFI `BOOTX64.EFI` is replaced. Other original boot paths are
unchanged. Do not combine this embedded script with a FAT/ISO `autoexec.ipxe`;
an unused second script can enter Linux's synthetic initrd. The builder rejects
that combination and checks the completed ISO, not only its staging files.

Outputs include `menu-bootstrap.iso`, `menu-bootstrap.efi`, `menu.ipxe`,
`manifest.json`, `boot-metadata.txt` and a build log. The manifest records source
commit, input and output hashes, build mode, embedded-script hash and linked
driver symbols. The build uses the source commit's timestamp via
`SOURCE_DATE_EPOCH`; filesystem-image metadata and toolchain versions can still
affect byte-for-byte output. Retain the manifest alongside the actual ISO.
These generated files and site-specific arguments should remain outside Git.

## Validation boundaries

Run the network-free input/refusal checks with:

```sh
python3 scripts/validate_uefi_menu_bootstrap.py
```

A native build verifies the x86_64 EFI image, embedded script, absence of a second
autoexec script, El Torito UEFI entry and exact EFI readback from the completed
ISO. The no-USB variant additionally checks native Intel networking remains
linked and xHCI/EHCI/UHCI/USBIO driver symbols are absent. It never boots a machine
or writes a client disk.

On 2026-11-08, a Z790 HERO with PCIe I350 reached the native iVentoy 1.0.49 menu
through site-specific full and no-USB diagnostic ISOs from upstream commit
`a040f95796505c86619905eb27758aebd6b0ab87`. With the same embedded script, BMC
keyboard navigation failed in the full variant and worked with `ipxe-legacy.efi`.
The physically tested no-USB ISO was `ipxe-bmc15-menu-legacy.iso`, SHA256
`9e5d823a9961c1c35b519b49c0e7e27b5f2fcff6bbeb300010da48fcb845a24c`.

That diagnostic ISO subsequently completed an Ubuntu 24.04.3 manual installation
through the native iVentoy manual entry. A normal reboot reached the local tty1
login prompt. I350 DHCP worked, kernel `6.8.0-71-generic` remained held, and APT
automatic-update and unattended-upgrade services were masked. The preloaded setup
matched alpha57; there were no failed systemd services or Ventoy login banner.
The manual installation initially left root locked. After explicitly running
setup in offline mode with a hostname, its local root/user SSH checks passed and
a separate root SSH connection succeeded.

Repeated tests later that day did not reproduce reliable installer startup. Two
automatic-entry attempts (`auto:1`) and a subsequent manual-entry attempt
(`auto:0`) stopped after approximately 0.65 seconds of kernel output. Adding
`nomodeset` did not resolve the stall. A controlled test of GrubBoot (mode 2)
reported `out of memory` and then a black screen; VtoyBoot (mode 0) was restored.
The installed SSD system continued to boot successfully across repeated local
reboots. The automatic attempts did not reach disk writes.

The subsequent GRUB console A/B isolated an allocation failure in Ubuntu's TPM
verifier: the identical initrd loaded after unloading that GRUB module. The
[optional Ubuntu compatibility entry](ubuntu-uefi-low-memory.md) implements this
explicit choice without changing firmware TPM settings. It subsequently passed
an Ubuntu 24.04.3 automatic installation and hard-disk startup on the same Z790
machine; see the [dated acceptance record](../development/z790-ubuntu-2026-11-08.md)
for the exact artifact and scope. The bootstrap and the GRUB compatibility
choice address different stages of the boot chain.

The generic builder in this directory has separately passed input/refusal tests
and native artifact checks for both build modes. Its generated ISOs have not yet
been booted on hardware; the physical results belong to the site-specific
diagnostic ISO. They do not prove that the original firmware PXE path is fixed,
cover every Linux image, or exercise I226-V networking.
