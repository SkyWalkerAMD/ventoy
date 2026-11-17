#!/usr/bin/env python3
"""Enable installer-only KMS fallback without changing installation choices."""
import hashlib
import re
from pathlib import PurePosixPath

PARAMETER = 'nomodeset'
KERNEL = re.compile(r'(?:^|/)(?:hwe-)?vmlinuz(?:[-.][A-Za-z0-9._+-]+)?$')
GRUB = re.compile(r'^(\s*(?:linux|linuxefi|linux16)\s+)(\S+)(.*)$')
APPEND = re.compile(r'^(\s*append\s+)(.*)$', re.IGNORECASE)


def insert_parameter(arguments):
    # Insert before Debian/Ubuntu's --- separator so this additional option is
    # not intentionally requested as an installed-system bootloader setting.
    # Keeping all existing bytes also preserves escaped volume labels.
    words = arguments.split()
    if PARAMETER in words:
        return arguments
    if any(w.startswith(('nomodeset=', 'modeset=')) for w in words):
        raise ValueError('conflicting display parameter requires review')
    if any(c in arguments for c in ('\n', '\r', ';', '#', '`')) or arguments.rstrip().endswith('\\'):
        raise ValueError('unsupported compound or continued boot command')
    separator = re.search(r'(?<!\S)(?:---|--)(?!\S)', arguments)
    if separator:
        pos = separator.start()
        return arguments[:pos] + PARAMETER + ' ' + arguments[pos:]
    trailing = len(arguments) - len(arguments.rstrip(' \t'))
    end = len(arguments) - trailing
    if not end:
        return (arguments or ' ') + PARAMETER
    return arguments[:end] + ' ' + PARAMETER + arguments[end:]


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


def menu_kind(path):
    path = PurePosixPath(path)
    if path.suffix != '.cfg':
        return None
    text = path.as_posix()
    if text.startswith(('/boot/grub/', '/EFI/')):
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
