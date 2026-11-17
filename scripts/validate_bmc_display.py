"""Protect boot arguments, separators and unrelated menu paths during edits."""
from pathlib import Path
import hashlib
import importlib.util
import sys
import struct
import shutil
import subprocess
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

POLICY = ROOT / 'internal/center/assets/manual-preload/bmc-display-target.sh'


@unittest.skipUnless(shutil.which('sh') and sys.platform.startswith('linux'), 'requires Linux shell tools')
class TargetPolicyTests(unittest.TestCase):
    def test_explicit_policy_on_disposable_grub_configurations(self):
        # Run the chroot body with paths scoped to a fixture. A fake update-grub
        # reads the real edited defaults and emits a kernel command to verify.
        script = POLICY.read_text().split("<<'VCBMC'\n", 1)[1].split('\nVCBMC\n', 1)[0]
        for mode in ('install', 'installed'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                defaults = root / 'etc/default'
                defaults.mkdir(parents=True)
                (defaults / 'grub').write_text('GRUB_CMDLINE_LINUX="rootfixed nomodeset nomodeset"\n'
                                              'GRUB_CMDLINE_LINUX_DEFAULT="nomodeset quiet unrelated=nomodeset"\n')
                boot = root / 'boot/grub'
                boot.mkdir(parents=True)
                (boot / 'grub.cfg').touch()
                fake = r'''update-grub() {
    . /etc/default/grub
    for conf in /etc/default/grub.d/*.cfg; do [ ! -f "$conf" ] || . "$conf"; done
    printf 'linux /boot/vmlinuz-test %s %s\n' "$GRUB_CMDLINE_LINUX" \
      "$GRUB_CMDLINE_LINUX_DEFAULT" > /boot/grub/grub.cfg
}
'''
                body = script.replace('command -v grubby >/dev/null 2>&1', 'false')
                sandbox = (fake + body).replace('/etc/default', str(defaults))
                # Replace only the menu location, not vmlinuz inside it.
                sandbox = sandbox.replace('/boot/grub/grub.cfg', str(boot / 'grub.cfg'))
                for _ in range(2):
                    subprocess.run(['sh', '-s', '--', mode], input=sandbox, text=True, check=True)
                actual = (boot / 'grub.cfg').read_text().split()
                self.assertEqual(actual.count('nomodeset'), int(mode == 'installed'))
                self.assertIn('rootfixed', actual)
                self.assertIn('quiet', actual)
                self.assertIn('unrelated=nomodeset', actual)
                self.assertEqual((defaults / 'grub.d/zz-ventoy-bmc-display.cfg').exists(),
                                 mode == 'installed')


class MenuTests(unittest.TestCase):
    def test_ast_grub_choices_leave_normal_and_fallback_entries_intact(self):
        original = (b'set default=0\nmenuentry "Graphical install" {\n'
                    b' linux /install.amd/vmlinuz --- quiet\n initrd /install.amd/gtk/initrd.gz\n}\n'
                    b'menuentry "Install" {\n linux /install.amd/vmlinuz --- quiet\n'
                    b' initrd /install.amd/initrd.gz\n}\n'
                    b'menuentry "Safe graphics" {\n linux /install.amd/vmlinuz nomodeset ---\n'
                    b' initrd /install.amd/gtk/initrd.gz\n}\n')
        result, stats = menus.compatibility_choices(original, 'grub')
        self.assertEqual(stats['entries_added'], 2)
        self.assertTrue(result.startswith(original))
        appended = result[len(original):]
        self.assertNotIn(b'/gtk/', appended)
        self.assertIn(b'nomodeset ventoy.bmc=install --- quiet', appended)
        self.assertIn(b'nomodeset ventoy.bmc=installed --- quiet', appended)

    def test_ast_syslinux_choices_are_selectable_and_keep_the_media_default(self):
        original = (b'default check\nlabel linux\n menu label Install\n kernel vmlinuz\n'
                    b' append initrd=initrd.img quiet\nlabel check\n menu default\n'
                    b' kernel vmlinuz\n append initrd=initrd.img rd.live.check quiet\n'
                    b'menu begin Troubleshooting\nlabel rescue\n kernel vmlinuz\n'
                    b' append initrd=initrd.img rescue\nmenu end\n')
        result, stats = menus.compatibility_choices(original, 'syslinux')
        self.assertEqual(stats['entries_added'], 2)
        self.assertTrue(result.startswith(original))
        self.assertEqual(result.count(b'menu default'), 1)
        self.assertIn(b'append initrd=initrd.img quiet nomodeset ventoy.bmc=install\n', result)
        self.assertNotIn(b'rescue nomodeset', result)

    def test_el10_bios_grub2_directory_is_an_installer_menu(self):
        for name in ['/boot/grub2/grub.cfg', '/boot/grub/grub.cfg', '/EFI/BOOT/grub.cfg']:
            self.assertEqual(menus.menu_kind(name), 'grub')
        self.assertIsNone(menus.menu_kind('/boot/grub2-unrelated/grub.cfg'))

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
                     'linux /casper/vmlinuz quiet # nomodeset\n',
                     'linux /casper/vmlinuz nomodeset modeset=1\n',
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

    def test_keep_fallback_requires_the_exact_hidden_bios_layout(self):
        report = ('El Torito boot img : 1 BIOS y none 0x0000 0x00 4 100\n'
                  'El Torito boot img : 2 UEFI y none 0x0000 0x00 10240 200\n'
                  'El Torito img path : 2 /images/efiboot.img\n'
                  'System area summary: MBR cyl-align-off GPT\n')
        error = 'Cannot enable EL Torito boot image #1 because it is not a data file in the ISO filesystem'
        self.assertTrue(builder.hidden_bios_keep(report, error))
        self.assertFalse(builder.hidden_bios_keep(report, 'unrelated error'))
        for bad in [report + 'El Torito img path : 1 /isolinux/isolinux.bin\n',
                    report.replace('BIOS', 'UEFI'),
                    report.replace('/images/efiboot.img', '/other.img'),
                    report.replace('MBR cyl-align-off GPT', 'MBR')]:
            with self.subTest(report=bad):
                try:
                    allowed = builder.hidden_bios_keep(bad, error)
                except ValueError:
                    allowed = False
                self.assertFalse(allowed)

    def test_hybrid_partition_scheme_cannot_silently_disappear(self):
        first = 'System area summary: MBR isohybrid cyl-align-off GPT\n'
        same = 'System area summary: MBR isohybrid GPT\n'
        lost = 'System area summary: MBR isohybrid\n'
        self.assertEqual(builder.system_signature(first), builder.system_signature(same))
        self.assertNotEqual(builder.system_signature(first), builder.system_signature(lost))
        with self.assertRaises(ValueError):
            builder.system_signature('no system area\n')

    def test_hidden_bios_uses_the_current_menu_directory(self):
        loader = bytearray(2048)
        loader[:8] = bytes.fromhex('faea6c7c00009090')
        struct.pack_into('<4I', loader, 8, 5000, 5500, 2048, 7)
        struct.pack_into('<I', loader, 64, 7)
        updated = builder.updated_hidden_bios(bytes(loader), 5500)
        self.assertEqual(struct.unpack_from('<I', updated, 8)[0], 16)
        self.assertEqual(updated[:8], loader[:8])
        self.assertEqual(updated[12:], loader[12:])
        for offset in (0, 16, 20, 64):
            bad = bytearray(loader); bad[offset] ^= 255
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                builder.updated_hidden_bios(bytes(bad), 5500)
        with self.assertRaises(ValueError):
            builder.updated_hidden_bios(bytes(loader), 5501)


if __name__ == '__main__':
    unittest.main()
