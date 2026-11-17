#!/usr/bin/env python3
"""Build an unpublished Linux ISO with nomodeset on its installer entries.

The source is read-only. Existing kernel/initrd payloads, boot entry order and
installation arguments are preserved. No client disk or server is changed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess

from menus import menu_kind, patch_checksums, patch_config, patch_treeinfo


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def paths_from_listing(text):
    result = []
    for line in text.splitlines():
        if not line.startswith("'/"):
            continue
        row = shlex.split(line)
        if len(row) != 1:
            raise ValueError('ambiguous ISO path')
        path = PurePosixPath(row[0])
        if not path.is_absolute() or '..' in path.parts or str(path) != row[0]:
            raise ValueError('unsafe ISO path')
        result.append(row[0])
    if not result:
        raise ValueError('empty ISO file listing')
    return sorted(set(result))


def boot_records(text):
    images, paths, options = [], [], []
    for line in text.splitlines():
        if line.startswith('El Torito boot img :'):
            row = line.split(':', 1)[1].split()
            if len(row) != 8 or row[1] not in ('BIOS', 'UEFI'):
                raise ValueError('unsupported boot record')
            images.append(row)
        elif line.startswith('El Torito img path :'):
            paths.append(line.split(':', 1)[1].split())
        elif line.startswith('El Torito img opts :'):
            options.append(line.split(':', 1)[1].split())
    if not images or len([r for r in images if r[1] == 'UEFI']) != 1:
        raise ValueError('expected one x86 UEFI boot image')
    return {'images': images, 'paths': paths, 'options': options}


def boot_signature(text):
    record = boot_records(text)
    record['images'] = [row[:-1] for row in record['images']]
    return record


def system_signature(text):
    match = re.search(r'(?m)^System area summary:\s*(.*)$', text)
    if not match:
        raise ValueError('missing hybrid partition information')
    return {word for word in match[1].split()
            if word in ('MBR', 'GPT', 'APM', 'isohybrid', 'grub2-mbr')}


def hidden_bios_keep(text, error):
    """Keep existing extents only for the reviewed hidden-BIOS replay failure."""
    record = boot_records(text)
    return ("because it is not a data file in the ISO filesystem" in error and
            [row[1] for row in record['images']] == ['BIOS', 'UEFI'] and
            record['images'][0][2:7] == ['y', 'none', '0x0000', '0x00', '4'] and
            not any(row[0] == '1' for row in record['paths']) and
            ['2', '/images/efiboot.img'] in record['paths'] and
            system_signature(text) == {'MBR', 'GPT'})


def efi_bytes(iso, text):
    row = next(r for r in boot_records(text)['images'] if r[1] == 'UEFI')
    length, offset = int(row[6]) * 512, int(row[7]) * 2048
    if not 512 <= length <= 64 * 1024 * 1024 or offset + length > iso.stat().st_size:
        raise ValueError('invalid EFI extent')
    with iso.open('rb') as source:
        source.seek(offset)
        data = source.read(length)
    if len(data) != length:
        raise ValueError('truncated EFI image')
    return data


def appended_efi_args(source, text, image):
    """Explicit replay for GRUB hybrid media whose hidden EFI prevents growth."""
    record = boot_records(text)
    if ([r[1] for r in record['images']] != ['BIOS', 'UEFI'] or
            record['images'][0][2:7] != ['y', 'none', '0x0000', '0x00', '4'] or
            record['images'][1][2:6] != ['y', 'none', '0x0000', '0x00']):
        raise ValueError('unsupported appended-EFI boot layout')
    bios = next((r[1] for r in record['paths'] if r[0] == '1'), None)
    if bios not in ('/boot/grub/i386-pc/eltorito.img', '/images/eltorito.img'):
        raise ValueError('unsupported GRUB BIOS image')
    if ['1', 'boot-info-table', 'grub2-boot-info'] not in record['options']:
        raise ValueError('unreviewed BIOS loading options')
    date = re.search(r'(?m)^Creation Time:\s+([0-9]{16})$', text)
    offset = re.search(r'(?m)^Partition offset\s*:\s*(0|16)\s*$', text)
    catalog = re.search(r'(?m)^El Torito cat path\s*:\s*(/[^\s]+)\s*$', text)
    if not date or not offset:
        raise ValueError('missing volume timestamp or partition offset')
    if not catalog and (bios != '/images/eltorito.img' or
                        not re.search(r'(?m)^El Torito catalog\s*:\s*\d+\s+1\s*$', text)):
        raise ValueError('unreviewed hidden boot catalog')
    catalog_args = ['-boot_image', 'any', 'cat_path=' + (catalog[1] if catalog else '/boot.catalog')]
    if not catalog:
        catalog_args += ['-boot_image', 'any', 'cat_hidden=on']
    size = int(record['images'][1][6]) * 512
    return ['-boot_image', 'any', 'discard', '-volume_date', 'uuid', date[1],
            '-boot_image', 'grub', 'grub2_mbr=--interval:imported_iso:0s-15s:zero_mbrpt,zero_gpt:' + str(source),
            '-boot_image', 'any', 'partition_table=on',
            '-boot_image', 'any', 'partition_cyl_align=off',
            '-boot_image', 'any', 'partition_offset=' + offset[1],
            '-boot_image', 'any', 'mbr_force_bootable=on',
            '-append_partition', '2', '0xef', str(image),
            '-boot_image', 'any', 'appended_part_as=gpt',
            *catalog_args,
            '-boot_image', 'grub', 'bin_path=' + bios,
            '-boot_image', 'any', 'platform_id=0x00',
            '-boot_image', 'any', 'emul_type=no_emulation',
            '-boot_image', 'any', 'load_size=2048',
            '-boot_image', 'any', 'boot_info_table=on',
            '-boot_image', 'grub', 'grub2_boot_info=on',
            '-boot_image', 'any', 'next',
            '-boot_image', 'any', 'efi_path=--interval:appended_partition_2:all::',
            '-boot_image', 'any', 'platform_id=0xef',
            '-boot_image', 'any', 'emul_type=no_emulation',
            '-boot_image', 'any', 'load_size=' + str(size)]


def volume_id(iso):
    with iso.open('rb') as stream:
        stream.seek(16 * 2048)
        pvd = stream.read(2048)
    if pvd[:7] != b'\x01CD001\x01':
        raise ValueError('missing ISO9660 volume descriptor')
    return pvd[40:72].decode('ascii').rstrip(' ')


def build(args):
    source = args.source.absolute()
    if source.is_symlink() or not source.is_file() or source.suffix.lower() != '.iso':
        raise ValueError('source must be a regular ISO file')
    source = source.resolve(strict=True)
    output = args.output.resolve()
    if output.exists():
        raise ValueError('output directory already exists')
    if not re.fullmatch('[0-9a-f]{64}', args.source_sha256) or digest(source) != args.source_sha256:
        raise ValueError('source ISO SHA256 mismatch')
    checker = shutil.which('grub-script-check') or shutil.which('grub2-script-check')
    if not checker or any(not shutil.which(name) for name in ('xorriso', 'cp', 'mcopy', 'mdir')):
        raise ValueError('xorriso, GNU cp, mtools and GRUB syntax checker are required')
    initial = source.stat()
    output.mkdir(parents=True)
    before, after = output / 'before', output / 'after'
    before.mkdir(); after.mkdir()
    log = output / 'build.log'
    env = dict(os.environ, LC_ALL='C', LANG='C', MTOOLS_SKIP_CHECK='1')

    def run(argv, optional=False):
        proc = subprocess.run([str(v) for v in argv], capture_output=True, text=True, env=env)
        with log.open('a') as stream:
            stream.write(repr([str(v) for v in argv]) + '\n' + proc.stdout + proc.stderr)
        if proc.returncode and not optional:
            raise ValueError('command failed; inspect build.log')
        return proc

    def extract(iso, name, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        run(['xorriso', '-abort_on', 'FAILURE', '-osirrox', 'on', '-indev', iso, '-extract', name, target])

    def report(iso):
        proc = run(['xorriso', '-indev', iso, '-pvd_info', '-report_el_torito', 'plain', '-report_system_area', 'plain'])
        return proc.stdout + proc.stderr

    def fat_inventory(image, folder):
        folder.mkdir()
        names = run(['mdir', '-i', image, '-/', '-b', '::/']).stdout.splitlines()
        files = {}
        for index, name in enumerate(names):
            if name.endswith('/'):
                continue
            if not name.startswith('::/') or '..' in PurePosixPath(name[3:]).parts:
                raise ValueError('unrecognized FAT path')
            dest = folder / str(index)
            run(['mcopy', '-i', image, name, dest])
            files[name] = dest
        return files

    paths = paths_from_listing(run(['xorriso', '-indev', source, '-find', '/', '-type', 'f', '-exec', 'echo', '--']).stdout)
    original_report = report(source)
    (output / 'source-boot-report.txt').write_text(original_report)
    signature = boot_signature(original_report)
    changes, stats = {}, {}
    for name in paths:
        kind = menu_kind(name)
        if not kind:
            continue
        original = before / name.lstrip('/')
        extract(source, name, original)
        data = original.read_bytes()
        updated, counts = patch_config(data, kind)
        stats[name] = counts
        if updated != data:
            changes[name] = (data, updated)
            if kind == 'grub':
                check = after / name.lstrip('/')
                check.parent.mkdir(parents=True, exist_ok=True)
                check.write_bytes(updated)
                run([checker, check])
    if not sum(row['matched'] for row in stats.values()):
        raise ValueError('no recognized Linux installer commands')
    if not changes:
        raise ValueError('all installer entries already have nomodeset')

    efi_before = output / 'original-efi.img'
    efi_before.write_bytes(efi_bytes(source, original_report))
    fat_before = fat_inventory(efi_before, output / 'fat-before')
    efi_after = output / 'updated-efi.img'
    shutil.copyfile(efi_before, efi_after)
    fat_updates = {}
    for name, path in fat_before.items():
        if name.lower().endswith('/grub.cfg'):
            data = path.read_bytes()
            updated, counts = patch_config(data, 'grub')
            if updated != data:
                replacement = output / ('fat-menu-' + str(len(fat_updates)))
                replacement.write_bytes(updated)
                run([checker, replacement])
                run(['mcopy', '-o', '-i', efi_after, replacement, name])
                fat_updates[name] = hashlib.sha256(updated).hexdigest()
    fat_after = fat_inventory(efi_after, output / 'fat-after')
    if set(fat_before) != set(fat_after):
        raise ValueError('EFI filesystem paths changed')
    for name in fat_before:
        expected = fat_updates.get(name, digest(fat_before[name]))
        if digest(fat_after[name]) != expected:
            raise ValueError('unexpected EFI file change: ' + name)
    visible_efi = next((r[1] for r in boot_records(original_report)['paths'] if r[0] == '2'), None)
    if fat_updates and visible_efi:
        original = before / visible_efi.lstrip('/')
        extract(source, visible_efi, original)
        if original.read_bytes() != efi_before.read_bytes():
            raise ValueError('visible EFI image differs from boot image')
        changes[visible_efi] = (original.read_bytes(), efi_after.read_bytes())

    for name, algo in [('/md5sum.txt', 'md5'), ('/SHA256SUMS', 'sha256'), ('/SHA512SUMS', 'sha512')]:
        if name in paths:
            original = before / name.lstrip('/')
            extract(source, name, original)
            data = original.read_bytes()
            updated = patch_checksums(data, changes, algo)
            if updated != data:
                changes[name] = (data, updated)
    if '/.treeinfo' in paths:
        original = before / '.treeinfo'
        extract(source, '/.treeinfo', original)
        data = original.read_bytes()
        updated = patch_treeinfo(data, changes)
        if updated != data:
            changes['/.treeinfo'] = (data, updated)

    maps = []
    for name, (_, data) in changes.items():
        target = after / name.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        # EFI is a fixed-size FAT extent shared with the hybrid partition table.
        # Replacing its ISO tree node before replay leaves a stale boot extent.
        # Patch that exact extent on the private candidate after boot replay.
        if name != visible_efi:
            maps += ['-map', str(target), name]
    candidate = output / 'candidate.iso.partial'
    run(['cp', '--reflink=always', '--no-clobber', source, candidate])
    if candidate.stat().st_ino == initial.st_ino and candidate.stat().st_dev == initial.st_dev:
        raise ValueError('candidate aliases source')
    grown = run(['xorriso', '-abort_on', 'FAILURE', '-dev', candidate] + maps +
                ['-boot_image', 'any', 'replay', '-commit', '-end'], optional=True)
    storage = 'reflink-grow'
    if grown.returncode and hidden_bios_keep(original_report, grown.stderr):
        candidate.rename(output / 'failed-grow.iso.partial')
        run(['cp', '--reflink=always', '--no-clobber', source, candidate])
        # A hidden BIOS loader has no tree path for replay. Keep its original
        # extents and the existing hybrid system area while appending menus.
        run(['xorriso', '-abort_on', 'FAILURE', '-dev', candidate] + maps +
            ['-boot_image', 'any', 'keep', '-commit', '-end'])
        storage = 'reflink-grow-kept-hidden-bios'
        bios = boot_records(original_report)['images'][0]
        with source.open('rb') as left, candidate.open('rb') as right:
            if left.read(32768) != right.read(32768):
                raise ValueError('kept hybrid system area changed')
            left.seek(int(bios[7]) * 2048); right.seek(int(bios[7]) * 2048)
            if left.read(65536) != right.read(65536):
                raise ValueError('kept hidden BIOS extent changed')
    elif grown.returncode:
        if not args.allow_full_repack or 'Overlapping GPT entries requested' not in grown.stderr:
            raise ValueError('candidate growth failed; inspect build.log')
        if shutil.disk_usage(output).free < initial.st_size + 2 * 1024**3:
            raise ValueError('not enough free space for explicit full repack')
        candidate.rename(output / 'failed-grow.iso.partial')
        run(['xorriso', '-abort_on', 'FAILURE', '-indev', source, '-outdev', candidate] + maps +
            appended_efi_args(source, original_report, efi_after) + ['-commit', '-end'])
        storage = 'full-repack-appended-efi'
    final_report = report(candidate)
    (output / 'candidate-boot-report.txt').write_text(final_report)
    if boot_signature(final_report) != signature:
        raise ValueError('El Torito loading parameters changed')
    if system_signature(final_report) != system_signature(original_report):
        raise ValueError('hybrid partition scheme changed')
    if volume_id(source) != volume_id(candidate):
        raise ValueError('volume label changed')
    current_efi = efi_bytes(candidate, final_report)
    if current_efi not in (efi_before.read_bytes(), efi_after.read_bytes()):
        raise ValueError('unexpected EFI extent before patch')
    efi_record = next(r for r in boot_records(final_report)['images'] if r[1] == 'UEFI')
    with candidate.open('r+b') as stream:
        stream.seek(int(efi_record[7]) * 2048)
        stream.write(efi_after.read_bytes())
        stream.flush()
        os.fsync(stream.fileno())
    if efi_bytes(candidate, final_report) != efi_after.read_bytes():
        raise ValueError('EFI boot image readback differs')
    if '/.treeinfo' in paths:
        run(['implantisomd5', '--force', '--supported-iso', candidate])
        run(['checkisomd5', candidate])
    final_paths = paths_from_listing(run(['xorriso', '-indev', candidate, '-find', '/', '-type', 'f', '-exec', 'echo', '--']).stdout)
    if paths != final_paths:
        raise ValueError('ISO file inventory changed')
    preserved = {}
    for name in paths:
        # A modified boot loader record is checked through the boot signature.
        if name in changes:
            continue
        base = PurePosixPath(name).name.lower()
        if (menu_kind(name) or 'initrd' in base or base.startswith(('vmlinuz', 'hwe-vmlinuz')) or
                name.startswith('/ventoy-e610/') or base.endswith('.efi') or base == 'e610-media.json'):
            left, right = output / 'preserve-before', output / 'preserve-after'
            extract(source, name, left); extract(candidate, name, right)
            preserved[name] = digest(left)
            if digest(right) != preserved[name]:
                raise ValueError('kernel, driver or EFI executable changed: ' + name)
            left.unlink(); right.unlink()
    for name, (_, expected) in changes.items():
        readback = output / 'readback'
        extract(candidate, name, readback)
        if readback.read_bytes() != expected:
            raise ValueError('changed file readback mismatch: ' + name)
        readback.unlink()
    now = source.stat()
    if (now.st_dev, now.st_ino, now.st_size, now.st_mtime_ns) != (
            initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns):
        raise ValueError('source changed during build')
    final = output / 'candidate.iso'
    candidate.rename(final)
    result = {'status': 'built-not-published', 'source_sha256': args.source_sha256,
              'candidate_sha256': digest(final), 'candidate_size': final.stat().st_size,
              'parameter': 'nomodeset', 'storage': storage, 'menus': stats,
              'changed_files': sorted(changes), 'efi_menu_changes': sorted(fat_updates),
              'preserved_files': preserved, 'el_torito': signature,
              'physical_ast2500': 'not-tested', 'physical_ast2600': 'not-tested'}
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-full-repack', action='store_true')
    args = parser.parse_args()
    try:
        build(args)
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
