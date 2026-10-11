"""Reject generated commands that use tools or flags this Mac's man pages do not define."""

import functools
import os
import re
import shlex
import shutil
import subprocess

BUILTINS = {'cd', 'killall', 'echo', 'for', 'do', 'done', 'if', 'then', 'fi', 'while', 'export',
            'read', 'test', '[', 'printf', 'true', 'false', 'set', 'unset', 'alias', 'source', '.'}
WRAPPERS = {'sudo', 'xargs', 'time', 'nohup', 'env', 'command', 'exec'}
SEPARATORS = {'|', '&&', '||', ';', '|&'}
EXEC_FLAGS = {'-exec', '-execdir', '-ok', '-okdir'}
SYSTEM_PATHS = ('/proc/', '/sys/', '/etc/', '/var/log/', '/usr/', '/dev/')


@functools.lru_cache(maxsize=None)
def _man_text(cmd: str) -> str:
    try:
        out = subprocess.run(['man', cmd], capture_output=True, text=True, timeout=5,
                             env={'MANPAGER': 'cat', 'PAGER': 'cat', 'PATH': '/usr/bin:/bin'}).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ''
    return re.sub(r'.\x08', '', out)


@functools.lru_cache(maxsize=None)
def _documented(cmd: str) -> frozenset[str]:
    """Flags defined in the man page: SYNOPSIS groups like [-jnRu] plus option-definition lines."""
    text = _man_text(cmd)
    syn = text.split('DESCRIPTION')[0]
    flags = set()
    for group in re.findall(r'\[-([A-Za-z0-9]+)', syn):
        flags.update('-' + c for c in group)
    for m in re.finditer(r'^\s{3,8}(-{1,2}[A-Za-z][\w-]*)', text, re.M):
        flags.add(m.group(1))
        if not m.group(1).startswith('--'):
            flags.add('-' + m.group(1)[1:2])
    flags.update(re.findall(r'(?<![\w-])(-{1,2}[A-Za-z][\w-]*)', syn))
    return frozenset(flags)


def _segments(tokens: list[str]) -> list[list[str]]:
    segments, current = [], []
    for token in tokens:
        if token in SEPARATORS or token.endswith(';'):
            if token.endswith(';') and token not in SEPARATORS:
                current.append(token[:-1])
            segments.append(current)
            current = []
        else:
            current.append(token)
    segments.append(current)
    return segments


def problems(command: str) -> list[str]:
    """Return reasons the command will not run as written on this Mac; empty means no finding."""
    found = []
    if re.search(r"\bsed\s+(-[a-zA-Z]*\s+)*-i\s+(?!''|\"\"|-e|\S*\.bak)", command):
        found.append("BSD sed -i needs a suffix argument: sed -i ''")
    try:
        tokens = shlex.split(command)
    except ValueError:
        return ['command could not be parsed']
    for segment in _segments(tokens):
        while segment and segment[0] in ('do', 'then', 'else', '!'):
            segment.pop(0)
        while segment and (segment[0] in WRAPPERS or re.match(r'^\w+=', segment[0])):
            wrapper = segment.pop(0)
            if wrapper in ('xargs', 'sudo'):
                while segment and segment[0].startswith('-'):
                    segment.pop(0)
        if not segment:
            continue
        cmd = segment[0]
        if cmd in BUILTINS or '/' in cmd and shutil.which(cmd):
            continue
        if not shutil.which(cmd):
            found.append(f'{cmd}: not installed on macOS')
            continue
        for arg in segment[1:]:
            if arg.startswith(SYSTEM_PATHS) and not re.search(r'[*?\[{$]', arg) and not os.path.exists(arg):
                found.append(f'{arg}: path does not exist on macOS')
        if cmd == 'sysctl':
            for arg in segment[1:]:
                if re.fullmatch(r'[a-z][\w.]*[a-z0-9]', arg) and subprocess.run(
                        ['sysctl', '-N', arg], capture_output=True).returncode:
                    found.append(f'sysctl {arg}: unknown key')
        man = _man_text(cmd)
        if not man:
            continue
        args = segment[1:]
        for index, arg in enumerate(args):
            if arg in EXEC_FLAGS:
                args = args[:index]
                break
        documented = _documented(cmd)
        for arg in args:
            if arg.startswith('--') and len(arg) > 2:
                option = arg.split('=')[0]
                if option not in documented and option not in man:
                    found.append(f'{cmd} {option}: not in man page')
            elif re.fullmatch(r'-[a-zA-Z]{3,}', arg) and cmd == 'find':
                if arg not in man and not arg.startswith('-newer'):
                    found.append(f'{cmd} {arg}: not in man page')
            elif re.fullmatch(r'-[a-zA-Z]{1,4}', arg):
                bad = [f'-{c}' for c in arg[1:] if f'-{c}' not in documented]
                if bad and arg not in documented:
                    found.append(f'{cmd} {" ".join(bad)}: not in man page')
            elif re.match(r'-[a-zA-Z]', arg) and arg[:2] not in documented and arg not in documented:
                found.append(f'{cmd} {arg[:2]}: not in man page')
    return found

