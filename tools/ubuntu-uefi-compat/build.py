#!/usr/bin/env python3
"""Build, but never publish, an opt-in Ubuntu 24.04.3 UEFI compatibility menu.

Only GRUB's TPM measurement is skipped, only after selecting the new entry.
The source ISO, normal menu, kernel, initrd and EFI loaders are preserved.
Linux, xorriso, GNU cp with reflink support and grub-script-check are required.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

MARKER = '# ventoy-ubuntu24043-uefi-low-memory-v1'
MENU_ID = 'ubuntu24043-uefi-low-memory'
MENU_TITLE = 'Ubuntu Server (low-memory compatibility; skips GRUB TPM measurement)'
VOLUME_ID = 'Ubuntu-Server 24.04.3 LTS amd64'
GRUB_SHA256 = '52b8b3503d3efabfac8793f07e1db5d22c51d90ebb5b6319962fab5d02f49956'
GRUB_CONFIG = '/boot/grub/grub.cfg'
BOOT_FILES = ('/casper/vmlinuz', '/casper/initrd', '/casper/hwe-vmlinuz',
              '/casper/hwe-initrd', '/EFI/boot/bootx64.efi',
              '/EFI/boot/grubx64.efi', '/EFI/boot/mmx64.efi')
GA_ENTRY = ('menuentry "Try or Install Ubuntu Server" {\n'
            '\tset gfxpayload=keep\n'
            '\tlinux\t/casper/vmlinuz  ---\n'
            '\tinitrd\t/casper/initrd\n}\n')


def digest(path, algorithm='sha256'):
    value = hashlib.new(algorithm)
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def compatibility_entry():
    # Explicit boot and exit guards matter: GRUB otherwise implicitly boots a
    # loaded kernel even after some failed script commands (e.g. missing initrd).
    # exit 1 is Ubuntu's existing UEFI "Boot from next volume" command.
    return (MARKER + '\n'
            'if [ "$grub_platform" = "efi" ]; then\n'
            'menuentry "' + MENU_TITLE + '" --id ' + MENU_ID + ' {\n'
            '    echo "Compatibility mode: GRUB TPM measurement is skipped for this boot."\n'
            '    echo "Firmware TPM settings and normal boot entries are unchanged."\n'
            '    if rmmod tpm; then\n'
            '\tset gfxpayload=keep\n'
            '\tlinux\t/casper/vmlinuz  ---\n'
            '        if [ "$?" = "0" ]; then\n'
            '\tinitrd\t/casper/initrd\n'
            '            if [ "$?" = "0" ]; then\n'
            '                boot\n'
            '            fi\n'
            '        fi\n'
            '        insmod tpm\n'
            '        echo "Compatibility boot failed. Returning to UEFI without starting installation."\n'
            '    else\n'
            '        echo "Cannot unload GRUB TPM module. Returning to UEFI without starting installation."\n'
            '    fi\n'
            '    sleep --interruptible 10\n'
            '    exit 1\n'
            '}\n'
            'fi\n')


def patch_config(original):
    text = original.decode('utf-8')
    if MARKER in text or MENU_ID in text:
        raise ValueError('compatibility entry is already present')
    if '\r' in text or not text.endswith('\n'):
        raise ValueError('unexpected GRUB line endings')
    if text.count(GA_ENTRY) != 1 or not text.startswith('set timeout=30\n'):
        raise ValueError('unsupported Ubuntu GA menu; review instead of guessing')
    # Refuse a changed loader/default policy. This tool is intentionally not a
    # generic GRUB editor. It appends, preserving all existing bytes and indices.
    if re.search(r'(?m)^\s*(?:set\s+(?:default|fallback)|rmmod|insmod\s+tpm|source|configfile)\b', text):
        raise ValueError('unsupported GRUB boot policy')
    if text.count('menuentry ') != 5 or text.count('linux\t/casper/') != 2:
        raise ValueError('unsupported Ubuntu menu layout')
    return original + b'\n' + compatibility_entry().encode('ascii')


def patch_md5(original, before, after):
    result, count = [], 0
    old_hash, new_hash = hashlib.md5(before).hexdigest(), hashlib.md5(after).hexdigest()
    for line in original.decode('ascii').splitlines(keepends=True):
        match = re.fullmatch(r'([0-9a-fA-F]{32})([ \t]+)(\*?)(\./)?boot/grub/grub\.cfg(\n?)', line)
        if match:
            if match[1].lower() != old_hash:
                raise ValueError('original grub.cfg media checksum does not match')
            line = new_hash + line[32:]
            count += 1
        result.append(line)
    if count != 1:
        raise ValueError('expected one grub.cfg entry in md5sum.txt')
    return ''.join(result).encode('ascii')


def boot_signature(report):
    """Keep all El Torito loading parameters; only sector locations may move."""
    images, paths, options = [], [], []
    for line in report.splitlines():
        if line.startswith('El Torito boot img :'):
            row = line.split(':', 1)[1].split()
            if len(row) != 8:
                raise ValueError('unrecognized El Torito image record')
            images.append(row[:-1])
        elif line.startswith('El Torito img path :'):
            paths.append(line.split(':', 1)[1].split())
        elif line.startswith('El Torito img opts :'):
            options.append(line.split(':', 1)[1].split())
    if len(images) != 2 or [r[1] for r in images] != ['BIOS', 'UEFI']:
        raise ValueError('expected Ubuntu BIOS and UEFI boot images')
    return {'images': images, 'paths': paths, 'options': options}


def efi_image_bytes(iso, report):
    rows = [line.split(':', 1)[1].split() for line in report.splitlines()
            if line.startswith('El Torito boot img :')]
    rows = [row for row in rows if len(row) == 8 and row[1] == 'UEFI']
    if len(rows) != 1:
        raise ValueError('expected one UEFI boot image')
    size, offset = int(rows[0][6]) * 512, int(rows[0][7]) * 2048
    if not 512 <= size <= 64 * 1024 * 1024 or offset + size > Path(iso).stat().st_size:
        raise ValueError('invalid UEFI boot image extent')
    with Path(iso).open('rb') as source:
        source.seek(offset)
        data = source.read(size)
    if len(data) != size:
        raise ValueError('short UEFI boot image read')
    return data


def efi_image_hash(iso, report):
    return hashlib.sha256(efi_image_bytes(iso, report)).hexdigest()


def repack_boot_args(source, report, efi_path):
    """Reproduce the inspected hybrid layout without xorriso 1.5.4's EFI omission."""
    signature = boot_signature(report)
    expected = {'images': [['1', 'BIOS', 'y', 'none', '0x0000', '0x00', '4'],
                           ['2', 'UEFI', 'y', 'none', '0x0000', '0x00', '10160']],
                'paths': [['1', '/boot/grub/i386-pc/eltorito.img']],
                'options': [['1', 'boot-info-table', 'grub2-boot-info']]}
    if signature != expected:
        raise ValueError('unreviewed hybrid boot layout; cannot explicitly repack')
    date = re.search(r'(?m)^Creation Time:\s+([0-9]{16})$', report)
    if not date:
        raise ValueError('missing ISO creation timestamp')
    return ['-boot_image', 'any', 'discard', '-volume_date', 'uuid', date[1],
            '-boot_image', 'grub', 'grub2_mbr=--interval:imported_iso:0s-15s:zero_mbrpt,zero_gpt:' + str(source),
            '-boot_image', 'any', 'partition_table=on',
            '-boot_image', 'any', 'partition_cyl_align=off',
            '-boot_image', 'any', 'partition_offset=0',
            '-boot_image', 'any', 'mbr_force_bootable=on',
            '-append_partition', '2', '0xef', str(efi_path),
            '-boot_image', 'any', 'appended_part_as=gpt',
            '-boot_image', 'any', 'cat_path=/boot.catalog',
            '-boot_image', 'grub', 'bin_path=/boot/grub/i386-pc/eltorito.img',
            '-boot_image', 'any', 'platform_id=0x00',
            '-boot_image', 'any', 'emul_type=no_emulation',
            '-boot_image', 'any', 'load_size=2048',
            '-boot_image', 'any', 'boot_info_table=on',
            '-boot_image', 'grub', 'grub2_boot_info=on',
            '-boot_image', 'any', 'next',
            '-boot_image', 'any', 'efi_path=--interval:appended_partition_2:all::',
            '-boot_image', 'any', 'platform_id=0xef',
            '-boot_image', 'any', 'emul_type=no_emulation',
            '-boot_image', 'any', 'load_size=5201920']


def volume_id(iso):
    with Path(iso).open('rb') as source:
        source.seek(16 * 2048)
        pvd = source.read(2048)
    if pvd[:7] != b'\x01CD001\x01':
        raise ValueError('missing ISO9660 primary volume descriptor')
    return pvd[40:72].decode('ascii').rstrip(' ')


def build(args):
    source, output = args.source.resolve(strict=True), args.output.resolve()
    if not source.is_file():
        raise ValueError('source must be a regular ISO file')
    if output.exists():
        raise ValueError('output directory already exists')
    expected = args.source_sha256.lower()
    if not re.fullmatch('[0-9a-f]{64}', expected) or digest(source) != expected:
        raise ValueError('source ISO SHA256 mismatch')
    if volume_id(source) != VOLUME_ID:
        raise ValueError('only Ubuntu Server 24.04.3 amd64 is supported')
    checker = shutil.which('grub-script-check') or shutil.which('grub2-script-check')
    if not checker or any(not shutil.which(c) for c in ('xorriso', 'cp')):
        raise ValueError('xorriso, GNU cp and grub-script-check are required')
    identity = source.stat()
    output.mkdir(parents=True)
    log_path = output / 'build.log'
    env = dict(os.environ, LC_ALL='C', LANG='C')

    def run(argv):
        proc = subprocess.run([str(v) for v in argv], capture_output=True, text=True, env=env)
        with log_path.open('a', encoding='utf-8') as log:
            log.write('$ ' + repr([str(v) for v in argv]) + '\n' + proc.stdout + proc.stderr)
        if proc.returncode:
            raise ValueError('command failed; see ' + str(log_path))
        return proc.stdout + proc.stderr

    def extract(iso, directory, paths):
        directory.mkdir()
        argv = ['xorriso', '-abort_on', 'FAILURE', '-osirrox', 'on', '-indev', iso]
        for path in paths:
            destination = directory / path.lstrip('/')
            destination.parent.mkdir(parents=True, exist_ok=True)
            argv.extend(['-extract', path, destination])
        run(argv)

    def report(iso, name):
        text = run(['xorriso', '-indev', iso, '-pvd_info', '-report_el_torito', 'plain',
                    '-report_system_area', 'plain'])
        (output / name).write_text(text, encoding='utf-8')
        return text

    paths = (GRUB_CONFIG, '/md5sum.txt', '/.disk/info') + BOOT_FILES
    extract(source, output / 'before', paths)
    before = output / 'before'
    info = (before / '.disk/info').read_text().strip()
    if not re.fullmatch(r'Ubuntu-Server 24\.04\.3 LTS "Noble Numbat" - Release amd64 \([0-9]+(?:\.[0-9]+)?\)', info):
        raise ValueError('unsupported .disk/info release')
    if digest(before / 'EFI/boot/grubx64.efi') != GRUB_SHA256:
        raise ValueError('unreviewed GRUB EFI binary; expected 2.12-1ubuntu7.3')
    original = (before / GRUB_CONFIG.lstrip('/')).read_bytes()
    updated = patch_config(original)
    new_config = output / 'grub.cfg'
    new_config.write_bytes(updated)
    new_md5 = output / 'md5sum.txt'
    new_md5.write_bytes(patch_md5((before / 'md5sum.txt').read_bytes(), original, updated))
    run([checker, new_config])
    original_report = report(source, 'source-boot-report.txt')
    signature = boot_signature(original_report)
    original_efi = efi_image_hash(source, original_report)

    candidate = output / 'candidate.iso.partial'
    # No fallback to a full ISO copy and no in-place write to the source.
    run(['cp', '--reflink=always', '--no-clobber', source, candidate])
    if (candidate.stat().st_dev, candidate.stat().st_ino) == (identity.st_dev, identity.st_ino):
        raise ValueError('candidate aliases the source inode')
    maps = ['-map', new_config, GRUB_CONFIG, '-map', new_md5, '/md5sum.txt']
    storage = 'reflink-grow'
    try:
        run(['xorriso', '-abort_on', 'FAILURE', '-dev', candidate] + maps +
            ['-boot_image', 'any', 'replay', '-commit', '-end'])
    except ValueError:
        # Ubuntu's hidden appended EFI partition can overlap a growing GPT.
        # Retaining stale boot metadata with "keep" is not an acceptable fix:
        # it can lose the BIOS boot-info-table and leave the GPT at the old end.
        if not getattr(args, 'allow_full_repack', False) or 'Overlapping GPT entries requested' not in log_path.read_text():
            raise
        if shutil.disk_usage(output).free < identity.st_size + 2 * 1024 ** 3:
            raise ValueError('not enough space for explicitly allowed full repack')
        candidate.rename(output / 'failed-grow.iso.partial')
        storage = 'full-repack-hidden-efi'
        efi_path = output / 'original-efi.img'
        efi_path.write_bytes(efi_image_bytes(source, original_report))
        run(['xorriso', '-abort_on', 'FAILURE', '-indev', source, '-outdev', candidate] + maps +
            repack_boot_args(source, original_report, efi_path) + ['-commit', '-end'])
    extract(candidate, output / 'after', paths)
    after = output / 'after'
    for path, expected_data in ((GRUB_CONFIG, updated), ('/md5sum.txt', new_md5.read_bytes())):
        if (after / path.lstrip('/')).read_bytes() != expected_data:
            raise ValueError('readback mismatch: ' + path)
    preserved = {}
    for path in BOOT_FILES + ('/.disk/info',):
        left, right = digest(before / path.lstrip('/')), digest(after / path.lstrip('/'))
        if left != right:
            raise ValueError('preserved file changed: ' + path)
        preserved[path] = left
    candidate_report = report(candidate, 'candidate-boot-report.txt')
    if volume_id(candidate) != VOLUME_ID or boot_signature(candidate_report) != signature:
        raise ValueError('volume or El Torito loading parameters changed')
    if efi_image_hash(candidate, candidate_report) != original_efi:
        raise ValueError('appended EFI boot image changed')
    current = source.stat()
    if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
            identity.st_dev, identity.st_ino, identity.st_size, identity.st_mtime_ns) or digest(source) != expected:
        raise ValueError('source changed during build; do not publish candidate')
    final = output / 'candidate.iso'
    candidate.rename(final)
    result = {'status': 'built-not-published', 'source': str(source), 'source_sha256': expected,
              'candidate': str(final), 'candidate_sha256': digest(final), 'candidate_size': final.stat().st_size,
              'storage': storage, 'volume_id': VOLUME_ID, 'menu_id': MENU_ID,
              'menu_title': MENU_TITLE, 'existing_menu_bytes_preserved': True,
              'compatibility_scope': 'Ubuntu 24.04.3 GA kernel, UEFI, opt-in GRUB TPM measurement skip',
              'preserved_files': preserved, 'efi_boot_image_sha256': original_efi,
              'el_torito': signature, 'syntax_check': str(checker), 'physical_test': 'not performed by builder'}
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True, help='new isolated directory, outside the live ISO inventory')
    parser.add_argument('--allow-full-repack', action='store_true',
                        help='allow a temporary full candidate when hidden EFI/GPT prevents reflink growth')
    args = parser.parse_args()
    try:
        build(args)
    except (OSError, ValueError) as error:
        print('Compatibility candidate FAILED: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
