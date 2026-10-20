"""Reject generated commands that use tools or flags this Mac's man pages do not define."""

import functools
import os
import posixpath
import re
import shlex
import shutil
import subprocess

from .shell import parse

BUILTINS = {':', 'cd', 'killall', 'echo', 'for', 'do', 'done', 'if', 'then', 'fi', 'while', 'export',
            'read', 'test', '[', 'printf', 'true', 'false', 'set', 'unset', 'alias', 'source', '.'}
NO_FLAG_CHECK = {'zsh', 'bash', 'sh', 'dash', 'ksh', 'perl', 'python', 'python3', 'ruby', 'node'}  # option sets live in other man pages
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
    for m in re.finditer(r'^\s{3,16}(-.*)$', text, re.M):
        spec = re.split(r'\s{2,}', m.group(1))[0]  # "-R, -r, --recursive" and "-n <number>" lines
        for flag in re.findall(r'(?<![\w-])-{1,2}[A-Za-z][\w-]*', spec):
            flags.add(flag)
            if not flag.startswith('--'):
                flags.add('-' + flag[1:2])
    flags.update(re.findall(r'(?<![\w-])(-{1,2}[A-Za-z][\w-]*)', syn))
    return frozenset(flags)


@functools.lru_cache(maxsize=None)
def _ps_known() -> frozenset[str]:
    """Keywords this Mac's `ps -L` lists; `ps -o` accepts only these."""
    try:
        out = subprocess.run(['ps', '-L'], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return frozenset()
    return frozenset(out.split())


def _ps_keywords(args: list[str]) -> list[str]:
    """Keywords named after -o/-O, e.g. `-o pid,comm=NAME` -> pid, comm."""
    found = []
    for index, arg in enumerate(args):
        value = args[index + 1] if arg in ('-o', '-O') and index + 1 < len(args) else (
            arg[2:] if re.match(r'-\w*[oO]\S', arg) and not arg.startswith('--') else '')
        found += [k.split('=')[0] for k in value.split(',') if k.split('=')[0]]
    return found


def problems(command: str) -> list[str]:
    """Return reasons the command will not run as written on this Mac; empty means no finding."""
    found = []
    if re.search(r'\{\{.*?\}\}', command):
        found.append('unfilled {{placeholder}} in command')
    if re.search(r"\bsed\s+(-[a-zA-Z]*\s+)*-i\s+(?!''|\"\"|-e|\S*\.bak)", command):
        found.append("BSD sed -i needs a suffix argument: sed -i ''")
    try:
        commands = parse(command)
    except ValueError as error:
        return [str(error)]
    for parsed in commands:
        for wrapper in parsed.wrappers:
            if not shutil.which(wrapper.value) and not wrapper.value.startswith(('./', '~/')):
                found.append(f'{wrapper.value}: wrapper is not installed on macOS')
        if parsed.lookup:
            continue
        segment = [word.value for word in parsed.words]
        if not segment:
            continue
        cmd = parsed.name
        if cmd in BUILTINS and '/' not in segment[0]:
            continue
        if not shutil.which(segment[0]) and not segment[0].startswith(('./', '~/')):
            found.append(f'{cmd}: not installed on macOS')
            continue
        for arg in segment[1:]:
            if arg.startswith(SYSTEM_PATHS) and not re.search(r'[*?\[{$]', arg) and not os.path.exists(arg):
                found.append(f'{arg}: path does not exist on macOS')
        if cmd == 'ps':
            known = _ps_known()
            for keyword in _ps_keywords(segment[1:]):
                if known and keyword not in known:
                    found.append(f'ps {keyword}: not a ps keyword on macOS')
        if cmd == 'sysctl':
            for arg in segment[1:]:
                if re.fullmatch(r'[a-z][\w.]*[a-z0-9]', arg) and subprocess.run(
                        ['sysctl', '-N', arg], capture_output=True).returncode:
                    found.append(f'sysctl {arg}: unknown key')
        args = segment[1:]
        page = cmd
        if args and re.fullmatch(r'[a-z][a-z0-9-]*', args[0]) and _man_text(f'{cmd}-{args[0]}'):
            page, args = f'{cmd}-{args[0]}', args[1:]  # git log -> man git-log
        man = _man_text(page)
        if not man or cmd in NO_FLAG_CHECK:
            continue
        documented = _documented(page)
        for arg in args:
            if cmd == 'chmod' and re.fullmatch(r'[ugoa]*[-+=][rwxXst]+(,[ugoa]*[-+=][rwxXst]+)*', arg):
                continue  # a symbolic mode such as -w, not an option
            if arg == '-r' and cmd in ('cp', 'rm') and '-R' in documented:
                continue  # traditional alias of -R
            if len(arg) > 2 and arg[0] == '-' and re.search(
                    r'(?<![\w-])' + re.escape(arg.split('=')[0]) + r'(?![\w-])', man):
                continue  # the whole option, e.g. -nobrowse or --nwi, is documented
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



BROAD_TARGETS = {'/', '~', '*', '.', '..', '~/', './', '/*', '~/*'}
DELETERS = {'rm', 'rmdir', 'unlink', 'shred', 'trash'}


def _named_targets(request: str, path: str | None) -> set[str]:
    """Only complete lexical names; ambiguous prose can use the explicit path input."""
    try:
        names = shlex.split(request)
    except ValueError:
        names = []
    names = [name.rstrip(',;:!?') for name in names]
    if path is not None:
        names.append(path)
    return {name[2:] if name.startswith('./') else name for name in names}


def unrequested_deletion(command: str, request: str, path: str | None = None) -> list[str]:
    """Align recognized deletion operands with named targets; this does not infer intent."""
    try:
        commands = parse(command)
    except ValueError as error:
        return [str(error)]
    named = _named_targets(request, path)
    found = []
    changed_directory = False
    for parsed in commands:
        cmd = parsed.name
        if parsed.lookup:
            continue
        if cmd == 'cd':
            changed_directory = True
        args = parsed.words[1:]
        if cmd not in DELETERS:
            continue
        if parsed.indirect:
            found.append('deletion through find or xargs is unsupported')
            continue
        targets = []
        options = True
        allowed = {'rm': 'dfiIPRrvW', 'rmdir': 'v', 'unlink': '', 'shred': '', 'trash': ''}[cmd]
        for word in args:
            value = word.value
            if options and value == '--':
                options = False
                continue
            if options and value.startswith('-') and value != '-':
                if value.startswith('--') or not value[1:] or any(c not in allowed for c in value[1:]):
                    found.append(f'{cmd}: unsupported deletion option {value}')
                continue
            options = False
            targets.append(word)
        if not targets:
            found.append(f'{cmd}: deletion requires an explicit literal target')
        if cmd == 'unlink' and len(targets) != 1:
            found.append('unlink requires exactly one target')
        for word in targets:
            target = word.value
            canonical = target[2:] if target.startswith('./') else target
            # Normalize only to reject broad scopes, never to grant target equivalence.
            broad = posixpath.normpath(re.sub(r'/+', '/', canonical)) in {'/', '.', '..', '~'}
            if (not target or canonical in BROAD_TARGETS or broad or word.dynamic or
                    target.startswith('~') and not word.home or
                    changed_directory and not target.startswith('/') and not word.home or
                    canonical not in named):
                found.append(f'deletes {target}, which is not an unambiguous named literal target')
    return found


def validation_findings(command: str, request: str, path: str | None = None, *, safety=None) -> dict[str, list[str]]:
    """One serving/data acceptance boundary; categories retain dataset rejection evidence."""
    if not isinstance(command, str) or not command.strip() or len(command) > 4096 or any(c in command for c in '\x00\r\n'):
        return {'invalid_command': ['invalid generated command']}
    if (not isinstance(request, str) or not request.strip() or len(request) > 2000 or
            any(c in request for c in '\x00\r\n') or
            path is not None and (not isinstance(path, str) or not path.strip() or
                                  len(path) > 8192 or any(ord(c) < 32 or 127 <= ord(c) < 160 for c in path))):
        return {'invalid_command': ['invalid request or explicit path']}
    if safety is None:
        from whatisit import safety
    findings = safety.check(command)
    result = {
        'danger': [reason for severity, reason in findings if severity == 'DANGER'],
        'macos_lint': problems(command),
        'deletion_guard': unrequested_deletion(command, request, path),
        'placeholder': [f'{m.group(0)!r} is a placeholder, not something you named'
                        for m in safety.PLACEHOLDER_HINT.finditer(command)
                        if m.group(0).casefold() not in request.casefold() and
                        (path is None or m.group(0) not in path)],
    }
    return {category: reasons for category, reasons in result.items() if reasons}


def validation_issues(command: str, request: str, path: str | None = None, *, safety=None) -> list[str]:
    return [reason for reasons in validation_findings(command, request, path, safety=safety).values()
            for reason in reasons]
