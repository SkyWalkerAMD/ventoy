#!/usr/bin/env python3
"""Enable installer-only KMS fallback without changing installation choices."""
import hashlib
import re
from pathlib import PurePosixPath

PARAMETER = 'nomodeset'
CHOICES = (
    ('install', 'AST/BMC display compatibility (install only)'),
    ('installed', 'AST/BMC display compatibility (keep after install)'),
)
KERNEL = re.compile(r'(?:^|/)(?:hwe-)?vmlinuz(?:[-.][A-Za-z0-9._+-]+)?$')
GRUB = re.compile(r'^(\s*(?:linux|linuxefi|linux16)\s+)(\S+)(.*)$')
APPEND = re.compile(r'^(\s*append\s+)(.*)$', re.IGNORECASE)


def insert_parameter(arguments, parameter=PARAMETER):
    # Insert before Debian/Ubuntu's --- separator so this additional option is
    # not intentionally requested as an installed-system bootloader setting.
    # Keeping all existing bytes also preserves escaped volume labels.
    if any(c in arguments for c in ('\n', '\r', ';', '#', '`')) or arguments.rstrip().endswith('\\'):
        raise ValueError('unsupported compound or continued boot command')
    words = arguments.split()
    if any(w.startswith(('nomodeset=', 'modeset=')) for w in words):
        raise ValueError('conflicting display parameter requires review')
    if all(word in words for word in parameter.split()):
        return arguments
    separator = re.search(r'(?<!\S)(?:---|--)(?!\S)', arguments)
    if separator:
        pos = separator.start()
        return arguments[:pos] + parameter + ' ' + arguments[pos:]
    trailing = len(arguments) - len(arguments.rstrip(' \t'))
    end = len(arguments) - trailing
    if not end:
        return (arguments or ' ') + parameter
    return arguments[:end] + ' ' + parameter + arguments[end:]


def patch_config(original, kind):
    if kind not in ('grub', 'syslinux'):
        raise ValueError('unknown boot menu kind')
    text = original.decode('utf-8')
    if '\x00' in text or '\r' in text:
        raise ValueError('unsupported boot configuration encoding')
    output, changed, matched = [], 0, 0
    kernel = None
    for raw in text.splitlines(keepends=True):
        ending = '\n' if raw.endswith('\n') else ''
        line = raw[:-1] if ending else raw
        if kind == 'grub':
            match = GRUB.fullmatch(line)
            if match and KERNEL.search(match[2]):
                matched += 1
                updated = match[1] + match[2] + insert_parameter(match[3])
                changed += updated != line
                line = updated
        else:
            if re.match(r'^\s*label\s+', line, re.IGNORECASE):
                kernel = None
            match = re.fullmatch(r'\s*(?:kernel|linux)\s+(\S+)\s*', line, re.IGNORECASE)
            if match:
                kernel = match[1]
            match = APPEND.fullmatch(line)
            if match and kernel and KERNEL.search(kernel):
                if not re.search(r'(?:^|\s)initrd=\S+', match[2]):
                    raise ValueError('installer APPEND has no explicit initrd')
                matched += 1
                updated = match[1] + insert_parameter(match[2])
                changed += updated != line
                line = updated
        output.append(line + ending)
    return ''.join(output).encode(), {'matched': matched, 'changed': changed}


def compatibility_choices(original, kind):
    """Keep vendor entries and append two explicit clones of the primary install."""
    _, counts = patch_config(original, kind)
    text = original.decode('utf-8')
    if not counts['matched']:
        return original, {'entries_added': 0}
    if 'ventoy.bmc=' in text or 'ventoy-bmc-install' in text:
        raise ValueError('expected a source menu without managed AST/BMC choices')
    entries = []
    if kind == 'grub':
        # Primary entries have a simple standalone body. Leave advanced,
        # rescue and multi-branch entries (e.g. the TPM fallback) untouched.
        for entry in re.finditer(r'(?m)^menuentry [^\n]+\{\n((?:[ \t][^\n]*\n)+)\}\s*$', text):
            body = entry[1]
            commands = body.splitlines()
            kernels = [GRUB.fullmatch(line) for line in commands]
            kernels = [m for m in kernels if m and KERNEL.search(m[2])]
            if (len(kernels) != 1 or not any(re.match(r'^\s*initrd(?:efi|16)?\s', line) for line in commands)
                    or not all(re.match(r'^\s*(?:set |echo |linux(?:efi|16)?\s|initrd(?:efi|16)?\s)', line)
                               for line in commands)):
                continue
            args = kernels[0][3].split()
            if (PARAMETER in args or 'rd.live.check' in args or
                    any(word.startswith(('inst.rescue', 'rescue', 'auto=true')) for word in args)):
                continue
            # Debian's text installer is the fallback when the graphical
            # installer cannot use the firmware framebuffer.
            entries.append((any('/gtk/initrd' in line for line in commands), body, kernels[0]))
        if not entries:
            return original, {'entries_added': 0}
        _, body, kernel = min(entries, key=lambda entry: entry[0])
        clones = []
        for mode, title in CHOICES:
            cmd = kernel[1] + kernel[2] + insert_parameter(kernel[3], f'{PARAMETER} ventoy.bmc={mode}')
            clones.append(f"menuentry '{title}' --id ventoy-bmc-{mode} {{\n" +
                          body.replace(kernel[0] + '\n', cmd + '\n', 1) + '}\n')
    else:
        primary = re.search(r'(?im)^[ \t]*label[ \t]+(?:linux|install|live)[ \t]*\n'
                            r'((?:(?![ \t]*(?:label|menu begin|menu end)\b)[^\n]*\n?)*)', text)
        if not primary:
            return original, {'entries_added': 0}
        kernel = re.search(r'(?im)^[ \t]*(?:kernel|linux)[ \t]+(\S+)[ \t]*$', primary[1])
        params = re.search(r'(?im)^[ \t]*append[ \t]+([^\n]+)$', primary[1])
        if not kernel or not KERNEL.search(kernel[1]) or not params or PARAMETER in params[1].split():
            raise ValueError('expected a normal Syslinux install entry')
        if re.search(r'(?im)^default[ \t]+live[ \t]*$', text) and not re.search(r'(?im)^ui[ \t]', text):
            # Ubuntu's legacy menu already ships vesamenu.c32. Use it so the
            # two labels can be selected with the keyboard as well as typed.
            text = 'ui vesamenu.c32\n' + text
        clones = [
            f'label ventoy-bmc-{mode}\n  menu label {title}\n'
            f'  kernel {kernel[1]}\n  append {insert_parameter(params[1], f"{PARAMETER} ventoy.bmc={mode}")}\n'
            for mode, title in CHOICES
        ]
    return (text.rstrip('\n') + '\n\n' + '\n'.join(clones)).encode(), {'entries_added': len(clones)}


def menu_kind(path):
    path = PurePosixPath(path)
    if path.suffix != '.cfg':
        return None
    text = path.as_posix()
    if text.startswith(('/boot/grub/', '/boot/grub2/', '/EFI/')):
        return 'grub'
    if text.startswith(('/isolinux/', '/syslinux/')):
        return 'syslinux'
    return None


def patch_checksums(original, changes, algorithm):
    """Update only original manifest records referring to changed files."""
    output = []
    for raw in original.decode('utf-8').splitlines(keepends=True):
        match = re.fullmatch(r'([a-fA-F0-9]+)([ \t]+)(\*?)(\./)?([^\n]+)(\n?)', raw)
        if match:
            path = '/' + match[5].lstrip('/')
            if path in changes:
                before, after = changes[path]
                if match[1].lower() != hashlib.new(algorithm, before).hexdigest():
                    raise ValueError('original media checksum mismatch: ' + path)
                raw = hashlib.new(algorithm, after).hexdigest() + raw[len(match[1]):]
        output.append(raw)
    return ''.join(output).encode()


def patch_treeinfo(original, changes):
    output, section = [], ''
    for raw in original.decode('utf-8').splitlines(keepends=True):
        if raw.strip().startswith('['):
            section = raw.strip()
        match = re.fullmatch(r'(\s*([^=]+?)\s*=\s*)([a-z0-9]+):([a-fA-F0-9]+)(\s*\n?)', raw)
        if section == '[checksums]' and match:
            path = '/' + match[2].strip().lstrip('/')
            if path in changes:
                before, after = changes[path]
                if hashlib.new(match[3], before).hexdigest() != match[4].lower():
                    raise ValueError('original treeinfo checksum mismatch: ' + path)
                raw = match[1] + match[3] + ':' + hashlib.new(match[3], after).hexdigest() + match[5]
        output.append(raw)
    return ''.join(output).encode()
