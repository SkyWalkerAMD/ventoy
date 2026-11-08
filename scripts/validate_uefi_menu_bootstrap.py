"""Validate bootstrap input boundaries and refusal paths without network or a VM."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('menu_bootstrap', ROOT / 'tools/uefi-menu-bootstrap/build.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class BootstrapTests(unittest.TestCase):
    def test_only_selected_nic_and_menu(self):
        script = bootstrap.render_script('02:00:00:AB:CD:EF', 'http://pxe.example.test:16000/hboot/loader/menu.efi')
        self.assertIn('02:00:00:ab:cd:ef', script)
        self.assertEqual(script.count('dhcp ${target}'), 1)
        self.assertEqual(script.count('\nchain '), 1)
        self.assertLess(script.index('\nimgfree\n'), script.index('\nchain '))
        for prohibited in ('autoinstall', 'kickstart', 'kernel ', 'initrd ', 'sanboot ', 'autoexec.ipxe'):
            self.assertNotIn(prohibited, script)
        self.assertIn('goto failed\n:have_nic', script)

    def test_rejects_mac_or_url_script_injection(self):
        for mac in ('', '00:00:00:00:00:00', 'ff:ff:ff:ff:ff:ff', '01:00:00:00:00:01', '02:00:00:00:00:01\nboot', '${net0/mac}'):
            with self.subTest(mac=mac), self.assertRaises(ValueError):
                bootstrap.render_script(mac, 'http://pxe.example.test/menu.efi')
        for url in ('http://user:pass@pxe.example.test/menu.efi', 'http://pxe.example.test/menu.efi\nboot',
                    'http://pxe.example.test/${filename}.efi', 'http://pxe.example.test/menu.efi?token=secret',
                    'http://pxe.example.test:70000/menu.efi', 'http://pxe.example.test/../menu.efi',
                    'file:///menu.efi', 'http://pxe.example.test/menu.ipxe', 'http://pxe.example.test/"menu".efi'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                bootstrap.render_script('02:00:00:00:00:01', url)

    def test_source_commit_and_local_changes_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            with patch.object(bootstrap.subprocess, 'check_output', return_value='b' * 40 + '\n'):
                with self.assertRaisesRegex(ValueError, 'does not match'):
                    bootstrap.checked_source(source, 'a' * 40)
            with patch.object(bootstrap.subprocess, 'check_output', side_effect=['a' * 40 + '\n', '?? src/config/local/usb.h\n']):
                with self.assertRaisesRegex(ValueError, 'must be clean'):
                    bootstrap.checked_source(source, 'a' * 40)
            (source / 'src/config/local').mkdir(parents=True)
            (source / 'src/Makefile').write_text('# fixture\n')
            (source / 'src/config/local/usb.h').write_text('#define USB_HCD_XHCI\n')
            with patch.object(bootstrap.subprocess, 'check_output', side_effect=['a' * 40 + '\n', '']):
                with self.assertRaisesRegex(ValueError, 'ignored iPXE local configuration'):
                    bootstrap.checked_source(source, 'a' * 40)

    def test_existing_output_or_wrong_iso_never_executes_a_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = root / 'fixture.iso'
            base.write_bytes(b'fixture only')
            args = argparse.Namespace(mac='02:00:00:00:00:01', loader_url='http://pxe.example.test/menu.efi',
                                      ipxe_source=root, ipxe_commit='a' * 40, base_iso=base,
                                      base_iso_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),
                                      output=root, preserve_firmware_usb=True, jobs=2)
            with patch.object(bootstrap.subprocess, 'run') as run, patch.object(bootstrap.subprocess, 'check_output') as read:
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    bootstrap.build(args)
                args.output = root / 'new-output'
                args.base_iso_sha256 = '0' * 64
                with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                    bootstrap.build(args)
                run.assert_not_called()
                read.assert_not_called()
                self.assertFalse(args.output.exists())


if __name__ == '__main__':
    unittest.main()
