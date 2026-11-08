#!/usr/bin/env python3
"""Build an optional x86_64 UEFI iPXE menu bootstrap from verified local inputs.

This tool never installs a boot file, changes DHCP, starts a service or selects an OS.
It requires Linux build tools and a clean, pinned upstream iPXE checkout.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from urllib.parse import urlsplit

USB_DRIVERS = ('xhci_driver', 'ehci_driver', 'uhci_driver', 'usbio_driver')


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def mac_address(value):
    if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', value):
        raise ValueError('MAC must have six hexadecimal octets separated by colons')
    value = value.lower()
    if value == '00:00:00:00:00:00' or int(value[:2], 16) & 1:
        raise ValueError('MAC must identify a unicast network adapter')
    return value


def loader_url(value):
    # No shell/iPXE expansion, credentials, query strings or script delimiters.
    if not re.fullmatch(r'https?://[A-Za-z0-9.:-]+/[A-Za-z0-9_./~-]+\.efi', value):
        raise ValueError('loader URL must be an HTTP(S) .efi URL without credentials or query parameters')
    parsed = urlsplit(value)
    if not parsed.hostname or not re.fullmatch(r'[A-Za-z0-9.-]+', parsed.hostname):
        raise ValueError('loader URL requires a DNS name or IPv4 address')
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError('invalid loader port')
    if any(part in ('.', '..') for part in parsed.path.split('/')):
        raise ValueError('loader URL cannot contain dot path segments')
    return value


def render_script(mac, url):
    mac, url = mac_address(mac), loader_url(url)
    lines = ['#!ipxe', 'echo UEFI network menu bootstrap',
             'echo No default operating system or installation is selected.']
    for index in range(32):
        lines.append('iseq ${net%d/mac} %s && set target net%d && goto have_nic ||' % (index, mac, index))
    lines += ['echo Expected network adapter was not found.', 'goto failed',
              ':have_nic', 'echo Using ${target}', 'dhcp ${target} || goto dhcp_failed',
              'imgfree', 'chain ' + url + ' || goto chain_failed', 'goto failed',
              ':dhcp_failed', 'echo DHCP failed on the selected adapter.', 'goto failed',
              ':chain_failed', 'echo Unable to start the network menu.', 'goto failed',
              ':failed', 'ifstat', 'imgstat',
              'echo Stopped. No operating system was selected by this bootstrap.',
              'shell', 'goto failed']
    return '\n'.join(lines) + '\n'


def checked_source(source, commit):
    if not re.fullmatch(r'[0-9a-fA-F]{40}', commit):
        raise ValueError('supply the complete 40-character upstream commit')
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual.lower() != commit.lower():
        raise ValueError('iPXE checkout does not match the requested commit')
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=normal'], text=True)
    if dirty.strip():
        raise ValueError('iPXE checkout must be clean, including local configuration')
    if not (source / 'src/Makefile').is_file():
        raise ValueError('--ipxe-source must point to the upstream repository root')
    # Upstream ignores local headers and creates empty ones during make.
    # A clean git status alone does not establish a stock configuration.
    for local in (source / 'src/config/local').rglob('*.h'):
        if local.stat().st_size:
            raise ValueError('nonempty ignored iPXE local configuration: ' + str(local))
    epoch = int(subprocess.check_output(['git', '-C', str(source), 'show', '-s', '--format=%ct', 'HEAD'], text=True).strip())
    return actual, epoch


def build(args):
    script = render_script(args.mac, args.loader_url)
    source, base, output = (p.resolve() for p in (args.ipxe_source, args.base_iso, args.output))
    if output.exists():
        raise ValueError('output directory already exists; choose a new directory')
    if not re.fullmatch(r'[0-9a-fA-F]{64}', args.base_iso_sha256) or digest(base) != args.base_iso_sha256.lower():
        raise ValueError('base ISO SHA256 mismatch')
    # EMBED is later expanded in upstream Make recipes, not only subprocess argv.
    if any(not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(path)) for path in (source, output)):
        raise ValueError('iPXE make paths must be absolute Linux paths using letters, digits, /, _, . or -')
    for command in ('git', 'make', 'gcc', 'ld', 'objcopy', 'nm', 'xorriso', 'mcopy', 'mdir'):
        if not shutil.which(command):
            raise ValueError('missing build command: ' + command)
    commit, epoch = checked_source(source, args.ipxe_commit)
    src = source / 'src'
    target = 'ipxe-legacy.efi' if args.preserve_firmware_usb else 'ipxe.efi'
    if args.preserve_firmware_usb and 'DRIVERS_ipxe-legacy' not in (src / 'Makefile').read_text():
        raise ValueError('this upstream revision has no official ipxe-legacy target')
    output.mkdir(parents=True)
    script_path = output / 'menu.ipxe'
    script_path.write_bytes(script.encode('ascii'))
    env = dict(os.environ, LC_ALL='C', TZ='UTC', SOURCE_DATE_EPOCH=str(epoch))
    # Do not let inherited make options change the selected build or configs.
    env.pop('MAKEFLAGS', None)
    env.pop('MFLAGS', None)
    log_path = output / 'build.log'

    def run(command, cwd=None, ok=True):
        completed = subprocess.run(list(map(str, command)), cwd=cwd, env=env, capture_output=True, text=True)
        with log_path.open('a', encoding='utf-8') as log:
            log.write('$ ' + ' '.join(map(str, command)) + '\n')
            log.write(completed.stdout + completed.stderr)
        if ok and completed.returncode:
            raise RuntimeError('command failed; inspect ' + str(log_path))
        return completed

    def no_autoexec(esp):
        run(['mdir', '-i', esp, '::/EFI/BOOT'])
        result = run(['mdir', '-i', esp, '::/autoexec.ipxe'], ok=False)
        if result.returncode == 0:
            raise ValueError('FAT autoexec.ipxe must not coexist with an EMBED script')
        if 'not found' not in (result.stdout + result.stderr).lower():
            raise ValueError('could not verify absence of FAT autoexec.ipxe')

    run(['make', '-j', str(args.jobs), 'bin-x86_64-efi/' + target, 'EMBED=' + str(script_path)], cwd=src)
    compiled = src / 'bin-x86_64-efi' / target
    binary = compiled.read_bytes()
    if binary[:2] != b'MZ' or len(binary) < 64:
        raise ValueError('compiled output is not an EFI PE executable')
    pe = struct.unpack_from('<I', binary, 60)[0]
    if binary[pe:pe + 4] != b'PE\0\0' or struct.unpack_from('<H', binary, pe + 4)[0] != 0x8664:
        raise ValueError('compiled EFI output is not x86_64')
    if script.encode('ascii') not in binary:
        raise ValueError('compiled EFI output does not contain the requested EMBED script')
    symbols = run(['nm', src / 'bin-x86_64-efi' / (target + '.tmp')]).stdout
    drivers = {name: bool(re.search(r'\b' + re.escape(name) + r'\b', symbols)) for name in ('intel_driver',) + USB_DRIVERS}
    if args.preserve_firmware_usb and (not drivers['intel_driver'] or any(drivers[name] for name in USB_DRIVERS)):
        raise ValueError('legacy target must retain native Intel PCI networking without USB host drivers')
    efi = output / 'menu-bootstrap.efi'
    shutil.copyfile(compiled, efi)
    os.utime(efi, (epoch, epoch))
    esp = output / 'esp.img'
    run(['xorriso', '-osirrox', 'on', '-indev', base, '-extract', '/esp.img', esp])
    no_autoexec(esp)
    run(['mcopy', '-o', '-m', '-i', esp, efi, '::/EFI/BOOT/BOOTX64.EFI'])
    partial = output / 'menu-bootstrap.iso.partial'
    run(['xorriso', '-indev', base, '-outdev', partial, '-boot_image', 'any', 'replay',
         '-map', esp, '/esp.img', '-volid', 'IPXE-MENU-BOOT', '-commit'])
    verify = output / 'verify'
    verify.mkdir()
    run(['xorriso', '-osirrox', 'on', '-indev', partial, '-extract', '/esp.img', verify / 'esp.img'])
    no_autoexec(verify / 'esp.img')
    run(['mcopy', '-i', verify / 'esp.img', '::/EFI/BOOT/BOOTX64.EFI', verify / 'BOOTX64.EFI'])
    if (verify / 'BOOTX64.EFI').read_bytes() != binary:
        raise ValueError('ISO EFI readback differs from the compiled binary')
    tree = run(['xorriso', '-indev', partial, '-find', '/', '-exec', 'lsdl', '--']).stdout
    if '/autoexec.ipxe' in tree.lower():
        raise ValueError('ISO autoexec.ipxe must not coexist with an EMBED script')
    boot = run(['xorriso', '-indev', partial, '-report_el_torito', 'plain'])
    metadata = boot.stdout + boot.stderr
    if 'UEFI' not in metadata:
        raise ValueError('ISO lacks an El Torito UEFI boot entry')
    (output / 'boot-metadata.txt').write_text(metadata, encoding='utf-8')
    iso = output / 'menu-bootstrap.iso'
    partial.rename(iso)
    manifest = {'schema': 1, 'build_target': target, 'ipxe_commit': commit, 'source_date_epoch': epoch,
                'base_iso_sha256': digest(base), 'preserve_firmware_usb': args.preserve_firmware_usb,
                'mac': mac_address(args.mac), 'loader_url': args.loader_url,
                'script_sha256': digest(script_path), 'efi_sha256': digest(efi), 'iso_sha256': digest(iso),
                'linked_driver_symbols': drivers, 'efi_readback_verified': True, 'autoexec_absent': True,
                'scope': 'Only x86_64 UEFI BOOTX64.EFI is replaced; other original boot paths are unchanged.',
                'hardware_validation': 'Not performed by this build; menu entry, keyboard and installation are separate checks.',
                'built_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return {'iso': str(iso), 'sha256': manifest['iso_sha256'], 'manifest': str(output / 'manifest.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ipxe-source', required=True, type=Path)
    parser.add_argument('--ipxe-commit', required=True)
    parser.add_argument('--base-iso', required=True, type=Path, help='official iPXE ISO containing /esp.img')
    parser.add_argument('--base-iso-sha256', required=True)
    parser.add_argument('--loader-url', required=True, help='native iVentoy UEFI menu loader URL')
    parser.add_argument('--mac', required=True, help='unicast MAC of the adapter allowed to use DHCP')
    parser.add_argument('--output', required=True, type=Path, help='new, non-existing output directory')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--preserve-firmware-usb', action='store_true', help='use official ipxe-legacy.efi: native PCI networking, no USB driver takeover')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 64:
        parser.error('--jobs must be between 1 and 64')
    try:
        print(json.dumps(build(args), indent=2))
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print('UEFI menu bootstrap build failed: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
