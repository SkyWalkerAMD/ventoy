"""Protect boot arguments, separators and unrelated menu paths during edits."""
from pathlib import Path
import hashlib
import importlib.util
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bmc_menus', ROOT / 'tools/linux-bmc-display/menus.py')
menus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(menus)
sys.path.insert(0, str(ROOT / 'tools/linux-bmc-display'))
spec = importlib.util.spec_from_file_location('bmc_build', ROOT / 'tools/linux-bmc-display/build.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class MenuTests(unittest.TestCase):
    def test_grub_all_install_modes_keep_boot_paths_and_defaults(self):
        original = (b'set default="1"\nset timeout=60\n'
                    b'menuentry "Install" {\n'
                    b' linuxefi /images/pxeboot/vmlinuz inst.stage2=hd:LABEL=Example\\x20OS quiet\n'
                    b' initrdefi /images/pxeboot/initrd.img\n}\n'
                    b'linux /casper/hwe-vmlinuz autoinstall ---\n'
                    b'linux16 /boot/memtest86.bin\nexit 1\n')
        changed, result = menus.patch_config(original, 'grub')
        self.assertEqual(result, {'matched': 2, 'changed': 2})
        self.assertEqual(changed.count(b'nomodeset'), 2)
        self.assertIn(b'Example\\x20OS quiet nomodeset\n', changed)
        self.assertIn(b'autoinstall nomodeset ---', changed)
        for line in original.splitlines():
            if not line.strip().startswith((b'linux ', b'linuxefi ')):
                self.assertIn(line + b'\n', changed)

    def test_syslinux_preserves_memtest_and_manual_auto(self):
        original = (b'label install\n kernel /install.amd/vmlinuz\n'
                    b' append initrd=/install.amd/initrd.gz --- quiet\n'
                    b'label auto\n kernel /install.amd/vmlinuz\n'
                    b' append auto=true initrd=/install.amd/initrd.gz ---\n'
                    b'label memtest\n kernel memtest\n append console=tty0\n')
        changed, counts = menus.patch_config(original, 'syslinux')
        self.assertEqual(counts['changed'], 2)
        self.assertIn(b'--- quiet', changed)
        self.assertIn(b'nomodeset ---', changed)
        self.assertIn(b'kernel memtest\n append console=tty0\n', changed)

    def test_existing_nomodeset_is_idempotent(self):
        original = b'linux /casper/vmlinuz nomodeset ---\n'
        changed, counts = menus.patch_config(original, 'grub')
        self.assertEqual(changed, original)
        self.assertEqual(counts, {'matched': 1, 'changed': 0})

    def test_tpm_compatibility_logic_is_preserved(self):
        original = (b'if rmmod tpm; then\n linux /casper/vmlinuz ---\n'
                    b' initrd /casper/initrd\n boot\nfi\ninsmod tpm\nexit 1\n')
        changed, _ = menus.patch_config(original, 'grub')
        self.assertEqual(changed.replace(b'nomodeset ', b''), original)

    def test_only_exact_installer_kernel_names_match(self):
        for path in ['/boot/memtest86+x64.bin', '/kernel-not-reviewed', '/install.amd/vmlinuz.efi.bad;boot']:
            original = ('linux ' + path + ' quiet\n').encode()
            self.assertEqual(menus.patch_config(original, 'grub')[0], original)

    def test_compound_commands_and_encoding_fail_closed(self):
        for text in ['linux /casper/vmlinuz quiet; boot\n',
                     'linux /casper/vmlinuz quiet # comment\n',
                     'linux /casper/vmlinuz quiet \\\n',
                     'linux /casper/vmlinuz nomodeset=0\n',
                     'linux /casper/vmlinuz\r\n']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                menus.patch_config(text.encode(), 'grub')

    def test_empty_and_missing_final_newline_are_preserved(self):
        self.assertEqual(menus.patch_config(b'', 'syslinux'), (b'', {'matched': 0, 'changed': 0}))
        self.assertEqual(menus.patch_config(b'linux /casper/vmlinuz', 'grub')[0],
                         b'linux /casper/vmlinuz nomodeset')
        original = b'linux /casper/vmlinuz ---\ninitrd /casper/initrd\n}'
        result, _ = menus.patch_config(original, 'grub')
        self.assertTrue(result.endswith(b'\n}'))

    def test_checksum_preserves_other_records(self):
        before, after = b'before\n', b'after\n'
        source = (hashlib.md5(before).hexdigest() + '  ./boot/grub/grub.cfg\n' +
                  'f' * 32 + '  ./casper/initrd\n').encode()
        changed = menus.patch_checksums(source, {'/boot/grub/grub.cfg': (before, after)}, 'md5')
        self.assertEqual(changed.splitlines()[1:], source.splitlines()[1:])
        self.assertTrue(changed.startswith(hashlib.md5(after).hexdigest().encode()))
        with self.assertRaises(ValueError):
            menus.patch_checksums(source, {'/boot/grub/grub.cfg': (b'wrong', after)}, 'md5')

    def test_treeinfo_updates_only_efi_image_digest(self):
        before, after = b'old image', b'new image'
        original = ('[general]\nname = Example OS\n[checksums]\nimages/efiboot.img = sha256:' +
                    hashlib.sha256(before).hexdigest() + '\nimages/pxeboot/initrd.img = sha256:' + 'e' * 64 + '\n').encode()
        result = menus.patch_treeinfo(original, {'/images/efiboot.img': (before, after)})
        self.assertIn(hashlib.sha256(after).hexdigest().encode(), result)
        self.assertEqual(result.splitlines()[-1], original.splitlines()[-1])

    def test_boot_loading_parameters_preserved_except_sector_locations(self):
        text = ('El Torito boot img : 1 BIOS y none 0x0000 0x00 4 100\n'
                'El Torito boot img : 2 UEFI y none 0x0000 0x00 10240 200\n'
                'El Torito img path : 1 /boot/grub/i386-pc/eltorito.img\n'
                'El Torito img opts : 1 boot-info-table grub2-boot-info\n'
                'El Torito cat path : /boot.catalog\n'
                'Creation Time: 2026010100000000\nPartition offset : 0\n')
        self.assertEqual(builder.boot_signature(text), builder.boot_signature(text.replace('4 100', '4 300')))
        self.assertNotEqual(builder.boot_signature(text), builder.boot_signature(text.replace('10240', '10160')))
        args = builder.appended_efi_args('/source.iso', text, '/efi.img')
        self.assertIn('partition_offset=0', args)
        self.assertIn('efi_path=--interval:appended_partition_2:all::', args)
        self.assertIn('load_size=5242880', args)
        for bad in [text.replace('grub2-boot-info', ''), text.replace('Partition offset : 0', ''),
                    text.replace('UEFI', 'OTHER'), text.replace('/boot/grub/i386-pc/eltorito.img', '/other.img')]:
            with self.subTest(text=bad), self.assertRaises(ValueError):
                builder.appended_efi_args('/source.iso', bad, '/efi.img')
        hidden = text.replace('/boot/grub/i386-pc/eltorito.img', '/images/eltorito.img').replace(
            'El Torito cat path : /boot.catalog', 'El Torito catalog : 100 1')
        self.assertIn('cat_hidden=on', builder.appended_efi_args('/source.iso', hidden, '/efi.img'))

    def test_efi_extent_is_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'fixture.iso'
            path.write_bytes(b'\0' * 2048 + b'a' * 512)
            report = 'El Torito boot img : 2 UEFI y none 0x0000 0x00 1 1\n'
            self.assertEqual(builder.efi_bytes(path, report), b'a' * 512)
            with self.assertRaises(ValueError):
                builder.efi_bytes(path, report.replace('1 1', '2 1'))

    def test_hybrid_partition_scheme_cannot_silently_disappear(self):
        first = 'System area summary: MBR isohybrid cyl-align-off GPT\n'
        same = 'System area summary: MBR isohybrid GPT\n'
        lost = 'System area summary: MBR isohybrid\n'
        self.assertEqual(builder.system_signature(first), builder.system_signature(same))
        self.assertNotEqual(builder.system_signature(first), builder.system_signature(lost))
        with self.assertRaises(ValueError):
            builder.system_signature('no system area\n')


if __name__ == '__main__':
    unittest.main()
