"""A deliberately bounded shell grammar for static command inspection."""

from dataclasses import dataclass
from functools import lru_cache
import os
import re


@dataclass(frozen=True)
class Word:
    value: str
    dynamic: bool = False
    home: bool = False


@dataclass(frozen=True)
class Command:
    words: tuple[Word, ...]
    redirects: tuple[Word, ...] = ()
    indirect: bool = False
    lookup: bool = False
    wrappers: tuple[Word, ...] = ()

    @property
    def name(self) -> str:
        return os.path.basename(self.words[0].value)


@dataclass(frozen=True)
class _Token:
    word: Word
    quoted: bool = False
    assignment: bool = False


_REDIRECT = re.compile(r'\d*(?:>>|<>|>&|<&|>\||>|<)')
_NUMERIC_GLOB = re.compile(r'<[0-9]*-[0-9]*>')
_ASSIGNMENT = re.compile(r'([A-Za-z_][A-Za-z_0-9]*)=')
# Exact read-only, argument-fixed substitutions; anything else stays unsupported.
_SAFE_SUBSTITUTION = re.compile(
    r'\$\((?:pwd(?: -P)?|whoami|tty|id -(?:un|u|gn|g)|uname(?: -[mrsn])?'
    r'|sw_vers(?: -(?:productVersion|buildVersion|productName))?|date(?: \+[A-Za-z0-9%:_.-]+)?)\)')
_STATE = {'PATH', 'HOME', 'IFS', 'ENV', 'BASH_ENV', 'SHELLOPTS', 'BASHOPTS', 'CDPATH',
          'ZDOTDIR', 'FPATH', 'GLOBIGNORE'}
_RESERVED = {'if', 'then', 'else', 'elif', 'fi', 'for', 'while', 'until', 'do',
             'done', 'case', 'esac', 'in', 'function', 'select', 'coproc', '!',
             '{', '}', '[[', ']]', 'repeat', 'foreach', 'end'}
_SHELLS = {'sh', 'bash', 'zsh', 'dash', 'ksh', 'csh', 'tcsh', 'fish'}
_WRAPPERS = {'sudo', 'env', 'command', 'exec', 'nohup', 'time', 'xargs'}
_UNSUPPORTED_WRAPPERS = {'nice', 'caffeinate', 'arch', 'builtin', 'doas', 'busybox',
                         'toybox', 'timeout', 'ionice', 'stdbuf', 'setsid', 'chroot',
                         'xcrun', 'taskpolicy'}
_FIND_EXEC = {'-exec', '-execdir', '-ok', '-okdir'}
_FIND_VALUE = {'-f', '-name', '-iname', '-path', '-ipath', '-regex', '-iregex',
               '-lname', '-ilname', '-type', '-xtype', '-size', '-user', '-group',
               '-uid', '-gid', '-inum', '-links', '-perm', '-flags', '-fstype',
               '-mtime', '-atime', '-ctime', '-Btime', '-mmin', '-amin', '-cmin',
               '-Bmin', '-newer', '-anewer', '-cnewer', '-samefile', '-since',
               '-maxdepth', '-mindepth'}
_FIND_FLAGS = {'-H', '-L', '-P', '-E', '-X', '-d', '-s', '-x', '-a', '-and',
               '-o', '-or', '-not', '!', '(', ')', '-print', '-print0', '-ls',
               '-empty', '-prune', '-quit', '-true', '-false', '-depth', '-mount',
               '-xdev', '-follow', '-daystart', '-nouser', '-nogroup', '-acl',
               '-xattr', '-sparse', '-readable', '-writable', '-executable'}


def _lex(command: str) -> list[_Token | str]:
    if any(c in command for c in '\n\r\x00'):
        raise ValueError('newlines and NUL bytes are outside the supported shell grammar')
    tokens = []
    i = 0
    while i < len(command):
        if command[i].isspace():
            i += 1
            continue
        if _NUMERIC_GLOB.match(command, i):
            raise ValueError('zsh numeric glob expansion is not supported')
        if command.startswith(('<<', '<<<'), i):
            raise ValueError('here-documents and here-strings are not supported')
        redirect = _REDIRECT.match(command, i)
        if redirect:
            tokens.append(redirect[0])
            i = redirect.end()
            continue
        if command[i] in '|;&':
            op = next((op for op in ('&&', '||', '|&') if command.startswith(op, i)), command[i])
            tokens.append(op)
            i += len(op)
            continue
        assignment = bool(_ASSIGNMENT.match(command, i))
        value, quoted, dynamic, home = [], False, False, False
        quote = ''
        while i < len(command):
            c = command[i]
            if not quote and _NUMERIC_GLOB.match(command, i):
                raise ValueError('zsh numeric glob expansion is not supported')
            if not quote and (c.isspace() or c in '|;&<>'):
                break
            if c == "'" and quote != '"':
                quote = '' if quote else "'"
                quoted = True
                i += 1
                continue
            if c == '"' and quote != "'":
                quote = '' if quote else '"'
                quoted = True
                i += 1
                continue
            if c == '\\' and quote != "'":
                if i + 1 == len(command):
                    raise ValueError('trailing shell escape')
                if quote == '"' and command[i + 1] not in '$`"\\':
                    value.append(c)
                    i += 1
                    continue
                value.append(command[i + 1])
                quoted = True
                i += 2
                continue
            if quote != "'" and c == '!' and i + 1 < len(command) and (
                    not command[i + 1].isspace() and command[i + 1] not in '=('):
                raise ValueError('interactive shell history expansion is not supported')
            if quote != "'" and c == '`':
                raise ValueError('executable backtick substitution is not supported')
            if quote != "'" and c == '$':
                safe = _SAFE_SUBSTITUTION.match(command, i)
                if safe:
                    value.append(safe[0])
                    dynamic = True
                    i += len(safe[0])
                    continue
                if command.startswith('$(', i):
                    raise ValueError('command and arithmetic substitution are not supported')
                variable = re.match(r'\$(?:[A-Za-z_][A-Za-z_0-9]*|\{[A-Za-z_][A-Za-z_0-9]*\})', command[i:])
                if variable:
                    value.append(variable[0])
                    dynamic = True
                    i += len(variable[0])
                    continue
                if i + 1 < len(command) and command[i + 1] in "{0123456789@*#?$!-\"'":
                    raise ValueError('complex parameter or special shell expansion is not supported')
            if not quote:
                if c in '()' or c == '#' and not value:
                    raise ValueError('grouping, process substitution, and shell comments are not supported')
                if c in '{}':
                    # find's literal placeholder is data, unlike brace expansion/grouping.
                    if command.startswith('{}', i):
                        value.append('{}')
                        i += 2
                        continue
                    raise ValueError('brace expansion and shell grouping are not supported')
                dynamic |= c in '*?[' or c == '=' and not value
                if c == '~' and not value:
                    if i + 1 < len(command) and command[i + 1] not in '/ \t|;&<>':
                        raise ValueError('named-user home expansion is not supported')
                    home = True
            value.append(c)
            i += 1
        if quote:
            raise ValueError('unterminated shell quote')
        literal = ''.join(value)
        tokens.append(_Token(Word(literal, dynamic and literal != '[', home), quoted, assignment))
    return tokens


def _assignment(token: _Token, env: bool = False) -> bool:
    if not env and not token.assignment:
        return False
    match = _ASSIGNMENT.match(token.word.value)
    if not match:
        return False
    if token.word.dynamic or token.word.home:
        raise ValueError('dynamic environment assignments are not supported')
    if match[1] in _STATE or match[1].startswith(('LD_', 'DYLD_')):
        raise ValueError(f'{match[1]} assignment changes shell or executable resolution')
    return True


def _replaced(words: list[_Token], placeholder: str) -> list[_Token]:
    return [_Token(Word(t.word.value, t.word.dynamic or placeholder in t.word.value,
                        t.word.home), t.quoted, t.assignment) for t in words]


def _commands(words: list[_Token], redirects: tuple[Word, ...], indirect: bool = False,
              depth: int = 0, wrappers: tuple[Word, ...] = ()) -> list[Command]:
    if depth > 16:
        raise ValueError('too many nested command wrappers')
    while words and _assignment(words[0]):
        words = words[1:]
    if not words:
        if redirects:
            return [Command((Word(':'),), redirects, indirect, wrappers=wrappers)]
        raise ValueError('expected a command after assignments or wrapper')
    first = words[0]
    if first.word.dynamic or first.word.home or not first.word.value:
        raise ValueError('dynamic or empty command names are not supported')
    name = os.path.basename(first.word.value)
    if name in _UNSUPPORTED_WRAPPERS:
        raise ValueError(f'unsupported execution wrapper: {name}')
    if name == 'launchctl' and (
            len(words) < 2 and indirect or len(words) > 1 and (
                words[1].word.dynamic or words[1].word.value in {'asuser', 'bsexec', 'submit'})):
        raise ValueError('launchctl execution and dynamic subcommands are not supported')
    if not first.quoted and first.word.value in _RESERVED:
        raise ValueError('shell compound and control syntax is not supported')
    if name in _SHELLS or name in {'eval', 'source', '.', 'set', 'unset', 'alias',
                                  'unalias', 'export', 'read', 'typeset', 'declare',
                                  'local', 'builtin', 'enable', 'hash', 'trap', 'fc',
                                  'autoload', 'functions', 'unfunction', 'rehash',
                                  'unhash', 'zmodload', 'emulate', 'setopt', 'unsetopt'}:
        raise ValueError('shell interpreters and shell-state builtins are not supported')
    if name in _WRAPPERS:
        rest = words[1:]
        lookup = False
        placeholder = ''
        while rest:
            flag = rest[0].word.value
            if flag == '--':
                rest = rest[1:]
                break
            if name == 'env' and _assignment(rest[0], env=True):
                rest = rest[1:]
                continue
            if not flag.startswith('-') or flag == '-':
                break
            if rest[0].word.dynamic:
                raise ValueError(f'dynamic {name} options are not supported')
            takes_value = False
            if name == 'sudo':
                valid = bool(re.fullmatch(r'-[nEHSkK]+', flag))
                takes_value = flag in ('-u', '-g')
                valid |= takes_value or bool(re.fullmatch(r'-[ug].+', flag))
            elif name == 'env':
                valid = flag == '-i'
            elif name == 'command':
                valid = bool(re.fullmatch(r'-[pvV]+', flag))
                lookup |= 'v' in flag or 'V' in flag
            elif name == 'time':
                valid = flag == '-p'
            elif name == 'xargs':
                takes_value = flag in ('-I', '-J', '-L', '-n', '-P', '-s', '-R', '-S', '-E')
                valid = takes_value or bool(re.fullmatch(r'-(?:[0txro]+|[IJLnPsRSE].+)', flag))
                if flag[:2] in ('-I', '-J'):
                    placeholder = flag[2:] if len(flag) > 2 else (
                        rest[1].word.value if len(rest) > 1 else '')
                    if not placeholder:
                        raise ValueError('xargs replacement needs a nonempty literal placeholder')
            else:
                valid = False
            if not valid:
                raise ValueError(f'unsupported {name} option: {flag}')
            rest = rest[1:]
            if takes_value:
                if not rest or rest[0].word.dynamic or rest[0].word.home:
                    raise ValueError(f'{name} {flag} needs a literal option argument')
                rest = rest[1:]
        if lookup:
            if not rest or any(t.word.dynamic or t.word.home for t in rest):
                raise ValueError('command lookup needs literal names')
            return [Command(tuple(t.word for t in rest), redirects, indirect, True,
                            wrappers + (first.word,))]
        if placeholder:
            rest = _replaced(rest, placeholder)
        return _commands(rest, redirects, indirect or name == 'xargs', depth + 1,
                         wrappers + (first.word,))
    if name == 'find':
        if indirect or any(t.word.dynamic for t in words[1:]):
            raise ValueError('find requires literal arguments and cannot receive indirect command input')
        parent, children = [first.word], []
        i = 1
        while i < len(words):
            arg = words[i].word.value
            if arg == '-delete':
                raise ValueError('find -delete does not identify fixed deletion targets')
            if arg in _FIND_VALUE or re.fullmatch(r'-newer[acmB][acmtB]', arg):
                if i + 1 == len(words):
                    raise ValueError(f'find {arg} needs an operand')
                parent.extend((words[i].word, words[i + 1].word))
                i += 2
                continue
            if arg not in _FIND_EXEC:
                if arg.startswith('-') and arg not in _FIND_FLAGS:
                    raise ValueError(f'unsupported find predicate: {arg}')
                parent.append(words[i].word)
                i += 1
                continue
            end = i + 1
            while end < len(words) and not (words[end].word.value == ';' or
                    words[end].word.value == '+' and words[end - 1].word.value == '{}'):
                end += 1
            if end == len(words) or end == i + 1:
                raise ValueError('find -exec needs a command and an escaped or quoted terminator')
            children += _commands(_replaced(words[i + 1:end], '{}'), (), True,
                                  depth + 1, wrappers)
            i = end + 1
        return [Command(tuple(parent), redirects, indirect, wrappers=wrappers), *children]
    return [Command(tuple(t.word for t in words), redirects, indirect, wrappers=wrappers)]


@lru_cache(maxsize=128)
def parse(command: str) -> tuple[Command, ...]:
    """Inspect simple shell commands without executing or expanding any candidate text.

    Unsupported syntax fails closed; this is not an interpreter or an effect checker
    for scripts and text-processing programs.
    """
    tokens = _lex(command)
    commands, words, redirects = [], [], []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if isinstance(token, _Token):
            words.append(token)
        elif _REDIRECT.fullmatch(token):
            i += 1
            if i == len(tokens) or not isinstance(tokens[i], _Token):
                raise ValueError('redirection needs a filename or file descriptor')
            redirects.append(tokens[i].word)
        else:
            if not words and not redirects:
                raise ValueError('empty command between shell operators')
            commands += _commands(words, tuple(redirects))
            words, redirects = [], []
            if token == '&' and i != len(tokens) - 1:
                raise ValueError('background operator is supported only at the end')
            if i == len(tokens) - 1 and token not in (';', '&'):
                raise ValueError('shell operator needs a following command')
        i += 1
    if words or redirects:
        commands += _commands(words, tuple(redirects))
    if not commands:
        raise ValueError('expected a nonempty shell command')
    return tuple(commands)
