#!/usr/bin/env python3
"""Verify raw teacher samples on macOS and build a prompt-matched chat dataset."""

import argparse
from collections import Counter
import hashlib
import json
import platform
import random
import re
import shlex
import statistics
from pathlib import Path

from check_corpus import jaccard, words
from teacher_sample import TEACHER_SYSTEM_PROMPT
from whatisit_macos.local_recovery_worker import MACOS_PREFIX
from whatisit_macos.maclint import validation_findings

SUBCOMMANDS = {'git', 'brew', 'defaults', 'hdiutil', 'diskutil', 'launchctl', 'npm', 'pip', 'plutil', 'xcrun'}
WRAPPERS = {'sudo', 'env', 'command', 'time', 'nohup'}
TRIVIAL = {'echo', 'printf', '[', '[[', 'test', 'true', 'false', ':'}  # shell glue; carries no tool knowledge
PATH_EXTENSIONS = {'txt', 'log', 'csv', 'json', 'plist', 'pdf', 'md', 'sh', 'py', 'zip', 'gz', 'tar', 'png',
                   'jpg', 'jpeg', 'dmg', 'iso', 'app', 'html', 'xml', 'yaml', 'yml', 'conf', 'bak', 'tmp', 'tsv', 'mov',
                   'm4a', 'wav', 'aiff', 'aif', 'mp3', 'mp4', 'zsh', 'bash', 'pkg', 'ips', 'heic', 'db', 'sqlite',
                   'rtf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'key', 'pages', 'numbers', 'swift', 'c',
                   'h', 'js', 'ts', 'rb', 'pl', 'sql', 'ini', 'cfg', 'toml', 'lock', 'out', 'dat', 'bin', 'img',
                   'cer', 'crt', 'pem', 'csr', 'p12', 'gif', 'tiff', 'bmp', 'webp', 'svg', 'epub', 'tgz', 'bz2',
                   'xz', '7z', 'rar', 'sparseimage', 'sparsebundle', 'webloc', 'strings', 'entitlements'}
INTERACTIVE = re.compile(r'\s*(?:sudo\s+)?(?:man|less|more|vi|vim|nano|emacs|top)\b[^|]*$')  # needs a terminal, not an answer
REDIRECT = re.compile(r'^(?:\d*|&)(?:>>|>|<)(?:&\d+)?$')
REVIEW_JACCARD = 0.5
SHORT_OPTION_TOOLS = {'ls', 'cp', 'mv', 'rm', 'df', 'du', 'ps', 'grep', 'sort', 'tar', 'chmod'}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _segments(command):
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|')
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError as error:
        raise ValueError(f'cannot tokenize command for leakage check: {error}') from error
    segments, current = [], []
    for token in tokens + [';']:
        if token in ('|', '|&', '&&', '||', ';', '&'):
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    if not tokens:
        raise ValueError('empty command signature in leakage check')
    return segments


def _flags(tool, args):
    flags = set()
    for arg in args:
        option = arg.split('=')[0]
        if tool in SHORT_OPTION_TOOLS and re.fullmatch(r'-[A-Za-z]{2,4}', option):
            flags.update('-' + char for char in option[1:])
        elif re.fullmatch(r'-[0-9]', option):
            flags.add(option)
        elif re.match(r'^-{1,2}[A-Za-z]', option):
            flags.add(option if re.fullmatch(r'-{1,2}[A-Za-z][\w-]*', option) else option[:2])
    return tuple(sorted(flags))


PROGRAM_TOOLS = {'sed', 'awk', 'gawk', 'grep', 'egrep', 'fgrep', 'perl', 'mdfind', 'tr', 'jq'}


def _path_like(arg, tool=''):
    """A filesystem operand: a single word of path characters (or a glob or known extension)."""
    if re.search(r'\s', arg) or re.search(r'[=(){}"\']', arg):
        return False  # programs, predicates and queries carry knowledge
    if re.fullmatch(r'\d+(?:\.\d+)?[A-Za-z]{0,2}', arg):
        return tool != 'chmod'  # PIDs, counts and durations are user literals; chmod modes are not
    if tool == 'sysctl':
        return False  # keys such as hw.ncpu look like file.ext
    return bool(re.fullmatch(r'[~./$][\w.*?\[\]~$/+-]*|[\w.*?\[\]+-]+(/[\w.*?\[\]+-]*)+/?', arg) or
                '*' in arg or '.' in arg and arg.rsplit('.', 1)[-1].lower() in PATH_EXTENSIONS)


def _parts(command):
    """Yield (tool, flags, operands) for each non-trivial pipeline stage."""
    for segment in _segments(command):
        while segment and (segment[0] in WRAPPERS or re.fullmatch(r'\w+=.*', segment[0])):
            segment.pop(0)
        if not segment or segment[0] in TRIVIAL:
            continue
        tool = Path(segment[0]).name
        args = segment[1:]
        if tool in SUBCOMMANDS and args and not args[0].startswith('-'):
            tool += ' ' + args.pop(0)
        cleaned, skip = [], False
        for a in args:  # redirections are plumbing, not operands
            if skip:
                skip = False
            elif REDIRECT.fullmatch(a):
                skip = not re.search(r'&\d+$', a)
            elif not re.match(r'^(?:\d*|&)(?:>>|>|<)\S', a):
                cleaned.append(a)
        args = cleaned
        words_ = [a for a in args if a and not a.startswith('-')]
        keep_first = {words_[0]} if tool in PROGRAM_TOOLS and words_ else set()  # sed/grep pattern, not a path
        operands = frozenset(a for a in words_ if a in keep_first or not _path_like(a, tool))
        yield tool, _flags(tool, args), operands


def signature(command):
    """Tool/subcommand and option names per stage, ignoring shell glue such as echo and [. Report-only."""
    return tuple((tool, flags) for tool, flags, _ in _parts(command))


def normalized(command):
    """Stages that carry specific knowledge: tool, flags and non-path operands (sysctl keys, mdls
    attributes, plutil formats, awk programs). A bare tool-plus-flags stage inside a pipeline counts
    only when the whole command is that single stage. Hard leakage check."""
    parts = list(_parts(command))
    return tuple(part for part in parts if part[2] or len(parts) == 1)


VALUE_FLAGS = {'head': {'-n', '-c'}, 'tail': {'-n', '-c'},
               'grep': {'-e', '-f', '-m', '-A', '-B', '-C'},
               'sort': {'-k', '-t', '-o', '-T', '-S'}, 'du': {'-d', '-I', '-B', '-t'},
               'ls': set(), 'cat': set(), 'wc': set(), 'df': set(),
               'system_profiler': {'-detailLevel', '-timeout'},
               'cp': set(), 'mv': set(), 'rm': set(), 'chmod': set(),
               'ps': {'-o', '-O', '-p', '-G', '-g', '-u', '-U', '-t'},
               'mdfind': {'-onlyin', '-name'}, 'mdls': {'-name', '-nullMarker'},
               'stat': {'-f', '-t'},
               'git': {'-C', '-c'}, 'date': {'-f', '-r', '-v', '-z'},
               'iostat': {'-c', '-n', '-w'},
               'openssl': {'-in', '-out', '-inform', '-outform', '-key', '-keyform',
                           '-passin', '-passout', '-subj', '-days', '-config', '-extensions',
                           '-reqexts', '-nameopt', '-newkey'},
               'xcodebuild': {'-project', '-workspace', '-scheme', '-configuration', '-sdk',
                             '-destination', '-arch', '-xcconfig', '-jobs', '-derivedDataPath',
                             '-resultBundlePath'},
               'find': {'-maxdepth', '-mindepth', '-type', '-name', '-iname', '-path', '-ipath',
                        '-size', '-user', '-group', '-perm', '-mtime', '-mmin', '-newer'}}
LONG_VALUES = {'grep': {'--max-count', '--regexp', '--file'}, 'curl': {'--output'}}
NO_VALUE_FLAGS = {
    'head': set(), 'tail': {'-F', '-f', '-q', '-r'},
    'grep': {'-' + c for c in 'a b c E F G H h I i l L n o q R r s v w x'.split()},
    'sort': {'-' + c for c in 'b c C d f g h i M m n R r s u V'.split()},
    'du': {'-' + c for c in 'A a c H h k L l m n P r s x'.split()},
    'ls': {'-' + c for c in 'ABCFGHLOPRSTUW@abcdefghiklmnopqrstuwx1'.strip()},
    'cat': {'-' + c for c in 'benstuv'}, 'wc': {'-' + c for c in 'clmw'},
    'df': {'-' + c for c in 'abcgHhiklmnP'},
    'system_profiler': {'-xml', '-json', '-listDataTypes'},
    'cp': {'-' + c for c in 'RHLPaficlNnpSsvXx'},
    'mv': {'-' + c for c in 'finv'}, 'rm': {'-' + c for c in 'dfiPRrvW'},
    'chmod': {'-' + c for c in 'fhRv'},
    'ps': {'-' + c for c in 'AaCcEefhjlLMmrSTvwXx'},
    'mdfind': {'-0', '-live', '-count', '-literal', '-interpret'}, 'mdls': {'-raw'},
    'stat': {'-' + c for c in 'FLnqlrsx'}, 'git': set(), 'date': {'-j', '-n', '-R', '-u'},
    'iostat': {'-' + c for c in 'CUdKIoT?'},
    'openssl': {'-text', '-noout', '-pubkey', '-subject', '-modulus', '-verify', '-new', '-nodes', '-x509'},
    'xcodebuild': {'-list', '-showBuildSettings', '-showdestinations', '-version', '-quiet', '-verbose', '-help'},
    'find': {'-H', '-L', '-P', '-E', '-X', '-d', '-s', '-x', '-empty'},
}
PATH_TOOLS = {'ls', 'cat', 'wc', 'head', 'tail', 'cp', 'mv', 'rm', 'du', 'df', 'find', 'stat',
              'mdls', 'plutil', 'ditto', 'afinfo', 'git status'}


def voting_key(command):
    """Conservative surface key; retain positional order and option/value bindings."""
    singleton = ('exact', command)
    if '\n' in command or '$(' in command or '`' in command:
        return singleton
    try:
        segments = _segments(command)
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|')
        lexer.whitespace_split = True
        tokens = list(lexer)
        raw_lexer = shlex.shlex(command, posix=False, punctuation_chars=';&|')
        raw_lexer.whitespace_split = True
        raw_tokens = list(raw_lexer)
        separators = tuple(t for t in tokens if t in ('|', '|&', '&&', '||', ';', '&'))
        if len(tokens) != len(raw_tokens) or len(separators) != len(segments) - 1:
            return singleton
        profiles, current = [], []
        for value, raw in zip(tokens, raw_tokens):
            if shlex.split(raw) != [value]:
                return singleton
            if raw.startswith('='):
                return singleton  # stock zsh expands leading =command to its executable path
            if ('$' in raw and any(q in raw for q in ('"', "'")) and not any(
                    raw.startswith(q) and raw.endswith(q) and raw.count(q) == 2 for q in ('"', "'"))):
                return singleton  # mixed quoting can change where a variable name ends
            if re.match(r'^(?:\d*|&)(?:>>|>|<)', value) and raw != value:
                return singleton
            if value in ('|', '|&', '&&', '||', ';', '&'):
                if raw != value:
                    return singleton
                profiles.append(current)
                current = []
                continue
            quote, expanded, position = '', [], 0
            for char in raw:
                if char in ('"', "'") and (not quote or quote == char):
                    quote = char if not quote else ''
                    continue
                elif char == '\\' and quote != "'":
                    return singleton  # escaped shell syntax requires more than shlex's word values
                elif quote != "'" and (char == '$' or not quote and char in '*?~[{}()^#!<>'):
                    expanded.append((position, char + quote))
                position += 1
            profile = tuple(expanded)
            if value.startswith('~/') and raw.startswith('~/'):
                profile = ((0, 'home'),) + profile[1:]
            elif value.startswith('$HOME/') and profile and profile[0] in ((0, '$'), (0, '$"')):
                profile = ((0, 'home'),) + tuple((pos - 4, char) for pos, char in profile[1:])
            current.append(profile)
        profiles.append(current)
    except ValueError:
        return singleton
    stages = []
    for stage_index, (segment, profile) in enumerate(zip(segments, profiles)):
        tool, *args = segment
        if tool in WRAPPERS | {'for', 'do', 'done', 'if', 'then', 'else', 'fi', 'case', 'esac',
                               'while', 'until', 'select', 'function'} or '=' in tool:
            return singleton
        if tool in SUBCOMMANDS and args and not args[0].startswith('-'):
            tool += ' ' + args.pop(0)
            profile.pop(1)
        if profile[0]:
            return singleton
        profile = profile[1:]
        flags, operands, positional, bindings, expansions = [], [], [], [], []
        ps_width = 0
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == '--':
                return singleton
            if arg.startswith('--'):
                option, eq, value = arg.partition('=')
                flags.append(option)
                if option in LONG_VALUES.get(tool, ()):
                    if not eq:
                        if i + 1 == len(args) or args[i + 1].startswith('-'):
                            return singleton
                        i += 1
                        value = args[i]
                    bindings.append((option, value))
                    operands.append(value)
                elif eq:
                    bindings.append((str(i), arg))
                    operands.append(value)
                else:
                    bindings.append((str(i), option))
                if profile[i]:
                    expansions.append((arg, profile[i]))
            elif arg.startswith('-') and arg != '-':
                if not _flags(tool, [arg]):
                    return singleton
                flags.append(arg)
                valued = set(_flags(tool, [arg])) & VALUE_FLAGS.get(tool, set())
                if tool == 'ps':
                    ps_width += arg[1:].count('w')
                if arg in VALUE_FLAGS.get(tool, set()) or (len(valued) == 1 and
                        tool in SHORT_OPTION_TOOLS and arg.endswith(next(iter(valued))[1:])):
                    if i + 1 == len(args):
                        return singleton
                    i += 1
                    value = args[i]
                    if (tool, arg) in (('mdfind', '-onlyin'), ('git', '-C')):
                        if value.startswith('$HOME/') and profile[i] and profile[i][0] == (0, 'home'):
                            value = '~/' + value[6:]
                        if value.startswith('./') and not value.startswith('.//'):
                            value = value[2:] or '.'
                        if len(value) > 1 and value.endswith('/'):
                            value = value[:-1]
                    bindings.append((next(iter(valued)), value))
                    operands.append(value)
                    if profile[i]:
                        expansions.append((value, profile[i]))
                elif (not set(_flags(tool, [arg])) <= NO_VALUE_FLAGS.get(tool, set()) and
                      not (tool == 'hdiutil attach' and arg in ('-nobrowse', '-noautoopen'))):
                    # Unknown option arity/order: keep its exact position rather than guess.
                    bindings.append((str(i), arg))
                elif len(arg) > 2 and any('-' + c in VALUE_FLAGS.get(tool, set()) for c in arg[1:]):
                    return singleton
            else:
                value = arg
                if tool in PATH_TOOLS or tool == '/usr/bin/time' and not positional:
                    if value.startswith('$HOME/') and profile[i] and profile[i][0] == (0, 'home'):
                        value = '~/' + value[6:]
                    if value.startswith('./') and not value.startswith('.//'):
                        relative = value[2:] or '.'
                        piped = stage_index < len(separators) and (
                            separators[stage_index] in ('|', '|&') or
                            any(re.match(r'^(?:\d*|&)>', token) for token in segment))
                        if (relative != '-' and (tool != '/usr/bin/time' or '/' in relative) and
                                (tool != 'git status' or _path_like(value)) and
                                (not piped or tool == 'cat' and separators[stage_index] == '|')):
                            value = relative
                operands.append(value)
                positional.append(value)
                if profile[i]:
                    expansions.append((value, profile[i]))
            i += 1
        # Retain order too: a multiset alone would merge cp a b with cp b a.
        canonical_flags = _flags(tool, flags)
        conflicts = {'sort': {'-n', '-g', '-h', '-M', '-R', '-V'},
                     'ls': {'-l', '-1', '-C', '-x', '-m'}, 'df': {'-h', '-H', '-k', '-m'},
                     'cp': {'-f', '-i', '-n'}, 'mv': {'-f', '-i', '-n'},
                     'ps': {'-m', '-r', '-v', '-f', '-j', '-l'},
                     'head': {'-n', '-c'}, 'tail': {'-n', '-c'}}
        if len(set(canonical_flags) & conflicts.get(tool, set())) > 1:
            return singleton
        if tool == 'cp' and len(set(canonical_flags) & {'-H', '-L', '-P'}) > 1:
            return singleton
        if tool == 'du' and (len(set(canonical_flags) & {'-g', '-h', '-k', '-m'}) > 1 or
                             len(set(canonical_flags) & {'-H', '-L', '-P'}) > 1):
            return singleton
        ordered_modes = {'ls': ({'-S', '-t', '-f'}, {'-c', '-u', '-U'}, {'-B', '-b', '-w', '-q'},
                                {'-H', '-L', '-P'}, {'-a', '-A'}, {'-F', '-p'}),
                         'find': ({'-H', '-L', '-P'},), 'du': ({'-a', '-s', '-d'},),
                         'date': ({'-f', '-r'},)}
        if any(len(set(canonical_flags) & group) > 1 for group in ordered_modes.get(tool, ())):
            return singleton
        if tool == 'cp' and '-a' in canonical_flags and set(canonical_flags) & {'-H', '-L'}:
            return singleton
        if tool == 'find' and any(a in args for a in
                ('-o', '-or', '-a', '-and', '!', '-not', '(', ')', '-exec', '-execdir',
                 '-print', '-print0', '-prune', '-delete', '-ls', '-ok', '-okdir')):
            return singleton
        if len({option for option, _ in bindings}) != len(bindings):
            return singleton  # repeated value options can be ordered or last-wins
        if tool == 'iostat' and '-d' in canonical_flags and set(canonical_flags) & {'-C', '-U', '-T'}:
            return singleton
        stages.append((tool, canonical_flags, tuple(sorted(operands)),
                       tuple(positional), tuple(sorted(bindings)), tuple(sorted(expansions)), ps_width))
    return ('stages', tuple(stages), separators) if stages else singleton


def command_vote(valid, mode):
    """Return the representative, winning count and exact strings (verified samples only)."""
    clusters = {}
    for command, count in valid.items():
        key = voting_key(command) if mode == 'equivalence' else command
        clusters.setdefault(key, Counter())[command] = count
    if not clusters:
        return None, 0, []
    cluster = max(clusters.values(), key=lambda c: sum(c.values()))
    size = sum(cluster.values())
    exact = [cmd for cmd, n in valid.items() if n >= 3]
    target = min(exact or cluster, key=lambda cmd: (-valid[cmd], len(cmd), cmd)) if size >= 3 else None
    return target, size, sorted(cluster)


def check_inputs(requests_path, raw_path, manifest_path):
    requests = read_jsonl(requests_path)
    raw = read_jsonl(raw_path)
    manifest = json.loads(manifest_path.read_text())
    if not requests or not raw or len(raw) > len(requests):
        raise ValueError('corpus/raw counts are invalid')
    if len({r['id'] for r in requests}) != len(requests):
        raise ValueError('duplicate corpus id')
    for i, record in enumerate(raw):
        request = requests[i]
        if record.get('id') != request['id'] or record.get('request') != request['request']:
            raise ValueError(f'raw row {i + 1} does not match corpus prefix')
        if (request['kind'] not in ('answer', 'abstain') or
                not isinstance(record.get('samples'), list) or len(record['samples']) != 5):
            raise ValueError(f'invalid kind or sample count for {request["id"]}')
        for sample in record['samples']:
            if (not isinstance(sample, dict) or 'command' not in sample or
                    not isinstance(sample.get('parsed'), bool) or
                    sample.get('command') is not None and not isinstance(sample['command'], str)):
                raise ValueError(f'invalid sample schema for {request["id"]}')
    required = ('model', 'quant', 'server', 'host', 'seed_base', 'temperature', 'top_p',
                'max_tokens', 'wall_seconds_this_run', 'requests_file_sha256', 'system_prompt_sha256')
    if any(manifest.get(k) in (None, '') for k in required):
        raise ValueError('teacher manifest is incomplete')
    if manifest.get('requests_total') != len(raw) or manifest.get('samples_per_request') != 5:
        raise ValueError('teacher manifest counts do not match raw samples')
    if manifest['requests_file_sha256'] != hashlib.sha256(requests_path.read_bytes()).hexdigest():
        raise ValueError('teacher manifest request hash mismatch')
    if manifest['system_prompt_sha256'] != hashlib.sha256(TEACHER_SYSTEM_PROMPT.encode()).hexdigest():
        raise ValueError('teacher system prompt hash mismatch')
    return requests, raw, manifest


def eval_leakage(requests, labels, eval_dir):
    """Return (hard, review): hard hits are quarantined; review hits are only reported."""
    eval_requests, eval_signatures, eval_normalized = [], {}, {}
    for split in ('dev', 'everyday', 'frozen', 'heldout'):
        for case in read_jsonl(eval_dir / f'{split}.jsonl'):
            eval_requests.append((split, words(case['request'])))
            for command in [case.get('reference'), *(case.get('also_correct') or [])]:
                if isinstance(command, str) and command.strip():
                    for part in signature(command):
                        eval_signatures.setdefault(part, set()).add(split)
                    for part in normalized(command):
                        eval_normalized.setdefault(part, set()).add(split)
    hard, review = set(), set()
    for row in requests:
        for split, target in eval_requests:
            score = jaccard(words(row['request']), target)
            if score >= 0.7:
                hard.add((row['id'], 'request', split))
            elif score >= REVIEW_JACCARD:
                review.add((row['id'], 'request similarity 0.5-0.7', split))
    for row in labels:
        command = row['messages'][-1]['content']
        if command:
            for part in normalized(command):
                for split in eval_normalized.get(part, ()):
                    hard.add((row['id'], 'normalized command', split))
            for part in signature(command):
                for split in eval_signatures.get(part, ()):
                    review.add((row['id'], 'tool+flags', split))
    return sorted(hard), sorted(review)


def read_quarantine(path, known):
    ids = {}
    for line in path.read_text().splitlines() if path.exists() else []:
        line = line.strip()
        if line and not line.startswith('#'):
            rid, _, why = line.partition('#')
            ids[rid.strip()] = why.strip()
    if set(ids) - known:
        raise ValueError(f'quarantine list names unknown ids: {sorted(set(ids) - known)}')
    return ids


def build(requests_path, raw_path, manifest_path, eval_dir, output_path, report_path, review_path,
          quarantine_path=Path('data/distill/quarantine_ids.txt'), vote='exact'):
    if platform.system() != 'Darwin':
        raise RuntimeError('host-grounded verification must run on macOS')
    from whatisit import config, safety

    if vote not in ('exact', 'equivalence'):
        raise ValueError('unknown vote mode')
    provenance_path = output_path.with_suffix('.votes.jsonl')
    conflicts_path = output_path.with_suffix('.conflicts.jsonl')
    base_manifest_path = output_path.with_suffix('.manifest.json')
    paths = (output_path, report_path, review_path) + ((provenance_path, conflicts_path, base_manifest_path) if vote == 'equivalence' else ())
    if any(path.exists() for path in paths) or vote == 'equivalence' and output_path.parent.exists():
        raise FileExistsError('output already exists; choose fresh paths')
    requests, raw, manifest = check_inputs(requests_path, raw_path, manifest_path)
    labels, decisions, abstain_reasons, dropped = [], Counter(), Counter(), []
    provenance, conflicts = [], []
    request_by_id = {r['id']: r for r in requests}
    agreement, rejects = Counter(), Counter()
    candidates = rejected_candidates = 0
    tokens = []
    for record in raw:
        valid = Counter()
        nulls = 0
        for sample in record['samples']:
            token_count = sample.get('completion_tokens')
            if isinstance(token_count, int):
                tokens.append(token_count)
            if sample['parsed'] is not True or sample.get('finish_reason') != 'stop':
                rejects['unparsed_or_incomplete'] += 1
                continue
            command = sample['command']
            if command is None:
                nulls += 1
                continue
            candidates += 1
            if not command.strip() or len(command) > 4096 or any(c in command for c in '\x00\r\n'):
                rejects['invalid_command'] += 1
                rejected_candidates += 1
                continue
            if INTERACTIVE.fullmatch(command):
                rejects['interactive'] += 1
                rejected_candidates += 1
                continue
            findings = validation_findings(command, record['request'],
                                           path=record.get('path'), safety=safety)
            rejects.update(findings.keys())
            if findings:
                rejected_candidates += 1
                continue
            valid[command] += 1
        target, best, strings = command_vote(valid, vote)
        agreement[best] += 1
        if best >= 3:
            if (vote == 'equivalence' and max(valid.values()) < 3 and
                    request_by_id[record['id']]['kind'] == 'abstain'):
                decisions['dropped_author_abstain_command_majority'] += 1
                dropped.append((record['id'], 'author_abstain_command_majority', best))
                conflicts.append({'id': record['id'], 'request': record['request'],
                                  'cluster_votes': best, 'strings': strings})
                continue
            decision = 'kept'
            if vote == 'equivalence' and max(valid.values()) < 3:
                provenance.append({'id': record['id'], 'vote_mode': vote,
                                   'cluster_votes': best, 'strings': strings})
        elif nulls >= 3 or request_by_id[record['id']]['kind'] == 'abstain':
            target = ''
            decision = 'abstain'
            abstain_reasons['teacher_null_majority' if nulls >= 3 else 'author_abstain_no_majority'] += 1
        else:
            reason = 'no_valid_command' if not valid else 'no_majority'
            decisions['dropped_' + reason] += 1
            dropped.append((record['id'], reason, best))
            continue
        decisions[decision] += 1
        labels.append({'id': record['id'], 'messages': [
            {'role': 'system', 'content': config.SYSTEM_PROMPT},
            {'role': 'user', 'content': MACOS_PREFIX + record['request']},
            {'role': 'assistant', 'content': target}]})

    leakage, review_hits = eval_leakage(requests, labels, eval_dir)
    listed = read_quarantine(quarantine_path, set(request_by_id))
    leakage = sorted(set(leakage) | {(rid, 'author quarantine list: ' + why, 'frozen/dev') for rid, why in listed.items()})
    quarantined = sorted({rid for rid, _, _ in leakage})
    for row in labels:
        if row['id'] in quarantined:
            decisions['kept' if row['messages'][-1]['content'] else 'abstain'] -= 1
    labels = [r for r in labels if r['id'] not in quarantined]
    provenance = [r for r in provenance if r['id'] not in quarantined]
    if vote == 'equivalence':
        decisions['recovered'] = len(provenance)
    commands = [r for r in labels if r['messages'][-1]['content']]
    sample = random.Random(7).sample(commands, min(30, len(commands)))
    drop_details = ''.join(f'- {rid}: {reason} (maximum agreement {best})\n'
                           for rid, reason, best in dropped) or 'None.\n'
    wall = manifest['wall_seconds_this_run']
    token_rate = (f'{sum(tokens) / wall:.1f} tokens/s' if wall and
                  manifest.get('requests_written_this_run') == len(raw) else 'unavailable for resumed run')
    by_kind = Counter((kind, split) for _, kind, split in review_hits)
    overlap_text = ('; '.join(f'{kind} vs {split}: {count} rows' for (kind, split), count in sorted(by_kind.items()))
                    or 'none') + f' ({len(review_hits)} row/split pairs; ids are in the review-hit list below).'
    overlap_text += ''.join(f'\n- quarantined {rid}: {kind} {split}' for rid, kind, split in leakage)
    overlap_text += ''.join(f'\n- {rid}: {kind} {split}' for rid, kind, split in review_hits if kind != 'tool+flags')
    report = f'''# Distillation quality report

Host: {platform.platform()} (macOS verification)

Teacher: {manifest['model']}
Quant: {manifest['quant']}
Server: {manifest['server']}
Teacher host: {manifest['host']}
Request SHA-256: {manifest['requests_file_sha256']}
Teacher prompt SHA-256: {manifest['system_prompt_sha256']}
Sampling: n=5, temperature={manifest['temperature']}, top-p={manifest['top_p']}, max tokens={manifest['max_tokens']}, seed base={manifest['seed_base']}.

Requests: {len(raw)}; kept commands: {decisions['kept']}; abstain: {decisions['abstain']}; dropped: {decisions['dropped_no_valid_command'] + decisions['dropped_no_majority']} ({decisions['dropped_no_valid_command']} no valid command, {decisions['dropped_no_majority']} no majority).
Agreement histogram (maximum identical verified commands): {dict(sorted(agreement.items()))}.
Teacher command candidates: {candidates}; rejected candidates: {rejected_candidates} ({rejected_candidates / candidates if candidates else 0:.1%}). Rejection findings (categories can overlap): {dict(sorted(rejects.items()))}.
Abstain reasons: {dict(sorted(abstain_reasons.items()))}.

Dropped rows:
{drop_details}

Recorded completion tokens: {sum(tokens)} total, {statistics.median(tokens) if tokens else 'unavailable'} median per sample.
Manifest wall time: {wall} s for this invocation ({manifest.get('requests_written_this_run', 'unknown')} requests written); throughput: {token_rate}; per-request latency was not recorded by the sampler.
Manifest metadata: finished={manifest.get('finished_at', 'unknown')}, top-k={manifest.get('top_k', 'unknown')}, note={manifest.get('note', '')!r}.

Evaluation leakage gate: {len(quarantined)} rows quarantined (excluded from the dataset, never trained on). Hard checks: request word-Jaccard >= 0.7 and normalized command (tool, flags and non-path operands) against dev, everyday and frozen references. The frozen set was used only for this gate.
Report-only overlaps (not gated): {overlap_text}

No-command target: empty assistant content. The serving worker returns `unsupported` with no command when upstream generation produces no complete command; the worker-path test covers this behavior. The Mac prompt audit (`docs/distill-prompt-audit.json`) confirmed that an empty target trains its end-of-turn token. A live-model abstention probe remains pending.

Human precision review: **pending**. {len(sample)} rows were saved to `{review_path}` with blank human verdicts; no precision estimate is claimed. At least 30 reviewed rows are required for acceptance.
'''
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in labels))
    review_path.write_text(''.join(json.dumps({**row, 'model_correct' if vote == 'equivalence' else 'human_correct': None, 'review_notes': ''},
                                               ensure_ascii=False) + '\n' for row in sample))
    report_path.write_text(report)
    if vote == 'equivalence':
        provenance_path.write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n'
                                          for r in provenance))
        conflicts_path.write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n'
                                         for r in conflicts))
        report_path.write_text(report.replace('Human precision review:', 'Model review:')
                               .replace('blank human verdicts', 'blank model verdicts')
                               .replace(str(review_path), review_path.name) +
                               f'\nVote mode: {vote}; recovered command rows after quarantine: {len(provenance)}.\n')
        base_manifest = {'vote_mode': vote, 'decisions': dict(sorted(decisions.items())),
                         'inputs_sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
                                           for name, path in [('requests', requests_path), ('raw', raw_path),
                                                              ('teacher_manifest', manifest_path),
                                                              ('quarantine', quarantine_path),
                                                              ('builder', Path(__file__))]},
                         'outputs_sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                            for path in paths if path != base_manifest_path}}
        base_manifest_path.write_text(json.dumps(base_manifest, sort_keys=True, indent=2) + '\n')
    return decisions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    defaults = {'requests': 'data/corpus/requests.jsonl',
                'raw': 'data/teacher/pilot_raw_samples.jsonl',
                'manifest': 'data/teacher/pilot_manifest.json',
                'eval-dir': 'eval',
                'out': 'data/distill/pilot_train.jsonl',
                'report': 'data/distill/quality_report.md',
                'review-sample': 'data/distill/pilot_review_sample.jsonl'}
    for flag, default in defaults.items():
        parser.add_argument('--' + flag, default=Path(default), type=Path)
    parser.add_argument('--quarantine', default=Path('data/distill/quarantine_ids.txt'), type=Path)
    parser.add_argument('--vote', choices=('exact', 'equivalence'), default='exact')
    args = parser.parse_args()
    print(build(args.requests, args.raw, args.manifest, args.eval_dir,
                args.out, args.report, args.review_sample, args.quarantine, args.vote))


if __name__ == '__main__':
    main()
