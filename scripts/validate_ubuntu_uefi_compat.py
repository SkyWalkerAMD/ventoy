"""Validate the opt-in Ubuntu UEFI compatibility editor without an ISO or network."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ubuntu_uefi_compat', ROOT / 'tools/ubuntu-uefi-compat/build.py')
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)

ORIGINAL = ('''set timeout=30

loadfont unicode

set menu_color_normal=white/black
set menu_color_highlight=black/light-gray

''' + compat.GA_ENTRY + '''menuentry "Ubuntu Server with the HWE kernel" {
\tset gfxpayload=keep
\tlinux\t/casper/hwe-vmlinuz  ---
\tinitrd\t/casper/hwe-initrd
}
grub_platform
if [ "$grub_platform" = "efi" ]; then
menuentry 'Boot from next volume' {
\texit 1
}
menuentry 'UEFI Firmware Settings' {
\tfwsetup
}
else
menuentry 'Test memory' {
\tlinux16 /boot/memtest86+x64.bin
}
fi

''').encode('ascii')

REPORT = '''El Torito boot img :   1  BIOS  y   none  0x0000  0x00      4     1613564
El Torito boot img :   2  UEFI  y   none  0x0000  0x00  10160     1610304
El Torito img path :   1  /boot/grub/i386-pc/eltorito.img
El Torito img opts :   1  boot-info-table grub2-boot-info
'''


class CompatibilityTests(unittest.TestCase):
    def test_append_preserves_existing_defaults_and_command_bytes(self):
        edited = compat.patch_config(ORIGINAL)
        self.assertEqual(edited[:len(ORIGINAL)], ORIGINAL)
        appended = edited[len(ORIGINAL):].decode()
        self.assertTrue(appended.startswith('\n' + compat.MARKER))
        self.assertEqual(appended.count('menuentry '), 1)
        self.assertEqual(edited.count(b'set timeout='), 1)
        self.assertNotIn('set default', appended)
        self.assertNotIn('hwe-', appended)
        # Keep standalone command lines identical for iVentoy interception.
        for line in ('\tlinux\t/casper/vmlinuz  ---\n', '\tinitrd\t/casper/initrd\n'):
            self.assertEqual(appended.count(line), 1)
        for argument in ('autoinstall', 'vtinit', 'nomodeset', 'initrdmem', 'efi='):
            self.assertNotIn(argument, appended)

    def test_tpm_change_is_only_inside_efi_opt_in_entry(self):
        edited = compat.patch_config(ORIGINAL).decode()
        addition = edited[len(ORIGINAL):]
        start = addition.index('menuentry ')
        self.assertLess(addition.index('if [ "$grub_platform" = "efi" ]'), start)
        self.assertGreater(addition.index('if rmmod tpm; then'), start)
        self.assertEqual(edited.count('rmmod tpm'), 1)
        self.assertIn('insmod tpm', addition)
        self.assertIn('skips GRUB TPM measurement', addition)
        for unsafe in ('rmmod shim_lock', 'check_signatures', 'fwsetup', 'save_env', 'set default'):
            self.assertNotIn(unsafe, addition)
        self.assertLess(addition.index('boot\n'), addition.index('insmod tpm'))
        self.assertTrue(addition.rstrip().endswith('exit 1\n}\nfi'))
        self.assertEqual(addition.count('if [ "$?" = "0" ]; then'), 2)

    def test_repeated_or_unknown_config_is_rejected(self):
        bad = [compat.patch_config(ORIGINAL), ORIGINAL.replace(b' ---', b' quiet ---', 1),
               ORIGINAL.replace(b'timeout=30', b'timeout=0'),
               b'set default=1\n' + ORIGINAL, ORIGINAL + b'rmmod tpm\n',
               ORIGINAL.replace(b'\n', b'\r\n'), ORIGINAL.replace(b'Test memory', b'Test memory\nmenuentry ')]
        for data in bad:
            with self.subTest(data=data[-80:]), self.assertRaises(ValueError):
                compat.patch_config(data)

    def test_md5_updates_only_config_and_preserves_other_lines(self):
        old = hashlib.md5(ORIGINAL).hexdigest()
        manifest = (old + '  ./boot/grub/grub.cfg\n' + 'f' * 32 + '  ./casper/initrd\n').encode()
        changed = compat.patch_config(ORIGINAL)
        result = compat.patch_md5(manifest, ORIGINAL, changed)
        self.assertEqual(result.splitlines()[1:], manifest.splitlines()[1:])
        self.assertTrue(result.startswith(hashlib.md5(changed).hexdigest().encode()))
        for bad in (b'', manifest.replace(old.encode(), b'0' * 32), manifest + manifest):
            with self.assertRaises(ValueError):
                compat.patch_md5(bad, ORIGINAL, changed)

    def test_el_torito_relocation_allowed_but_semantic_change_detected(self):
        signature = compat.boot_signature(REPORT)
        self.assertEqual(signature, compat.boot_signature(REPORT.replace('1613564', '1972000')))
        for before, after in [('10160', '10000'), ('0x0000', '0x07c0'), (' y ', ' n '),
                              ('none', 'floppy'), ('grub2-boot-info', '')]:
            self.assertNotEqual(signature, compat.boot_signature(REPORT.replace(before, after)))
        for bad in ('', REPORT.replace('UEFI', 'BIOS'), REPORT.replace('10160', '10160 extra')):
            with self.assertRaises(ValueError):
                compat.boot_signature(bad)

    def test_existing_output_and_wrong_digest_cannot_mutate_iso(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source.iso'
            source.write_bytes(b'not an ISO')
            args = argparse.Namespace(source=source, output=root, source_sha256='0' * 64)
            with patch.object(compat.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    compat.build(args)
                args.output = root / 'new'
                with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                    compat.build(args)
                args.source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
                with self.assertRaisesRegex(ValueError, 'volume descriptor'):
                    compat.build(args)
                run.assert_not_called()
                self.assertFalse(args.output.exists())

    def test_explicit_repack_preserves_volume_uuid_and_both_boot_paths(self):
        args = compat.repack_boot_args('/source.iso', REPORT + 'Creation Time: 2025080523540700\n', '/original-efi.img')
        self.assertEqual(args[args.index('-volume_date') + 1:args.index('-volume_date') + 3],
                         ['uuid', '2025080523540700'])
        self.assertIn('efi_path=--interval:appended_partition_2:all::', args)
        self.assertIn('bin_path=/boot/grub/i386-pc/eltorito.img', args)
        self.assertIn('boot_info_table=on', args)
        self.assertIn('grub2_boot_info=on', args)
        self.assertIn('load_size=5201920', args)
        self.assertEqual(args[args.index('-append_partition') + 1:args.index('-append_partition') + 4],
                         ['2', '0xef', '/original-efi.img'])
        for report in (REPORT, REPORT.replace('10160', '10159') + 'Creation Time: 2025080523540700\n'):
            with self.assertRaises(ValueError):
                compat.repack_boot_args('/source.iso', report, '/original-efi.img')

    def test_efi_image_hash_uses_complete_bounded_boot_extent(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'fixture.iso'
            data = b'prefix'.ljust(2048, b'\0') + b'a' * 512 + b'suffix'
            path.write_bytes(data)
            report = 'El Torito boot img : 2 UEFI y none 0x0000 0x00 1 1\n'
            self.assertEqual(compat.efi_image_hash(path, report), hashlib.sha256(b'a' * 512).hexdigest())
            for bad in (report.replace('1 1', '2 1'), report.replace('1 1', '1 20')):
                with self.assertRaisesRegex(ValueError, 'extent'):
                    compat.efi_image_hash(path, bad)


if __name__ == '__main__':
    unittest.main()
